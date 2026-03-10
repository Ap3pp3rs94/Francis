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
    this.root.add(this.filaments.group);
    this.root.add(this.particles.points);
    this.root.add(this.core.mesh);

    if (options.enableBeam) {
      this.beam = new OrbTargetBeam();
      this.root.add(this.beam.mesh);
    }

    this.root.rotation.x = 0.18;
    this.root.rotation.y = -0.35;
    this.scene.add(this.root);
    this.buildLighting();
  }

  update(frame: OrbSignalFrame, profile: OrbStateProfile): void {
    this.core.update(frame, profile);
    this.shell.update(frame, profile);
    this.aura.update(frame, profile);
    this.filaments.update(frame, profile);
    this.particles.update(frame, profile);
    this.beam?.update(frame, profile);
    this.animateRoot(frame);
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

  private buildLighting(): void {
    const ambient = new THREE.AmbientLight(0xc8e4ff, 0.5);
    const point = new THREE.PointLight(0xe8f7ff, 3.2, 18, 2);
    point.position.set(0, 0, 3.2);

    this.scene.add(ambient);
    this.scene.add(point);
  }

  private animateRoot(frame: OrbSignalFrame): void {
    this.root.position.y = Math.sin(frame.elapsed * ORB_CONFIG.idleFloatSpeed) * ORB_CONFIG.idleFloatAmp;

    const target = frame.attentionTarget ?? new THREE.Vector3(0, 0, 0);
    const yaw = Math.atan2(target.x, 5.0);
    const pitch = Math.atan2(target.y, 6.0);

    this.root.rotation.y = lerp(this.root.rotation.y, -0.35 + yaw, 0.03);
    this.root.rotation.x = lerp(this.root.rotation.x, 0.18 - pitch, 0.03);
  }
}
