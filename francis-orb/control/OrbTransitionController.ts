import { ORB_CONFIG } from "../core/config";
import { ORB_STATE_PROFILES } from "../core/state-profiles";
import { lerp } from "../core/math";
import { OrbState, OrbStateProfile } from "../core/types";
import { normalizeOrbState } from "../core/state-semantics";

export class OrbTransitionController {
  private readonly currentProfile: OrbStateProfile = { ...ORB_STATE_PROFILES.idle_anchored };
  private targetProfile: OrbStateProfile = { ...ORB_STATE_PROFILES.idle_anchored };

  setState(state: OrbState): void {
    this.targetProfile = { ...ORB_STATE_PROFILES[normalizeOrbState(state)] };
  }

  update(): OrbStateProfile {
    const keys = Object.keys(this.currentProfile) as (keyof OrbStateProfile)[];
    for (const key of keys) {
      this.currentProfile[key] = lerp(
        this.currentProfile[key],
        this.targetProfile[key],
        ORB_CONFIG.profileLerp,
      );
    }
    return this.currentProfile;
  }

  get value(): OrbStateProfile {
    return this.currentProfile;
  }
}
