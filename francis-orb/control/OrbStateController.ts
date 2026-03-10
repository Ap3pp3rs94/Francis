import * as THREE from "three";
import { OrbState, OrbSignalFrame } from "../core/types";
import { OrbActionController } from "./OrbActionController";
import { OrbSpeechController } from "./OrbSpeechController";
import { OrbAttentionController } from "./OrbAttentionController";

export interface OrbExternalSignals {
  state: OrbState;
  speakingAmplitude?: number;
  attentionTarget?: THREE.Vector3 | null;
  actionTarget?: THREE.Vector3 | null;
  actionStrength?: number;
  confidence?: number;
  interjectionIntent?: boolean;
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

    return {
      state: signals.state,
      speakingAmplitude: this.speech.update(signals.speakingAmplitude ?? 0),
      attentionTarget: this.attention.update(signals.attentionTarget),
      actionTarget: action.target,
      actionStrength: action.strength,
      confidence: signals.confidence,
      interjectionIntent: signals.interjectionIntent ?? false,
      dt,
      elapsed,
    };
  }
}
