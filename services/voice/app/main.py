from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.voice.app.operator import build_live_operator_briefing, preview_operator_command
from services.voice.app.stt import capability_status as stt_capability_status
from services.voice.app.stt import preview_transcription
from services.voice.app.tts import build_briefing, capability_status as tts_capability_status
from services.voice.app.wakeword import capability_status as wakeword_capability_status

SERVICE_VERSION = "0.2.0"


class TranscriptPreviewRequest(BaseModel):
    utterance: str = Field(min_length=1, max_length=240)
    locale: str = Field(default="en-US")


class BriefingRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=240)
    mode: Literal["observe", "assist", "pilot", "away"] = "assist"
    include_receipts: bool = True


class VoiceCommandPreviewRequest(BaseModel):
    utterance: str = Field(min_length=1, max_length=240)
    locale: str = Field(default="en-US")
    max_actions: int = Field(default=5, ge=1, le=8)


def _build_app() -> FastAPI:
    app = FastAPI(title="Francis Voice", version=SERVICE_VERSION)

    @app.get("/")
    def root() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "voice",
            "version": app.version,
            "surfaces": [
                "health",
                "voice.status",
                "voice.briefing.live",
                "voice.command.preview",
                "stt.preview",
                "tts.briefing",
                "wakeword.status",
            ],
        }

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "service": "voice", "version": app.version}

    @app.get("/voice/status")
    def voice_status() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "voice",
            "version": app.version,
            "charter": {
                "voice": "calm, grounded, specific",
                "receipts_required": True,
                "control_transfer": "explicit only",
            },
            "modules": {
                "stt": stt_capability_status(),
                "tts": tts_capability_status(),
                "wakeword": wakeword_capability_status(),
            },
            "surfaces": {
                "briefing": ["/voice/tts/briefing", "/voice/briefing/live"],
                "command_preview": "/voice/command/preview",
            },
        }

    @app.get("/voice/wakeword/status")
    def wakeword_status() -> dict[str, object]:
        return {"status": "ok", "module": wakeword_capability_status()}

    @app.post("/voice/stt/preview")
    def stt_preview(payload: TranscriptPreviewRequest) -> dict[str, object]:
        try:
            preview = preview_transcription(payload.utterance, locale=payload.locale)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "preview": preview}

    @app.get("/voice/briefing/live")
    def live_briefing(mode: Literal["observe", "assist", "pilot", "away"] = "assist", max_actions: int = 3) -> dict[str, object]:
        try:
            return build_live_operator_briefing(mode=mode, max_actions=max_actions)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/voice/command/preview")
    def command_preview(payload: VoiceCommandPreviewRequest) -> dict[str, object]:
        try:
            return preview_operator_command(
                utterance=payload.utterance,
                locale=payload.locale,
                max_actions=payload.max_actions,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/voice/tts/briefing")
    def tts_briefing(payload: BriefingRequest) -> dict[str, object]:
        try:
            briefing = build_briefing(
                objective=payload.objective,
                mode=payload.mode,
                include_receipts=payload.include_receipts,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "mode": payload.mode, "briefing": briefing}

    return app


app = _build_app()
