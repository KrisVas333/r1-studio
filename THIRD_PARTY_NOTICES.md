# Third-party notices

Our own code in this repository is MIT ([LICENSE](LICENSE)). The parts below come from other projects and keep their own licences. Checked 2026-11-07.

| Path | What | Licence | How we checked |
|---|---|---|---|
| `studio/web/vendor/three.module.js` | three.js r160 | MIT, © 2010-2023 Three.js Authors | `SPDX-License-Identifier: MIT` header in the file |
| `studio/web/vendor/OrbitControls.js`, `STLLoader.js` | three.js examples (addons) | MIT, © Three.js Authors | part of the three.js repo; the files carry no header |
| `studio/web/vendor/blockly_compressed.js`, `blocks_compressed.js`, `en.js`, `lt.js` | Blockly 11.2.1 (Google / Raspberry Pi Foundation) and its message files | Apache-2.0 | version string `11.2.1` in the file; `lt.js` downloaded from `unpkg.com/blockly@11.2.1/msg/lt.js`. The minified files carry no licence header, so the licence is the upstream project's |
| `studio/web/vendor/vision_bundle.mjs`, `vendor/wasm/*` | MediaPipe Tasks Vision (Google) | Apache-2.0 | upstream project licence; the bundled files carry no header |
| `studio/web/vendor/gesture_recognizer.task`, `pose_landmarker_lite.task`, `efficientdet_lite0.tflite` | MediaPipe hand gesture, pose landmarker (lite) and EfficientDet-Lite0 object models | Apache-2.0 (per the MediaPipe model cards) | ⚠️ the model files carry no licence text; licence taken from the upstream model pages |
| `studio/web/model/r1.json`, `r1.bin` | 3D meshes and joint data exported by `studio/tools/export_model.py` from Unitree's R1 MuJoCo model (`unitree_mujoco/unitree_robots/r1`) | BSD-3-Clause, © 2016-2024 HangZhou YuShu Technology Co., Ltd. ("Unitree Robotics") | `LICENSE` file of `unitreerobotics/unitree_mujoco` |
| `r1ctl/cpp/*.cpp` | Our programs. They link against and follow the examples of Unitree's `unitree_sdk2` (not included here) | Ours: MIT. `unitree_sdk2`: BSD-3-Clause, © 2016-2023 Unitree Robotics | `LICENSE` file of `unitreerobotics/unitree_sdk2` |
| `studio/sounds/Bach Prelude.wav` | Bach, Prelude in C BWV 846, performed by Kimiko Ishizaka, converted to 16 kHz mono | CC0 | Wikimedia Commons file metadata, read 2026-10-17 |
| `studio/sounds/Vivaldi Spring.wav` | Vivaldi, Spring RV 269 I, Modena Chamber Orchestra (Musopen), converted to 16 kHz mono | Public domain (owner dedication) | Wikimedia Commons file metadata, read 2026-10-17 |

## Not in this repository
- **Unitree SDKs** (`unitree_sdk2`, `unitree_sdk2_python`), **BrainCo hand service**, **CycloneDDS**, **MuJoCo** and the full `unitree_mujoco` checkout: clone them yourself (commands in [README.md](README.md)). They have their own licences.
- **Sound effects and music beds** generated with ElevenLabs on a private plan are not published. `studio/tools/make_sounds.py` rebuilds them from a local kit. Without them the Remote's Sound tab shows only the two recordings above.
- **Voice lines** (robot speech in Kris's cloned voice) are generated locally into `r1ctl/cache/` and are not published.

## Apache-2.0 and BSD-3-Clause
Apache-2.0 full text: https://www.apache.org/licenses/LICENSE-2.0
BSD-3-Clause requires keeping the copyright notice above with any redistribution of the Unitree-derived model files.
