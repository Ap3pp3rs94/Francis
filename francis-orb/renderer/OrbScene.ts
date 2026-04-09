import * as THREE from "three";
import { ORB_CONFIG } from "../core/config";
import { lerp } from "../core/math";
import { OrbSignalFrame, OrbStateProfile } from "../core/types";
import { OrbAura } from "./OrbAura";
import { OrbCore } from "./OrbCore";
import { OrbFilaments } from "./OrbFilaments";
import { OrbParticles } from "./OrbParticles";
import { OrbShell } from "./OrbShell";
import { OrbTargetBeam } from "./OrbTargetBeam";

export interface OrbSceneOptions {
  width: number;
  height: number;
  seed: number;
  enableBeam: boolean;
  background?: number;
  transparentBackground?: boolean;
}

export class OrbScene {
  public readonly scene: THREE.Scene;
  public readonly camera: THREE.PerspectiveCamera;
  public readonly root = new THREE.Group();
  public readonly core: OrbCore;
  public readonly shell: OrbShell;
  public readonly aura: OrbAura;
  public readonly filaments: OrbFilaments;
  public readonly particles: OrbParticles;
  public readonly beam?: OrbTargetBeam;

  constructor(options: OrbSceneOptions) {
    this.scene = new THREE.Scene();
    if (!options.transparentBackground) {
      this.scene.background = new THREE.Color(options.background ?? 0x000000);
    }

    this.camera = new THREE.PerspectiveCamera(
      ORB_CONFIG.camera.fov,
      options.width / options.height,
      ORB_CONFIG.camera.near,
      ORB_CONFIG.camera.far,
    );
    this.camera.position.set(0, 0, ORB_CONFIG.camera.z);

    this.core = new OrbCore(ORB_CONFIG.coreRadius);
    this.shell = new OrbShell(ORB_CONFIG.shellRadius);
    this.aura = new OrbAura(ORB_CONFIG.auraRadius);
    this.filaments = new OrbFilaments(ORB_CONFIG.filamentCount, ORB_CONFIG.filamentSegments, options.seed);
    this.particles = new OrbParticles(ORB_CONFIG.particleCount, options.seed + 99);

    this.root.add(this.aura.sprite);
    this.root.add(this.shell.mesh);
    this.root.add(this.core.mesh);
    this.root.add(this.filaments.group);
    if (ORB_CONFIG.particleCount > 0) {
      this.root.add(this.particles.points);
    }

    if (options.enableBeam) {
      this.beam = new OrbTargetBeam();
      this.root.add(this.beam.mesh);
    }

    this.root.scale.setScalar(1.32);
    this.root.rotation.x = 0.05;
    this.root.rotation.y = -0.14;
    this.scene.add(this.root);
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    this.core.update(frame, profile);
    this.shell.update(frame, profile);
    this.aura.update(frame, profile);
    this.filaments.update(frame, profile);
    this.particles.update(frame, profile);
    this.beam?.update(frame, profile);
    this.animateRoot(frame, profile);
  }

  setSize(width: number, height: number): void {
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  dispose(): void {
    this.core.dispose();
    this.shell.dispose();
    this.aura.dispose();
    this.filaments.dispose();
    this.particles.dispose();
    this.beam?.dispose();
  }

  private animateRoot(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    const attentionStrength = Math.max(0, Math.min(1, Number(frame.attentionStrength ?? frame.confidence ?? 0.32)));
    const attentionLock = Math.max(0, Math.min(1, Number(frame.attentionLock ?? 0.18)));
    const attentionUncertainty = Math.max(0, Math.min(1, Number(frame.attentionUncertainty ?? 0.14)));
    const directionalBias = Math.max(0, Number(profile.directionalBias ?? 0));
    const rootStillness = Math.max(0.22, Math.min(1, Number(profile.rootStillness ?? 0.62)));
    const floatAmplitude =
      ORB_CONFIG.idleFloatAmp *
      Math.max(
        0.12,
        (1 - rootStillness * 0.72) *
          (1 - attentionStrength * 0.36 - attentionLock * 0.24 + attentionUncertainty * 0.18),
      );
    this.root.position.y = Math.sin(frame.elapsed * ORB_CONFIG.idleFloatSpeed) * floatAmplitude;
    this.root.position.x = Math.cos(frame.elapsed * (ORB_CONFIG.idleFloatSpeed * 0.72)) * floatAmplitude * 0.32;

    const target = frame.attentionTarget ?? new THREE.Vector3(0, 0, 0);
    const yaw = Math.atan2(target.x, 5.0);
    const pitch = Math.atan2(target.y, 6.0);
    const trackingLerp = Math.max(
      0.02,
      Math.min(
        0.1,
        0.022 +
          attentionStrength * 0.024 +
          attentionLock * 0.034 +
          directionalBias * 0.02 -
          rootStillness * 0.01 -
          attentionUncertainty * 0.012,
      ),
    );

    this.root.rotation.y = lerp(this.root.rotation.y, -0.12 + yaw, trackingLerp);
    this.root.rotation.x = lerp(this.root.rotation.x, 0.05 - pitch, trackingLerp);
    this.root.rotation.z = lerp(
      this.root.rotation.z,
      Math.sin(frame.elapsed * 0.26) * (0.01 + (1 - rootStillness) * 0.02) +
        attentionStrength * (0.004 + directionalBias * 0.01) -
        attentionLock * 0.008,
      Math.max(0.014, trackingLerp * 0.7),
    );
  }
}
