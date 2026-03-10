import * as THREE from "three";
import { FrancisOrbEngineOptions } from "../core/types";
import { OrbComposer } from "./OrbComposer";
import { OrbScene } from "./OrbScene";
import { OrbStateController, OrbExternalSignals } from "../control/OrbStateController";
import { OrbTransitionController } from "../control/OrbTransitionController";

export class FrancisOrbEngine {
  private readonly container: HTMLElement;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly orbScene: OrbScene;
  private readonly clock = new THREE.Clock();
  private readonly stateController = new OrbStateController();
  private readonly transitionController = new OrbTransitionController();
  private readonly composer?: OrbComposer;

  private signals: OrbExternalSignals = { state: "idle" };
  private rafId: number | null = null;
  private disposed = false;

  constructor(options: FrancisOrbEngineOptions) {
    this.container = options.container;

    const width = Math.max(1, this.container.clientWidth || 1);
    const height = Math.max(1, this.container.clientHeight || 1);

    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: !!options.transparentBackground,
      powerPreference: "high-performance",
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, options.pixelRatio ?? 2));
    this.renderer.setSize(width, height);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.setClearColor(0x000000, options.transparentBackground ? 0 : 1);
    this.renderer.domElement.style.background = "transparent";
    this.container.appendChild(this.renderer.domElement);

    this.orbScene = new OrbScene({
      width,
      height,
      seed: options.seed ?? 7,
      enableBeam: options.enableBeam ?? true,
      background: options.background,
      transparentBackground: options.transparentBackground,
    });

    if (options.usePostFX !== false) {
      this.composer = new OrbComposer(
        this.renderer,
        this.orbScene.scene,
        this.orbScene.camera,
        width,
        height,
      );
    }

    window.addEventListener("resize", this.onResize);
  }

  setSignals(next: OrbExternalSignals): void {
    this.signals = next;
    this.transitionController.setState(next.state);
  }

  start(): void {
    if (this.rafId !== null || this.disposed) {
      return;
    }
    this.clock.start();
    this.tick();
  }

  stop(): void {
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.stop();
    window.removeEventListener("resize", this.onResize);
    this.orbScene.dispose();
    this.renderer.dispose();
    if (this.renderer.domElement.parentElement === this.container) {
      this.container.removeChild(this.renderer.domElement);
    }
  }

  private tick = (): void => {
    if (this.disposed) {
      return;
    }

    const dt = this.clock.getDelta();
    const elapsed = this.clock.getElapsedTime();
    const frame = this.stateController.buildFrame(this.signals, dt, elapsed);
    const profile = this.transitionController.update();

    this.orbScene.update(frame, profile);

    if (this.composer) {
      this.composer.render();
    } else {
      this.renderer.render(this.orbScene.scene, this.orbScene.camera);
    }

    this.rafId = requestAnimationFrame(this.tick);
  };

  private onResize = (): void => {
    const width = Math.max(1, this.container.clientWidth || 1);
    const height = Math.max(1, this.container.clientHeight || 1);

    this.orbScene.setSize(width, height);
    this.renderer.setSize(width, height);
    this.composer?.setSize(width, height);
  };
}
