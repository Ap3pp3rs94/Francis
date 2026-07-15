"""Bounded local-only semantic observation for an existing foreground game."""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import re
import time
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from francis.kernel.paths import data_dir, repo_root
from francis.lens.perception_capture import DesktopFrame

LENS_GAME_OBSERVATION_KIND = "lens.game.observation"
LENS_GAME_OBSERVATION_VERSION = 2
LENS_GAME_OBSERVER_CONFIG_KIND = "lens.game_observer.runtime_config"
LENS_GAME_OBSERVER_CONFIG_VERSION = 2

_LEGACY_GAME_OBSERVER_CONFIG_VERSION = 1
_TARGET_MODE_PROCESS_ALLOWLIST = "process_allowlist"
_TARGET_MODE_FOREGROUND_GAME = "foreground_game"
_TARGET_MODES = frozenset({_TARGET_MODE_PROCESS_ALLOWLIST, _TARGET_MODE_FOREGROUND_GAME})
_SUPPORTED_GAME_LAUNCHERS = frozenset({"steam"})

_CONFIG_PATH_ENV = "FRANCIS_LENS_GAME_OBSERVER_CONFIG_PATH"
_TARGET_PROCESSES_ENV = "FRANCIS_LENS_GAME_TARGET_PROCESSES"
_TARGET_ID_ENV = "FRANCIS_LENS_GAME_TARGET_ID"
_MODEL_PATH_ENV = "FRANCIS_LENS_GAME_OBSERVER_MODEL_PATH"
_MODEL_ID_ENV = "FRANCIS_LENS_GAME_OBSERVER_MODEL_ID"
_SCENES_ENV = "FRANCIS_LENS_GAME_OBSERVER_SCENES_JSON"
_MIN_CONFIDENCE_ENV = "FRANCIS_LENS_GAME_OBSERVER_MIN_CONFIDENCE"
_MIN_MARGIN_ENV = "FRANCIS_LENS_GAME_OBSERVER_MIN_MARGIN"
_INFERENCE_INTERVAL_ENV = "FRANCIS_LENS_GAME_OBSERVER_INTERVAL_SECONDS"
_MAX_CLASSIFICATION_AGE_ENV = "FRANCIS_LENS_GAME_OBSERVER_MAX_AGE_SECONDS"

_CONFIG_MAX_BYTES = 64 * 1024
_CONFIGURATION_SOURCES = frozenset(
    {
        "unconfigured",
        "environment",
        "runtime_config",
        "runtime_config_with_environment_overrides",
        "invalid",
    }
)
_ENVIRONMENT_OVERRIDE_NAMES = (
    _TARGET_PROCESSES_ENV,
    _TARGET_ID_ENV,
    _MODEL_PATH_ENV,
    _MODEL_ID_ENV,
    _SCENES_ENV,
    _MIN_CONFIDENCE_ENV,
    _MIN_MARGIN_ENV,
    _INFERENCE_INTERVAL_ENV,
    _MAX_CLASSIFICATION_AGE_ENV,
)
_LEGACY_RUNTIME_GOVERNANCE = {
    "observation_only": True,
    "local_inference_only": True,
    "remote_frame_transfer": False,
    "raw_pixels_in_observer_state": False,
    "window_titles_captured": False,
    "keyboard_content_captured": False,
    "user_mouse_captured": False,
    "input_execution_authority": False,
    "memory_write": False,
    "learning_authority": False,
    "reward_authority": False,
}
_EXPECTED_RUNTIME_GOVERNANCE = {
    **_LEGACY_RUNTIME_GOVERNANCE,
    "foreground_game_required": True,
    "local_process_launch_authority": False,
}

_PROCESS_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_. -]{1,128}\.exe$", re.IGNORECASE)
_TARGET_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_SCENE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{0,47}$")
_STEAM_LIBRARY_PATH_PATTERN = re.compile(r'^\s*"path"\s+"((?:\\\\.|[^"\\])*)"\s*$', re.MULTILINE)
_STEAM_LIBRARY_CONFIG_MAX_BYTES = 512 * 1024


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
    enabled: bool = True
    target_id: str = ""
    target_processes: tuple[str, ...] = ()
    target_mode: str = _TARGET_MODE_PROCESS_ALLOWLIST
    game_launchers: tuple[str, ...] = ()
    model_path: Path | None = None
    model_id: str = ""
    scenes: tuple[GameSceneDefinition, ...] = _DEFAULT_SCENES
    min_confidence: float = 0.35
    min_margin: float = 0.05
    inference_interval_seconds: float = 2.0
    max_classification_age_seconds: float = 6.0
    configuration_source: str = "unconfigured"
    configuration_path_label: str = ""
    configuration_fingerprint: str = ""
    environment_override_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("lens_game_observer_enabled_invalid")
        if self.target_id and not _TARGET_ID_PATTERN.fullmatch(self.target_id):
            raise ValueError("lens_game_observer_target_id_invalid")
        if any(not _PROCESS_NAME_PATTERN.fullmatch(process_name) for process_name in self.target_processes):
            raise ValueError("lens_game_observer_target_process_invalid")
        if self.target_mode not in _TARGET_MODES:
            raise ValueError("lens_game_observer_target_mode_invalid")
        if any(launcher not in _SUPPORTED_GAME_LAUNCHERS for launcher in self.game_launchers) or len(
            set(self.game_launchers)
        ) != len(self.game_launchers):
            raise ValueError("lens_game_observer_game_launcher_invalid")
        if (self.target_processes or self.game_launchers) and not self.target_id:
            raise ValueError("lens_game_observer_target_id_required")
        if self.target_mode == _TARGET_MODE_PROCESS_ALLOWLIST and self.game_launchers:
            raise ValueError("lens_game_observer_target_mode_invalid")
        if self.target_mode == _TARGET_MODE_FOREGROUND_GAME and self.target_processes:
            raise ValueError("lens_game_observer_target_mode_invalid")
        if self.target_mode == _TARGET_MODE_FOREGROUND_GAME and self.target_id and not self.game_launchers:
            raise ValueError("lens_game_observer_game_launcher_required")
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
        if self.configuration_source not in _CONFIGURATION_SOURCES:
            raise ValueError("lens_game_observer_configuration_source_invalid")
        if self.configuration_fingerprint and not re.fullmatch(r"sha256:[0-9a-f]{64}", self.configuration_fingerprint):
            raise ValueError("lens_game_observer_configuration_fingerprint_invalid")
        if not 0 <= self.environment_override_count <= len(_ENVIRONMENT_OVERRIDE_NAMES):
            raise ValueError("lens_game_observer_environment_override_count_invalid")

    @property
    def target_configured(self) -> bool:
        if not self.enabled or not self.target_id:
            return False
        if self.target_mode == _TARGET_MODE_FOREGROUND_GAME:
            return bool(self.game_launchers)
        return bool(self.target_processes)

    @property
    def model_configured(self) -> bool:
        return self.enabled and self.model_path is not None and bool(self.model_id)

    @classmethod
    def from_environment(cls) -> LensGameObserverConfig:
        runtime_config = _runtime_config_from_environment()
        override_count = sum(1 for name in _ENVIRONMENT_OVERRIDE_NAMES if os.environ.get(name, "").strip())
        target_processes = tuple(runtime_config.get("target_processes") or ())
        target_mode = str(runtime_config.get("target_mode") or _TARGET_MODE_PROCESS_ALLOWLIST)
        game_launchers = tuple(runtime_config.get("game_launchers") or ())
        raw_target_processes = os.environ.get(_TARGET_PROCESSES_ENV, "").strip()
        if raw_target_processes:
            target_processes = _process_names_from_csv(raw_target_processes)
            target_mode = _TARGET_MODE_PROCESS_ALLOWLIST
            game_launchers = ()
        target_id = str(runtime_config.get("target_id") or "")
        raw_target_id = os.environ.get(_TARGET_ID_ENV, "").strip().casefold()
        if raw_target_id:
            target_id = raw_target_id
        elif not target_id and target_processes:
            target_id = _derived_target_id(target_processes[0])
        model_path = runtime_config.get("model_path")
        raw_model_path = os.environ.get(_MODEL_PATH_ENV, "").strip()
        if raw_model_path:
            model_path = _governed_model_path(raw_model_path)
        model_id = str(runtime_config.get("model_id") or "")
        raw_model_id = os.environ.get(_MODEL_ID_ENV, "").strip()
        if raw_model_id:
            model_id = raw_model_id
        elif not model_id and isinstance(model_path, Path):
            model_id = model_path.name
        scenes = tuple(runtime_config.get("scenes") or _DEFAULT_SCENES)
        if os.environ.get(_SCENES_ENV, "").strip():
            scenes = _scenes_from_environment()
        if runtime_config:
            configuration_source = "runtime_config_with_environment_overrides" if override_count else "runtime_config"
        else:
            configuration_source = "environment" if override_count else "unconfigured"
        return cls(
            enabled=bool(runtime_config.get("enabled", True)),
            target_id=target_id,
            target_processes=target_processes,
            target_mode=target_mode,
            game_launchers=game_launchers,
            model_path=model_path,
            model_id=model_id,
            scenes=scenes,
            min_confidence=_environment_float(_MIN_CONFIDENCE_ENV, float(runtime_config.get("min_confidence", 0.35))),
            min_margin=_environment_float(_MIN_MARGIN_ENV, float(runtime_config.get("min_margin", 0.05))),
            inference_interval_seconds=_environment_float(
                _INFERENCE_INTERVAL_ENV,
                float(runtime_config.get("inference_interval_seconds", 2.0)),
            ),
            max_classification_age_seconds=_environment_float(
                _MAX_CLASSIFICATION_AGE_ENV,
                float(runtime_config.get("max_classification_age_seconds", 6.0)),
            ),
            configuration_source=configuration_source,
            configuration_path_label=str(runtime_config.get("configuration_path_label") or ""),
            configuration_fingerprint=str(runtime_config.get("configuration_fingerprint") or ""),
            environment_override_count=override_count,
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
    """Observe a verified foreground game without launch, input, or memory authority."""

    def __init__(
        self,
        config: LensGameObserverConfig,
        *,
        foreground_process: Any = None,
        game_process_verifier: Any = None,
        classifier: GameSceneClassifier | None = None,
        executor: Executor | None = None,
        clock: Any = time.time,
    ) -> None:
        self.config = config
        self._foreground_process = foreground_process or windows_foreground_process_readback
        self._game_process_verifier = game_process_verifier or windows_foreground_game_process_verification
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
        self._pending_process_id = 0
        self._pending_process_name = ""
        self._pending_authority_receipt_id = ""
        self._last_submission_at: float | None = None
        self._last_classification: dict[str, Any] = {}
        self._active_foreground_process_id = 0
        self._active_foreground_process_name = ""

    @classmethod
    def from_environment(cls) -> LensGameObserver:
        try:
            config = LensGameObserverConfig.from_environment()
        except (OSError, TypeError, UnicodeError, ValueError, json.JSONDecodeError):
            config = LensGameObserverConfig(enabled=False, configuration_source="invalid")
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
        if self._last_classification and self._last_classification.get("authority_receipt_id") != receipt_id:
            self._last_classification = {}
        foreground = self._read_foreground_process()
        target_match, game_verification = self._target_match(foreground)
        foreground_process_id = _safe_int(foreground.get("process_id"))
        foreground_process_name = str(foreground.get("process_name") or "")
        configuration_invalid = self._last_classification.get("error") == "lens_game_observer_configuration_invalid"
        if not configuration_invalid:
            if not target_match:
                self._reset_observation_session()
            elif (
                foreground_process_id != self._active_foreground_process_id
                or foreground_process_name.casefold() != self._active_foreground_process_name.casefold()
            ):
                self._reset_observation_session()
                self._active_foreground_process_id = foreground_process_id
                self._active_foreground_process_name = foreground_process_name
        base = self._base_payload(
            source_frame_id=frame_id,
            authority_receipt_id=receipt_id,
            observed_at=now,
            target_match=target_match,
            foreground=foreground,
            game_verification=game_verification,
        )
        if configuration_invalid:
            return _blocked_payload(base, "configuration_invalid", "lens_game_observer_configuration_invalid")
        if not receipt_id:
            return _blocked_payload(base, "authority_missing", "lens_game_observer_authority_receipt_missing")
        if not self.config.target_configured:
            return _blocked_payload(base, "not_configured", "lens_game_observer_target_not_configured")
        if foreground.get("available") is not True:
            return _blocked_payload(base, "foreground_unavailable", "lens_game_observer_foreground_process_unavailable")
        if self.config.target_mode == _TARGET_MODE_FOREGROUND_GAME and game_verification.get("available") is not True:
            return _blocked_payload(
                base,
                "foreground_game_verification_unavailable",
                "lens_game_observer_foreground_game_verification_unavailable",
            )
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
            self._pending_process_id = foreground_process_id
            self._pending_process_name = foreground_process_name
            self._pending_authority_receipt_id = receipt_id
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
                    "max_age_ms": round(self.config.max_classification_age_seconds * 1000.0, 3),
                    "inference_ms": _safe_float(classification.get("inference_ms")),
                    "device": str(classification.get("device") or ""),
                    "backend": str(classification.get("backend") or ""),
                    "score_normalization": str(classification.get("score_normalization") or ""),
                    "target_id": str(classification.get("target_id") or ""),
                    "process_id": _safe_int(classification.get("process_id")),
                    "process_name": str(classification.get("process_name") or ""),
                    "model_id": str(classification.get("model_id") or ""),
                    "scene_id": str(scene.get("id") or ""),
                    "authority_receipt_id": str(classification.get("authority_receipt_id") or ""),
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
                "target_id": self.config.target_id,
                "process_id": self._pending_process_id,
                "process_name": self._pending_process_name,
                "model_id": self.config.model_id,
                "authority_receipt_id": self._pending_authority_receipt_id,
            }
        self._pending = None
        self._pending_source_frame_id = ""
        self._pending_submitted_at = 0.0
        self._pending_process_id = 0
        self._pending_process_name = ""
        self._pending_authority_receipt_id = ""

    def _read_foreground_process(self) -> dict[str, Any]:
        try:
            readback = self._foreground_process()
        except Exception:
            return {"supported": os.name == "nt", "available": False, "reason": "foreground_process_read_failed"}
        return readback if isinstance(readback, dict) else {"supported": False, "available": False}

    def _target_match(self, foreground: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        if foreground.get("available") is not True or not self.config.target_configured:
            return False, {"supported": os.name == "nt", "available": False, "verified": False}
        process_name = str(foreground.get("process_name") or "")
        if self.config.target_mode == _TARGET_MODE_PROCESS_ALLOWLIST:
            matched = bool(
                process_name
                and process_name.casefold() in {target.casefold() for target in self.config.target_processes}
            )
            return matched, {
                "supported": True,
                "available": True,
                "verified": matched,
                "basis": "foreground_process_match",
            }
        process_id = _safe_int(foreground.get("process_id"))
        try:
            readback = self._game_process_verifier(process_id, self.config.game_launchers)
        except Exception:
            readback = {
                "supported": os.name == "nt",
                "available": False,
                "verified": False,
                "reason": "foreground_game_verification_failed",
            }
        if not isinstance(readback, dict):
            readback = {"supported": False, "available": False, "verified": False}
        return readback.get("verified") is True, readback

    def _reset_observation_session(self) -> None:
        if self._pending is not None:
            self._pending.cancel()
        self._pending = None
        self._pending_source_frame_id = ""
        self._pending_submitted_at = 0.0
        self._pending_process_id = 0
        self._pending_process_name = ""
        self._pending_authority_receipt_id = ""
        self._last_submission_at = None
        self._last_classification = {}
        self._active_foreground_process_id = 0
        self._active_foreground_process_name = ""

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
        game_verification: dict[str, Any],
    ) -> dict[str, Any]:
        visibility_basis = str(game_verification.get("basis") or "") if target_match else "not_observed"
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
                "mode": self.config.target_mode,
                "process_names": list(self.config.target_processes),
                "launchers": list(self.config.game_launchers),
                "foreground": target_match,
                "visibility_basis": visibility_basis,
            },
            "foreground": {
                "supported": foreground.get("supported") is True,
                "available": foreground.get("available") is True,
                "target_match": target_match,
                "process_id": _safe_int(foreground.get("process_id")) if target_match else 0,
                "process_name": str(foreground.get("process_name") or "") if target_match else "",
                "window_id": _safe_int(foreground.get("window_id")) if target_match else 0,
                "window_title_included": False,
                "game_verified": (
                    game_verification.get("verified") is True
                    if self.config.target_mode == _TARGET_MODE_FOREGROUND_GAME
                    else False
                ),
                "verification_basis": visibility_basis if target_match else "",
            },
            "scene": {},
            "classification": {},
            "configuration": {
                "source": self.config.configuration_source,
                "loaded": bool(self.config.configuration_fingerprint),
                "enabled": self.config.enabled,
                "path": self.config.configuration_path_label,
                "fingerprint": self.config.configuration_fingerprint,
                "environment_override_count": self.config.environment_override_count,
            },
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
                "foreground_game_required": True,
                "local_process_launch_authority": False,
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
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        window = user32.GetForegroundWindow()
        if not window:
            return {"supported": True, "available": False, "reason": "foreground_window_missing"}
        process_id = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
        if not process_id.value:
            return {"supported": True, "available": False, "reason": "foreground_process_missing"}
        process_path = _windows_process_image_path(int(process_id.value))
        if process_path is None:
            return {"supported": True, "available": False, "reason": "foreground_process_query_failed"}
        process_name = process_path.name
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


def windows_foreground_game_process_verification(
    process_id: int,
    game_launchers: tuple[str, ...],
) -> dict[str, Any]:
    """Verify an existing process locally without returning its executable path."""

    if os.name != "nt":
        return {
            "supported": False,
            "available": False,
            "verified": False,
            "reason": "foreground_game_platform_unsupported",
        }
    process_path = _windows_process_image_path(process_id)
    if process_path is None:
        return {
            "supported": True,
            "available": False,
            "verified": False,
            "reason": "foreground_game_process_path_unavailable",
        }
    roots_available = False
    for launcher in game_launchers:
        roots = _windows_game_library_roots(launcher)
        roots_available = roots_available or bool(roots)
        if any(_path_is_within(process_path, root) for root in roots):
            return {
                "supported": True,
                "available": True,
                "verified": True,
                "basis": "local_launcher_library_path",
                "launcher_id": launcher,
            }
    if not roots_available:
        return {
            "supported": True,
            "available": False,
            "verified": False,
            "reason": "foreground_game_library_roots_unavailable",
        }
    return {
        "supported": True,
        "available": True,
        "verified": False,
        "reason": "foreground_process_outside_game_library",
    }


def _windows_process_image_path(process_id: int) -> Path | None:
    if os.name != "nt" or process_id <= 0:
        return None
    try:
        from ctypes import wintypes

        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None:
            return None
        kernel32 = win_dll("kernel32", use_last_error=True)
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
        process = kernel32.OpenProcess(0x1000, False, process_id)
        if not process:
            return None
        try:
            capacity = wintypes.DWORD(32_768)
            buffer = ctypes.create_unicode_buffer(capacity.value)
            if not kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(capacity)):
                return None
            return Path(buffer.value) if buffer.value else None
        finally:
            kernel32.CloseHandle(process)
    except Exception:
        return None


def _windows_game_library_roots(launcher: str) -> tuple[Path, ...]:
    if os.name != "nt" or launcher != "steam":
        return ()
    try:
        import winreg
    except ImportError:
        return ()
    hkey_current_user = getattr(winreg, "HKEY_CURRENT_USER", None)
    hkey_local_machine = getattr(winreg, "HKEY_LOCAL_MACHINE", None)
    open_key = getattr(winreg, "OpenKey", None)
    query_value = getattr(winreg, "QueryValueEx", None)
    if hkey_current_user is None or hkey_local_machine is None or open_key is None or query_value is None:
        return ()
    steam_roots: list[Path] = []
    registry_values = (
        (hkey_current_user, r"Software\Valve\Steam", "SteamPath"),
        (hkey_local_machine, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (hkey_local_machine, r"SOFTWARE\Valve\Steam", "InstallPath"),
    )
    for hive, key_path, value_name in registry_values:
        try:
            with open_key(hive, key_path) as key:
                value, _value_type = query_value(key, value_name)
        except OSError:
            continue
        if isinstance(value, str) and value.strip():
            steam_roots.append(Path(value.strip()))

    library_roots = list(steam_roots)
    for steam_root in tuple(steam_roots):
        library_config = steam_root / "steamapps" / "libraryfolders.vdf"
        try:
            raw = library_config.read_bytes()
        except OSError:
            continue
        if len(raw) > _STEAM_LIBRARY_CONFIG_MAX_BYTES:
            continue
        text = raw.decode("utf-8-sig", errors="replace")
        for match in _STEAM_LIBRARY_PATH_PATTERN.finditer(text):
            library_path = match.group(1).replace(r"\\", "\\").replace(r"\"", '"').strip()
            if library_path:
                library_roots.append(Path(library_path))

    game_roots: list[Path] = []
    seen: set[str] = set()
    for library_root in library_roots:
        game_root = library_root / "steamapps" / "common"
        try:
            normalized = str(game_root.resolve(strict=False)).casefold()
        except OSError:
            continue
        if normalized in seen or not game_root.is_dir():
            continue
        seen.add(normalized)
        game_roots.append(game_root)
    return tuple(game_roots)


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (OSError, ValueError):
        return False
    return True


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


def _runtime_config_from_environment() -> dict[str, Any]:
    raw_path = os.environ.get(_CONFIG_PATH_ENV, "").strip()
    if not raw_path:
        return {}
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ValueError("lens_game_observer_config_path_must_be_absolute")
    try:
        resolved_path = path.resolve(strict=True)
        raw_payload = resolved_path.read_bytes()
    except OSError as exc:
        raise ValueError("lens_game_observer_runtime_config_unreadable") from exc
    if len(raw_payload) > _CONFIG_MAX_BYTES:
        raise ValueError("lens_game_observer_runtime_config_too_large")
    try:
        payload = json.loads(raw_payload.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("lens_game_observer_runtime_config_invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("lens_game_observer_runtime_config_invalid")
    _require_exact_keys(
        payload,
        {"kind", "version", "enabled", "target", "model", "scenes", "thresholds", "governance"},
        "lens_game_observer_runtime_config_invalid",
    )
    if payload.get("kind") != LENS_GAME_OBSERVER_CONFIG_KIND:
        raise ValueError("lens_game_observer_runtime_config_kind_invalid")
    version = payload.get("version")
    if isinstance(version, bool) or version not in {
        _LEGACY_GAME_OBSERVER_CONFIG_VERSION,
        LENS_GAME_OBSERVER_CONFIG_VERSION,
    }:
        raise ValueError("lens_game_observer_runtime_config_version_invalid")
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("lens_game_observer_enabled_invalid")

    target = _required_json_object(payload.get("target"), "lens_game_observer_target_invalid")
    if version == _LEGACY_GAME_OBSERVER_CONFIG_VERSION:
        _require_exact_keys(target, {"id", "process_names"}, "lens_game_observer_target_invalid")
        target_mode = _TARGET_MODE_PROCESS_ALLOWLIST
        game_launchers: tuple[str, ...] = ()
    else:
        _require_exact_keys(
            target,
            {"id", "mode", "process_names", "launchers"},
            "lens_game_observer_target_invalid",
        )
        target_mode = _required_config_string(
            target.get("mode"),
            "lens_game_observer_target_mode_invalid",
        ).casefold()
        raw_launchers = target.get("launchers")
        if not isinstance(raw_launchers, list) or any(
            not isinstance(item, str) or not item.strip() for item in raw_launchers
        ):
            raise ValueError("lens_game_observer_game_launcher_invalid")
        game_launchers = tuple(dict.fromkeys(item.strip().casefold() for item in raw_launchers))
    target_id = _required_config_string(target.get("id"), "lens_game_observer_target_id_invalid").casefold()
    raw_processes = target.get("process_names")
    if not isinstance(raw_processes, list) or any(
        not isinstance(item, str) or not item.strip() for item in raw_processes
    ):
        raise ValueError("lens_game_observer_target_process_invalid")
    if target_mode == _TARGET_MODE_PROCESS_ALLOWLIST and not raw_processes:
        raise ValueError("lens_game_observer_target_process_invalid")
    target_processes = tuple(dict.fromkeys(item.strip() for item in raw_processes))

    model = _required_json_object(payload.get("model"), "lens_game_observer_model_invalid")
    _require_exact_keys(
        model,
        {"id", "data_relative_path", "remote_inference"},
        "lens_game_observer_model_invalid",
    )
    if model.get("remote_inference") is not False:
        raise ValueError("lens_game_observer_remote_inference_forbidden")
    model_id = _required_config_string(model.get("id"), "lens_game_observer_model_id_invalid")
    model_path = _data_relative_model_path(model.get("data_relative_path"))

    raw_scenes = _required_json_object(payload.get("scenes"), "lens_game_observer_scenes_invalid")
    if any(not isinstance(scene_id, str) or not isinstance(prompt, str) for scene_id, prompt in raw_scenes.items()):
        raise ValueError("lens_game_observer_scenes_invalid")
    scenes = tuple(GameSceneDefinition(scene_id, prompt) for scene_id, prompt in raw_scenes.items())

    thresholds = _required_json_object(payload.get("thresholds"), "lens_game_observer_thresholds_invalid")
    _require_exact_keys(
        thresholds,
        {
            "min_confidence",
            "min_margin",
            "inference_interval_seconds",
            "max_classification_age_seconds",
        },
        "lens_game_observer_thresholds_invalid",
    )

    governance = _required_json_object(payload.get("governance"), "lens_game_observer_governance_invalid")
    expected_governance = (
        _LEGACY_RUNTIME_GOVERNANCE if version == _LEGACY_GAME_OBSERVER_CONFIG_VERSION else _EXPECTED_RUNTIME_GOVERNANCE
    )
    if governance != expected_governance:
        raise ValueError("lens_game_observer_governance_invalid")

    return {
        "enabled": enabled,
        "target_id": target_id,
        "target_processes": target_processes,
        "target_mode": target_mode,
        "game_launchers": game_launchers,
        "model_path": model_path,
        "model_id": model_id,
        "scenes": scenes,
        "min_confidence": _config_float(thresholds.get("min_confidence")),
        "min_margin": _config_float(thresholds.get("min_margin")),
        "inference_interval_seconds": _config_float(thresholds.get("inference_interval_seconds")),
        "max_classification_age_seconds": _config_float(thresholds.get("max_classification_age_seconds")),
        "configuration_path_label": _configuration_path_label(resolved_path),
        "configuration_fingerprint": f"sha256:{hashlib.sha256(raw_payload).hexdigest()}",
    }


def _required_json_object(value: Any, error_code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(error_code)
    return value


def _require_exact_keys(value: dict[str, Any], keys: set[str], error_code: str) -> None:
    if set(value) != keys:
        raise ValueError(error_code)


def _required_config_string(value: Any, error_code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(error_code)
    return value.strip()


def _config_float(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("lens_game_observer_thresholds_invalid")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("lens_game_observer_thresholds_invalid") from exc
    if not math.isfinite(parsed):
        raise ValueError("lens_game_observer_thresholds_invalid")
    return parsed


def _data_relative_model_path(value: Any) -> Path:
    raw_path = _required_config_string(value, "lens_game_observer_model_path_invalid")
    relative_path = Path(raw_path)
    if relative_path.is_absolute() or relative_path.drive or ".." in relative_path.parts:
        raise ValueError("lens_game_observer_model_path_outside_data")
    return _governed_model_path(raw_path)


def _governed_model_path(value: Any) -> Path:
    raw_path = _required_config_string(value, "lens_game_observer_model_path_invalid")
    data_root = data_dir().resolve()
    candidate = Path(raw_path).expanduser()
    resolved_path = (candidate if candidate.is_absolute() else data_root / candidate).resolve()
    try:
        resolved_path.relative_to(data_root)
    except ValueError as exc:
        raise ValueError("lens_game_observer_model_path_outside_data") from exc
    if resolved_path == data_root:
        raise ValueError("lens_game_observer_model_path_outside_data")
    return resolved_path


def _configuration_path_label(path: Path) -> str:
    try:
        return path.relative_to(repo_root().resolve()).as_posix()
    except ValueError:
        return path.name


def _process_names_from_csv(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(process_name.strip() for process_name in value.split(",") if process_name.strip()))


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
