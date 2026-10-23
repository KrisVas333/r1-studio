# r1-studio — Unitree R1 EDU Pro + BrainCo Revo2 control kit (Robotikos Akademija)

Browser studio (blocks · 45-move deck · AI host · vision · telepresence) + terminal controller (`r1ctl`) + simulator preview, for a Unitree R1 EDU Pro.
**Status 2026-10-23:** ✅ simulator + browser tested · ⚠️ not yet run on the real robot.

| Folder | What |
|---|---|
| `R1-SETUP.md` | Step-by-step: cable → SSH → deploy → first moves |
| `studio/` | R1 Studio web app + server (`studio/README.md`) |
| `r1ctl/` | Terminal controller + C++ executors (`r1_arm`, `r1_hand`, `r1_say`) + library (dances, hands, arm moves, personas, vision skills) |
| `sim/` | MuJoCo preview/checker on Unitree's R1 model (`~/r1/preview <dance>`) |
| `research/` | GitHub sweep · G1→R1 + simulators · forums/events · social robots |

## Third-party (not in this repo) — clone into the repo root
```bash
git clone --depth 1 https://github.com/unitreerobotics/unitree_sdk2
git clone --depth 1 https://github.com/unitreerobotics/brainco_hand_service
git clone --depth 1 https://github.com/Mmaotttt/unitree_sdk2-modified   # fix: delete the stray "lococlient" on line 1 of example/r1/high_level/r1_loco_client_example.cpp
git clone --depth 1 https://github.com/dshifrin5/unitree-r1-brainco-hands  # retrofit notes only
cd sim && git clone --depth 1 --filter=blob:none --sparse https://github.com/unitreerobotics/unitree_mujoco && (cd unitree_mujoco && git sparse-checkout set unitree_robots/r1)
python3 -m venv .venv && .venv/bin/pip install mujoco pyyaml numpy "imageio[ffmpeg]"
```
`brainco_hand_service/test/hand_cli.cpp` (+ one CMake line) is ours: copy it in after cloning.

## Licenses
`studio/web/model/r1.*` is exported from Unitree's `unitree_mujoco` R1 model. Vendored libraries: Blockly (Apache-2.0), three.js (MIT), MediaPipe tasks-vision + models (Apache-2.0).

Safety: dry-run by default, GO prompt for live, Stop/Space everywhere, speed caps, gantry for first runs, no blades, kids behind 2 m.
