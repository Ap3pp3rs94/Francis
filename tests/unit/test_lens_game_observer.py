from __future__ import annotations

import json
from concurrent.futures import Executor, Future
from pathlib import Path
from typing import Any

import pytest

from francis.lens.game_observer import (
    GameSceneDefinition,
    LensGameObserver,
    LensGameObserverConfig,
)
from francis.lens.perception_capture import DesktopFrame


class _ImmediateExecutor(Executor):
    def submit(self, fn, /, *args, **kwargs):
        future: Future[dict[str, Any]] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:
            future.set_exception(exc)
        return future


class _Classifier:
    def __init__(self, scores: list[dict[str, Any]]) -> None:
        self.scores = scores
        self.calls = 0

    def classify(self, frame: DesktopFrame, scenes: tuple[GameSceneDefinition, ...]) -> dict[str, Any]:
        self.calls += 1
        assert frame.width == 2
        assert {scene.scene_id for scene in scenes} == {"active_gameplay", "game_menu"}
        return {
            "scores": self.scores,
            "inference_ms": 12.5,
            "device": "cpu",
            "backend": "test_zero_shot_classifier",
            "score_normalization": "softmax_over_mutually_exclusive_scenes",
        }


def _frame(*, captured_at: float = 100.0) -> DesktopFrame:
    return DesktopFrame(
        captured_at=captured_at,
        origin_x=0,
        origin_y=0,
        source_width=1920,
        source_height=1080,
        width=2,
        height=2,
        bgra=bytes((10, 20, 30, 0)) * 4,
        backend="synthetic_game_observer_test",
    )


def _config(model_path: Path) -> LensGameObserverConfig:
    return LensGameObserverConfig(
        target_id="sand",
        target_processes=("Sand.exe", "Sand-Win64-Shipping.exe"),
        model_path=model_path,
        model_id="test/siglip",
        scenes=(
            GameSceneDefinition("active_gameplay", "an active video game gameplay scene"),
            GameSceneDefinition("game_menu", "a video game menu screen"),
        ),
        min_confidence=0.35,
        min_margin=0.05,
        inference_interval_seconds=2.0,
        max_classification_age_seconds=6.0,
    )


def _foreground(process_name: str = "Sand.exe") -> dict[str, Any]:
    return {
        "supported": True,
        "available": True,
        "window_id": 44,
        "process_id": 55,
        "process_name": process_name,
        "window_title": "private title must not propagate",
    }


def test_config_reads_bounded_target_and_scene_environment(tmp_path: Path, monkeypatch) -> None:
    model_path = tmp_path / "model"
    monkeypatch.setenv("FRANCIS_LENS_GAME_TARGET_PROCESSES", "Sand.exe,Sand-Win64-Shipping.exe,Sand.exe")
    monkeypatch.setenv("FRANCIS_LENS_GAME_TARGET_ID", "sand")
    monkeypatch.setenv("FRANCIS_LENS_GAME_OBSERVER_MODEL_PATH", str(model_path))
    monkeypatch.setenv("FRANCIS_LENS_GAME_OBSERVER_MODEL_ID", "google/siglip-base-patch16-224")
    monkeypatch.setenv(
        "FRANCIS_LENS_GAME_OBSERVER_SCENES_JSON",
        json.dumps({"active_gameplay": "active gameplay", "game_menu": "a game menu"}),
    )

    config = LensGameObserverConfig.from_environment()

    assert config.target_processes == ("Sand.exe", "Sand-Win64-Shipping.exe")
    assert config.target_id == "sand"
    assert config.model_path == model_path
    assert [scene.scene_id for scene in config.scenes] == ["active_gameplay", "game_menu"]


def test_config_rejects_process_paths() -> None:
    with pytest.raises(ValueError, match="lens_game_observer_target_process_invalid"):
        LensGameObserverConfig(target_id="sand", target_processes=(r"C:\Games\Sand.exe",))


def test_observer_classifies_allowlisted_foreground_game_without_leaking_window_title(tmp_path: Path) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    classifier = _Classifier(
        [
            {"scene_id": "active_gameplay", "score": 0.78},
            {"scene_id": "game_menu", "score": 0.12},
        ]
    )
    observer = LensGameObserver(
        _config(model_path),
        foreground_process=_foreground,
        classifier=classifier,
        executor=_ImmediateExecutor(),
        clock=lambda: 100.15,
    )

    warming = observer.observe(
        frame=_frame(),
        source_frame_id="frame-1",
        authority_receipt_id="capture-receipt",
        observed_at=100.1,
    )
    classified = observer.observe(
        frame=_frame(captured_at=100.2),
        source_frame_id="frame-2",
        authority_receipt_id="capture-receipt",
        observed_at=100.2,
    )

    assert warming["status"] == "semantic_warming"
    assert classified["status"] == "scene_classified"
    assert classified["semantic_scene_ready"] is True
    assert classified["scene"]["id"] == "active_gameplay"
    assert classified["classification"]["source_frame_id"] == "frame-1"
    assert classified["classification"]["score_normalization"] == "softmax_over_mutually_exclusive_scenes"
    assert classified["foreground"]["process_name"] == "Sand.exe"
    assert classified["foreground"]["window_title_included"] is False
    assert "private title" not in json.dumps(classified)
    assert classified["governance"]["input_execution_authority"] is False
    assert classified["governance"]["learning_authority"] is False
    assert classifier.calls == 1


def test_observer_keeps_low_margin_scene_truthfully_uncertain(tmp_path: Path) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    classifier = _Classifier(
        [
            {"scene_id": "active_gameplay", "score": 0.45},
            {"scene_id": "game_menu", "score": 0.43},
        ]
    )
    observer = LensGameObserver(
        _config(model_path),
        foreground_process=_foreground,
        classifier=classifier,
        executor=_ImmediateExecutor(),
        clock=lambda: 100.15,
    )
    observer.observe(
        frame=_frame(),
        source_frame_id="frame-1",
        authority_receipt_id="capture-receipt",
        observed_at=100.1,
    )

    result = observer.observe(
        frame=_frame(captured_at=100.2),
        source_frame_id="frame-2",
        authority_receipt_id="capture-receipt",
        observed_at=100.2,
    )

    assert result["status"] == "scene_uncertain"
    assert result["semantic_scene_ready"] is False
    assert result["scene"]["id"] == "uncertain"
    assert result["blockers"] == ["lens_game_scene_confidence_below_threshold"]


def test_observer_does_not_classify_or_disclose_unrelated_foreground_process(tmp_path: Path) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    classifier = _Classifier([])
    observer = LensGameObserver(
        _config(model_path),
        foreground_process=lambda: _foreground("Code.exe"),
        classifier=classifier,
        executor=_ImmediateExecutor(),
    )

    result = observer.observe(
        frame=_frame(),
        source_frame_id="frame-1",
        authority_receipt_id="capture-receipt",
        observed_at=100.1,
    )

    assert result["status"] == "target_not_foreground"
    assert result["foreground"]["target_match"] is False
    assert result["foreground"]["process_name"] == ""
    assert result["foreground"]["process_id"] == 0
    assert "Code.exe" not in json.dumps(result)
    assert classifier.calls == 0


def test_observer_reports_missing_local_model_before_inference(tmp_path: Path) -> None:
    observer = LensGameObserver(
        _config(tmp_path / "missing-model"),
        foreground_process=_foreground,
    )
    try:
        result = observer.observe(
            frame=_frame(),
            source_frame_id="frame-1",
            authority_receipt_id="capture-receipt",
            observed_at=100.1,
        )
    finally:
        observer.close()

    assert result["status"] == "semantic_model_missing"
    assert result["model"]["remote_inference"] is False
    assert result["blockers"] == ["lens_game_observer_model_files_missing"]
