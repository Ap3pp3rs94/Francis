import * as THREE from "three";
import { OrbAttentionState, OrbState, OrbSignalFrame, OrbVisualTelemetry } from "../core/types";
import { OrbActionController } from "./OrbActionController";
import { OrbSpeechController } from "./OrbSpeechController";
import { OrbAttentionController } from "./OrbAttentionController";

export interface OrbExternalSignals {
  state: OrbState;
  visual?: OrbVisualTelemetry | null;
  speakingAmplitude?: number;
  attentionTarget?: THREE.Vector3 | null;
  attentionState?: OrbAttentionState | null;
  attentionStrength?: number;
  attentionLock?: number;
  attentionUncertainty?: number;
  actionTarget?: THREE.Vector3 | null;
  actionStrength?: number;
  confidence?: number;
  interjectionIntent?: boolean;
}

function defaultAttentionStateForOrbState(state: OrbState): OrbAttentionState {
  if (state === "target_lock" || state === "commit_move" || state === "hover_ready" || state === "click_act" || state === "drag_act" || state === "type_hold") {
    return "target_lock";
  }
  if (state === "investigate" || state === "attentive") {
    return "investigate";
  }
  if (state === "blocked" || state === "interrupted") {
    return "reassess";
  }
  return "idle";
}

export class OrbStateController {
  private readonly speech = new OrbSpeechController();
  private readonly attention = new OrbAttentionController();
  private readonly action = new OrbActionController();

  buildFrame(
    signals: OrbExternalSignals,
    dt: number,
    elapsed: number,
  ): OrbSignalFrame {
    const action = this.action.update(signals.actionTarget, signals.actionStrength ?? 0);
    const attentionState = signals.attentionState ?? defaultAttentionStateForOrbState(signals.state);
    const attentionStrength = Math.max(0, Math.min(1, Number(signals.attentionStrength ?? signals.confidence ?? 0.36)));
    const attentionLock = Math.max(
      0,
      Math.min(
        1,
        Number(
          signals.attentionLock
          ?? (attentionState === "target_lock" ? 0.82 : attentionState === "investigate" ? 0.42 : 0.16),
        ),
      ),
    );
    const attentionUncertainty = Math.max(
      0,
      Math.min(
        1,
        Number(
          signals.attentionUncertainty
          ?? (attentionState === "reassess" ? 0.72 : attentionState === "investigate" ? 0.34 : 0.12),
        ),
      ),
    );

    return {
      state: signals.state,
      speakingAmplitude: this.speech.update(signals.speakingAmplitude ?? 0),
      visualCoreBrightness: Number(signals.visual?.coreBrightness ?? 0.84),
      visualHaloStrength: Number(signals.visual?.haloStrength ?? 0.9),
      visualRingDensity: Number(signals.visual?.ringDensity ?? 0.92),
      visualRingTightness: Number(signals.visual?.ringTightness ?? 0.82),
      visualOrbitSpeed: Number(signals.visual?.orbitSpeed ?? 0.74),
      attentionTarget: this.attention.update({
        target: signals.attentionTarget,
        state: attentionState,
        strength: attentionStrength,
        lock: attentionLock,
        uncertainty: attentionUncertainty,
        elapsed,
      }),
      attentionState,
      attentionStrength,
      attentionLock,
      attentionUncertainty,
      actionTarget: action.target,
      actionStrength: action.strength,
      confidence: signals.confidence,
      interjectionIntent: signals.interjectionIntent ?? false,
      dt,
      elapsed,
    };
  }
}
