import * as THREE from "three";
import { createFrancisOrb } from "./createFrancisOrb";

const mount = document.getElementById("orb-root");
if (!mount) {
  throw new Error("Missing orb-root");
}

const app = createFrancisOrb(mount, {
  transparentBackground: false,
  background: 0x000000,
});

const states = ["idle", "listening", "thinking", "speaking", "acting"] as const;
let index = 0;

setInterval(() => {
  const state = states[index % states.length];

  switch (state) {
    case "idle":
      app.setIdle();
      break;
    case "listening":
      app.setListening();
      break;
    case "thinking":
      app.setThinking(0.84);
      break;
    case "speaking":
      app.setSpeaking(Math.random());
      break;
    case "acting":
      app.setActing(new THREE.Vector3(2.4, 1.2, 0), 1);
      break;
  }

  index += 1;
}, 3000);

setInterval(() => {
  app.setSpeaking(Math.random());
}, 120);
