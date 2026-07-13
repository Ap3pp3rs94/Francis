"""Bounded local-only semantic observation for an allowlisted foreground game."""

from __future__ import annotations

import ctypes
import json
import math
import os
import re
import time
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from francis.lens.perception_capture import DesktopFrame

LENS_GAME_OBSERVATION_KIND = "lens.game.observation"
LENS_GAME_OBSERVATION_VERSION = 1

_TARGET_PROCESSES_ENV = "FRANCIS_LENS_GAME_TARGET_PROCESSES"
_TARGET_ID_ENV = "FRANCIS_LENS_GAME_TARGET_ID"
_MODEL_PATH_ENV = "FRANCIS_LENS_GAME_OBSERVER_MODEL_PATH"
_MODEL_ID_ENV = "FRANCIS_LENS_GAME_OBSERVER_MODEL_ID"
_SCENES_ENV = "FRANCIS_LENS_GAME_OBSERVER_SCENES_JSON"
_MIN_CONFIDENCE_ENV = "FRANCIS_LENS_GAME_OBSERVER_MIN_CONFIDENCE"
_MIN_MARGIN_ENV = "FRANCIS_LENS_GAME_OBSERVER_MIN_MARGIN"
_INFERENCE_INTERVAL_ENV = "FRANCIS_LENS_GAME_OBSERVER_INTERVAL_SECONDS"
_MAX_CLASSIFICATION_AGE_ENV = "FRANCIS_LENS_GAME_OBSERVER_MAX_AGE_SECONDS"

_PROCESS_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_. -]{1,128}\.exe$", re.IGNORECASE)
_TARGET_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_SCENE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{0,47}$")


@dataclass(frozen=True, slots=True)
class GameSceneDefinition:
    scene_id: str
    prompt: str

    def __post_init__(self) -> None:
        if not _SCENE_ID_PATTERN.fullmatch(self.scene_id):
            raise ValueError("lens_game_observer_scene_id_invalid")
        if not 4 <= len(self.prompt.strip()) <= 160:
            raise ValueError("lens_game_observer_scene_prompt_invalid")


_DEFAULT_SCENES = (
    GameSceneDefinition("active_gameplay", "an active video game gameplay scene"),
    GameSceneDefinition("game_menu", "a video game menu or setup screen"),
    GameSceneDefinition("loading", "a video game loading or transition screen"),
    GameSceneDefinition("paused", "a paused video game screen with an overlay menu"),
    GameSceneDefinition("other_application", "a computer desktop or another application instead of a game"),
)


@dataclass(frozen=True, slots=True)
class LensGameObserverConfig:
    target_id: str = ""
    target_processes: tuple[str, ...] = ()
    model_path: Path | None = None
    model_id: str = ""
    scenes: tuple[GameSceneDefinition, ...] = _DEFAULT_SCENES
    min_confidence: float = 0.35
    min_margin: float = 0.05
    inference_interval_seconds: float = 2.0
    max_classification_age_seconds: float = 6.0

    def __post_init__(self) -> None:
        if self.target_id and not _TARGET_ID_PATTERN.fullmatch(self.target_id):
            raise ValueError("lens_game_observer_target_id_invalid")
        if any(not _PROCESS_NAME_PATTERN.fullmatch(process_name) for process_name in self.target_processes):
            raise ValueError("lens_game_observer_target_process_invalid")
        if self.target_processes and not self.target_id:
            raise ValueError("lens_game_observer_target_id_required")
        if self.model_path is not None and not self.model_path.is_absolute():
            raise ValueError("lens_game_observer_model_path_must_be_absolute")
        if not 2 <= len(self.scenes) <= 8 or len({scene.scene_id for scene in self.scenes}) != len(self.scenes):
            raise ValueError("lens_game_observer_scenes_invalid")
        if not math.isfinite(self.min_confidence) or not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("lens_game_observer_min_confidence_invalid")
        if not math.isfinite(self.min_margin) or not 0.0 <= self.min_margin <= 1.0:
            raise ValueError("lens_game_observer_min_margin_invalid")
        if not math.isfinite(self.inference_interval_seconds) or not 0.5 <= self.inference_interval_seconds <= 30.0:
            raise ValueError("lens_game_observer_interval_invalid")
        if (
            not math.isfinite(self.max_classification_age_seconds)
            or not self.inference_interval_seconds <= self.max_classification_age_seconds <= 60.0
        ):
            raise ValueError("lens_game_observer_max_age_invalid")

    @property
    def target_configured(self) -> bool:
        return bool(self.target_id and self.target_processes)

    @property
    def model_configured(self) -> bool:
        return self.model_path is not None and bool(self.model_id)

    @classmethod
    def from_environment(cls) -> LensGameObserverConfig:
        target_processes = tuple(
            dict.fromkeys(
                process_name.strip()
                for process_name in os.environ.get(_TARGET_PROCESSES_ENV, "").split(",")
                if process_name.strip()
            )
        )
        raw_target_id = os.environ.get(_TARGET_ID_ENV, "").strip().casefold()
        target_id = raw_target_id or (_derived_target_id(target_processes[0]) if target_processes else "")
        raw_model_path = os.environ.get(_MODEL_PATH_ENV, "").strip()
        model_path = Path(raw_model_path).expanduser() if raw_model_path else None
        model_id = os.environ.get(_MODEL_ID_ENV, "").strip() or (model_path.name if model_path is not None else "")
        return cls(
            target_id=target_id,
            target_processes=target_processes,
            model_path=model_path,
            model_id=model_id,
            scenes=_scenes_from_environment(),
            min_confidence=_environment_float(_MIN_CONFIDENCE_ENV, 0.35),
            min_margin=_environment_float(_MIN_MARGIN_ENV, 0.05),
            inference_interval_seconds=_environment_float(_INFERENCE_INTERVAL_ENV, 2.0),
            max_classification_age_seconds=_environment_float(_MAX_CLASSIFICATION_AGE_ENV, 6.0),
        )


class GameObservationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class GameSceneClassifier(Protocol):
    def classify(self, frame: DesktopFrame, scenes: tuple[GameSceneDefinition, ...]) -> dict[str, Any]: ...


class GameObserver(Protocol):
    def observe(
        self,
        *,
        frame: DesktopFrame,
        source_frame_id: str,
        authority_receipt_id: str,
        observed_at: float | None = None,
    ) -> dict[str, Any]: ...

    def close(self) -> None: ...


class LocalTransformersZeroShotClassifier:
    """Lazy local Transformers classifier; model files are never fetched at runtime."""

    def __init__(self, *, model_path: Path, model_id: str) -> None:
        self.model_path = model_path
        self.model_id = model_id
        self._processor: Any = None
        self._model: Any = None
        self._torch: Any = None
        self._device = ""

    def classify(self, frame: DesktopFrame, scenes: tuple[GameSceneDefinition, ...]) -> dict[str, Any]:
        self._ensure_loaded()
        started = time.perf_counter()
        image: Any = None
        try:
            from PIL import Image

            image = Image.frombytes("RGBA", (frame.width, frame.height), frame.bgra, "raw", "BGRA").convert("RGB")
            inputs = self._processor(
                text=[scene.prompt for scene in scenes],
                images=image,
                padding="max_length",
                return_tensors="pt",
            )
            inputs = {name: value.to(self._device) for name, value in inputs.items()}
            with self._torch.inference_mode():
                outputs = self._model(**inputs)
            logits = outputs.logits_per_image
            probabilities = logits.softmax(dim=-1)[0]
            raw_scores = probabilities.detach().cpu().tolist()
        except GameObservationError:
            raise
        except Exception as exc:
            raise GameObservationError("lens_game_observer_inference_failed") from exc
        finally:
            if image is not None:
                image.close()
        scores: list[dict[str, Any]] = [
            {"scene_id": scene.scene_id, "score": round(float(score), 6)}
            for scene, score in zip(scenes, raw_scores, strict=True)
        ]
        scores.sort(key=lambda item: float(item["score"]), reverse=True)
        return {
            "scores": scores,
            "inference_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "device": self._device,
            "backend": "transformers_zero_shot_image_classification",
            "score_normalization": "softmax_over_mutually_exclusive_scenes",
        }

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        if not self.model_path.is_dir():
            raise GameObservationError("lens_game_observer_model_files_missing")
        try:
            import torch
            from transformers import AutoModelForZeroShotImageClassification, AutoProcessor

            processor = AutoProcessor.from_pretrained(str(self.model_path), local_files_only=True)
            model = AutoModelForZeroShotImageClassification.from_pretrained(
                str(self.model_path),
                local_files_only=True,
                use_safetensors=True,
            )
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model.to(device)
            model.eval()
        except ImportError as exc:
            raise GameObservationError("lens_game_observer_dependencies_missing") from exc
        except Exception as exc:
            raise GameObservationError("lens_game_observer_model_load_failed") from exc
        self._torch = torch
        self._processor = processor
        self._model = model
        self._device = device


class LensGameObserver:
    """Observe one configured foreground game without input or durable memory authority."""

    def __init__(
        self,
        config: LensGameObserverConfig,
        *,
        foreground_process: Any = None,
        classifier: GameSceneClassifier | None = None,
        executor: Executor | None = None,
        clock: Any = time.time,
    ) -> None:
        self.config = config
        self._foreground_process = foreground_process or windows_foreground_process_readback
        self._classifier = classifier
        if self._classifier is None and config.model_path is not None:
            self._classifier = LocalTransformersZeroShotClassifier(
                model_path=config.model_path,
                model_id=config.model_id,
            )
        self._executor = executor
        self._owns_executor = False
        if self._executor is None and self._classifier is not None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="francis-game-observer")
            self._owns_executor = True
        self._clock = clock
        self._pending: Future[dict[str, Any]] | None = None
        self._pending_source_frame_id = ""
        self._pending_submitted_at = 0.0
        self._last_submission_at: float | None = None
        self._last_classification: dict[str, Any] = {}

    @classmethod
    def from_environment(cls) -> LensGameObserver:
        try:
            config = LensGameObserverConfig.from_environment()
        except (TypeError, ValueError, json.JSONDecodeError):
            config = LensGameObserverConfig()
            observer = cls(config)
            observer._last_classification = {"error": "lens_game_observer_configuration_invalid"}
            return observer
        return cls(config)

    def observe(
        self,
        *,
        frame: DesktopFrame,
        source_frame_id: str,
        authority_receipt_id: str,
        observed_at: float | None = None,
    ) -> dict[str, Any]:
        now = self._clock() if observed_at is None else float(observed_at)
        frame_id = str(source_frame_id or "").strip()
        receipt_id = str(authority_receipt_id or "").strip()
        if not math.isfinite(now) or now < frame.captured_at or not frame_id:
            raise ValueError("lens_game_observer_observation_invalid")
        self._harvest_pending()
        foreground = self._read_foreground_process()
        process_name = str(foreground.get("process_name") or "")
        target_match = bool(
            foreground.get("available") is True
            and process_name
            and process_name.casefold() in {target.casefold() for target in self.config.target_processes}
        )
        base = self._base_payload(
            source_frame_id=frame_id,
            authority_receipt_id=receipt_id,
            observed_at=now,
            target_match=target_match,
            foreground=foreground,
        )
        if self._last_classification.get("error") == "lens_game_observer_configuration_invalid":
            return _blocked_payload(base, "configuration_invalid", "lens_game_observer_configuration_invalid")
        if not receipt_id:
            return _blocked_payload(base, "authority_missing", "lens_game_observer_authority_receipt_missing")
        if not self.config.target_configured:
            return _blocked_payload(base, "not_configured", "lens_game_observer_target_not_configured")
        if foreground.get("available") is not True:
            return _blocked_payload(base, "foreground_unavailable", "lens_game_observer_foreground_process_unavailable")
        if not target_match:
            return _blocked_payload(base, "target_not_foreground", "lens_game_target_not_foreground")
        if not self.config.model_configured or self._classifier is None or self._executor is None:
            return _blocked_payload(base, "semantic_model_not_configured", "lens_game_semantic_model_not_configured")
        if self.config.model_path is None or not self.config.model_path.is_dir():
            return _blocked_payload(base, "semantic_model_missing", "lens_game_observer_model_files_missing")

        if self._should_submit(now):
            self._pending = self._executor.submit(self._classifier.classify, frame, self.config.scenes)
            self._pending_source_frame_id = frame_id
            self._pending_submitted_at = now
            self._last_submission_at = now

        classification = self._last_classification
        if classification.get("error"):
            return _blocked_payload(base, "semantic_inference_failed", str(classification["error"]))
        classified_at = _safe_float(classification.get("classified_at"))
        age_seconds = now - classified_at if classified_at is not None else None
        fresh = bool(
            age_seconds is not None
            and 0.0 <= age_seconds <= self.config.max_classification_age_seconds
            and classification.get("source_frame_id")
        )
        if not fresh:
            return _blocked_payload(base, "semantic_warming", "lens_game_semantic_inference_pending")

        scores = _score_items(classification.get("scores"))
        scene = _select_scene(
            scores,
            min_confidence=self.config.min_confidence,
            min_margin=self.config.min_margin,
        )
        semantic_ready = scene.get("ready") is True
        base.update(
            {
                "status": "scene_classified" if semantic_ready else "scene_uncertain",
                "ready": semantic_ready,
                "semantic_scene_ready": semantic_ready,
                "scene": scene,
                "classification": {
                    "source_frame_id": str(classification.get("source_frame_id") or ""),
                    "classified_at": classified_at,
                    "age_ms": round(max(0.0, age_seconds or 0.0) * 1000.0, 3),
                    "inference_ms": _safe_float(classification.get("inference_ms")),
                    "device": str(classification.get("device") or ""),
                    "backend": str(classification.get("backend") or ""),
                    "score_normalization": str(classification.get("score_normalization") or ""),
                },
                "blockers": [] if semantic_ready else ["lens_game_scene_confidence_below_threshold"],
            }
        )
        return base

    def close(self) -> None:
        if self._owns_executor and isinstance(self._executor, ThreadPoolExecutor):
            self._executor.shutdown(wait=False, cancel_futures=True)

    def _harvest_pending(self) -> None:
        if self._pending is None or not self._pending.done():
            return
        try:
            result = self._pending.result()
        except GameObservationError as exc:
            self._last_classification = {"error": exc.code}
        except Exception:
            self._last_classification = {"error": "lens_game_observer_inference_failed"}
        else:
            self._last_classification = {
                **result,
                "source_frame_id": self._pending_source_frame_id,
                "submitted_at": self._pending_submitted_at,
                "classified_at": self._clock(),
            }
        self._pending = None
        self._pending_source_frame_id = ""
        self._pending_submitted_at = 0.0

    def _read_foreground_process(self) -> dict[str, Any]:
        try:
            readback = self._foreground_process()
        except Exception:
            return {"supported": os.name == "nt", "available": False, "reason": "foreground_process_read_failed"}
        return readback if isinstance(readback, dict) else {"supported": False, "available": False}

    def _should_submit(self, now: float) -> bool:
        return bool(
            self._pending is None
            and (
                self._last_submission_at is None
                or now - self._last_submission_at >= self.config.inference_interval_seconds
            )
        )

    def _base_payload(
        self,
        *,
        source_frame_id: str,
        authority_receipt_id: str,
        observed_at: float,
        target_match: bool,
        foreground: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "kind": LENS_GAME_OBSERVATION_KIND,
            "version": LENS_GAME_OBSERVATION_VERSION,
            "status": "blocked",
            "ready": False,
            "semantic_scene_ready": False,
            "source_frame_id": source_frame_id,
            "observed_at": observed_at,
            "target": {
                "id": self.config.target_id,
                "configured": self.config.target_configured,
                "process_names": list(self.config.target_processes),
                "foreground": target_match,
                "visibility_basis": "foreground_process_match" if target_match else "not_observed",
            },
            "foreground": {
                "supported": foreground.get("supported") is True,
                "available": foreground.get("available") is True,
                "target_match": target_match,
                "process_id": _safe_int(foreground.get("process_id")) if target_match else 0,
                "process_name": str(foreground.get("process_name") or "") if target_match else "",
                "window_id": _safe_int(foreground.get("window_id")) if target_match else 0,
                "window_title_included": False,
            },
            "scene": {},
            "classification": {},
            "model": {
                "id": self.config.model_id,
                "configured": self.config.model_configured,
                "local_files_present": bool(self.config.model_path and self.config.model_path.is_dir()),
                "remote_inference": False,
            },
            "runtime_identity": {"authority_receipt_id": authority_receipt_id},
            "blockers": [],
            "governance": {
                "observation_only": True,
                "local_inference_only": True,
                "remote_frame_transfer": False,
                "raw_pixels_in_state": False,
                "window_titles_captured": False,
                "keyboard_content_captured": False,
                "user_mouse_captured": False,
                "input_execution_authority": False,
                "memory_write": False,
                "learning_authority": False,
                "reward_authority": False,
            },
        }


def windows_foreground_process_readback() -> dict[str, Any]:
    if os.name != "nt":
        return {"supported": False, "available": False, "reason": "foreground_process_platform_unsupported"}
    try:
        from ctypes import wintypes

        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None:
            return {"supported": False, "available": False, "reason": "foreground_process_platform_unsupported"}
        user32 = win_dll("user32", use_last_error=True)
        kernel32 = win_dll("kernel32", use_last_error=True)
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        window = user32.GetForegroundWindow()
        if not window:
            return {"supported": True, "available": False, "reason": "foreground_window_missing"}
        process_id = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
        if not process_id.value:
            return {"supported": True, "available": False, "reason": "foreground_process_missing"}
        process = kernel32.OpenProcess(0x1000, False, process_id.value)
        if not process:
            return {"supported": True, "available": False, "reason": "foreground_process_open_failed"}
        try:
            capacity = wintypes.DWORD(32_768)
            buffer = ctypes.create_unicode_buffer(capacity.value)
            if not kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(capacity)):
                return {"supported": True, "available": False, "reason": "foreground_process_query_failed"}
        finally:
            kernel32.CloseHandle(process)
        process_name = Path(buffer.value).name
        if not process_name:
            return {"supported": True, "available": False, "reason": "foreground_process_name_missing"}
        return {
            "supported": True,
            "available": True,
            "window_id": int(window),
            "process_id": int(process_id.value),
            "process_name": process_name,
            "window_title_included": False,
        }
    except Exception:
        return {"supported": False, "available": False, "reason": "foreground_process_read_failed"}


def _blocked_payload(payload: dict[str, Any], status: str, blocker: str) -> dict[str, Any]:
    payload.update({"status": status, "ready": False, "semantic_scene_ready": False, "blockers": [blocker]})
    return payload


def _select_scene(
    scores: list[dict[str, Any]],
    *,
    min_confidence: float,
    min_margin: float,
) -> dict[str, Any]:
    if not scores:
        return {"ready": False, "id": "", "confidence": 0.0, "margin": 0.0, "candidates": []}
    ordered = sorted(scores, key=lambda item: float(item["score"]), reverse=True)
    confidence = float(ordered[0]["score"])
    runner_up = float(ordered[1]["score"]) if len(ordered) > 1 else 0.0
    margin = max(0.0, confidence - runner_up)
    ready = confidence >= min_confidence and margin >= min_margin
    return {
        "ready": ready,
        "id": str(ordered[0]["scene_id"]) if ready else "uncertain",
        "top_candidate_id": str(ordered[0]["scene_id"]),
        "confidence": round(confidence, 6),
        "margin": round(margin, 6),
        "min_confidence": min_confidence,
        "min_margin": min_margin,
        "candidates": ordered[:3],
    }


def _score_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        scene_id = str(item.get("scene_id") or "")
        score = _safe_float(item.get("score"))
        if _SCENE_ID_PATTERN.fullmatch(scene_id) and score is not None and 0.0 <= score <= 1.0:
            items.append({"scene_id": scene_id, "score": score})
    return items


def _scenes_from_environment() -> tuple[GameSceneDefinition, ...]:
    raw = os.environ.get(_SCENES_ENV, "").strip()
    if not raw:
        return _DEFAULT_SCENES
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("lens_game_observer_scenes_invalid")
    return tuple(GameSceneDefinition(str(scene_id), str(prompt)) for scene_id, prompt in payload.items())


def _environment_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    return default if not raw else float(raw)


def _derived_target_id(process_name: str) -> str:
    stem = Path(process_name).stem.casefold()
    cleaned = re.sub(r"[^a-z0-9_.-]+", "-", stem).strip("-.")
    return cleaned[:64]


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


__all__ = [
    "GameObservationError",
    "GameObserver",
    "GameSceneDefinition",
    "LENS_GAME_OBSERVATION_KIND",
    "LENS_GAME_OBSERVATION_VERSION",
    "LensGameObserver",
    "LensGameObserverConfig",
    "LocalTransformersZeroShotClassifier",
    "windows_foreground_process_readback",
]
