# GitHub sweep: Unitree R1 EDU Pro + BrainCo Revo2 Pro (2026-10-23)

Status: COMPLETE 2026-10-23 (GitHub only; forums/YouTube = other scout). Raw logs below; synthesis first in this block.

## TL;DR top 10 (verdict first)
1. **R1 is officially supported in unitree_sdk2 (C++) and sdk2_python (partial).** C++: example/r1/{audio,high_level,low_level}; high_level = r1_arm_action_example, r1_arm_sdk_dds_example, r1_loco_client_example. Python: r1_loco_client + low-level A5/A7 only (no arm-action/audio found) https://github.com/unitreerobotics/unitree_sdk2 https://github.com/unitreerobotics/unitree_sdk2_python
2. **BrainCo ships a real Revo2 action-sequence tool**: python/revo2/revo2_action_seq.py + python/gui/action_sequence_panel.py, MIT, v2.0.8, pushed 2026-10-19. That is the "hand moves" path. TRY https://github.com/BrainCoTech/brainco-hand-sdk
3. **HanlongLi/hands = only repo built for exactly R1 EDU + Revo2** (RS485 USB per hand into Jetson, Mac browser panel, presets, webcam teleop, stall guard). Level 1 hands ready, never run on hw per README. TRY https://github.com/HanlongLi/hands
4. **IdlebBack/R1-EDU-Robot = event-ready C++ voice demos** (wake word Q&A, hotkey greetings, remote-combo + voice, wave+welcome). Closest to our event use. TRY https://github.com/IdlebBack/R1-EDU-Robot
5. **zzr-CO/Unitree_R1_Interactive_Greeting**: camera person-detect -> greeting + official arm action + BrainCo hand gesture. Exactly vision+voice+hands combo. TRY (read) https://github.com/zzr-CO/Unitree_R1_Interactive_Greeting
6. **Full-body dance on R1 is still not turnkey.** unitree_rl_mjlab has R1 for *velocity* task + deploy/robots/r1 only; *tracking* (motion imitation) = G1/G1_23dof only. GMR hits for "r1" are Galaxea R1 Pro (different robot), plus LZX968/GMR_R1 fork (sim retarget only). Use factory dances 601-603 + arm presets. https://github.com/unitreerobotics/unitree_rl_mjlab
7. **New sim path:** unitree_mujoco has unitree_robots/r1 (R1_C++.xml, scene.xml); cooplabs/spur adds R1+Dex3 MuJoCo sim; BrainCo brainco-description has Revo2 URDF/MJCF/USD (rel. 20261014); legion1581/unitree-mujoco-web runs policies in browser. WATCH/TRY on laptop.
8. **Safety-architecture to steal for kids:** HenrickTeng/r1-agent-motion (teacher approval, MuJoCo recheck, deterministic gateway, no LowCmd from models, NO dance). https://github.com/HenrickTeng/r1-agent-motion
9. **Do NOT run on our unit:** cooplabs/spur and kedianwen/LDRQ replace Unitree's balance/locomotion policy (spur: nothing proven beyond one robot; LDRQ: tens of seconds gantry-free). WATCH, read only.
10. **BrainCo is moving to Revo3 (SDK, RevoLab, Retargeting pushed 2026-10-23)**; Revo2 stays supported (Revo-Retargeting has revo2_retargeting branch w/ MANUS/Hex gloves). Don't confuse Revo3 repos with our Revo2 Pro.

## Best path (what to do)
- **New dances:** none via code. Use built-in 601-603/604 + arm presets by ID (`r1_arm_action_example --list`) + teach/playback (Mmaotttt, BSD-3). Whole-body imitation = G1 only today. Re-check unitree_rl_mjlab/tasks/tracking/config for an `r1` folder weekly.
- **Hand moves:** (1) revo2_action_seq.py + action_sequence_panel.py to author sequences on bench, (2) HanlongLi/hands for R1 wiring/safety/panel, (3) stark-serialport-example for raw Modbus. Per-hand: USB-RS485 into Jetson (HanlongLi doc, unverified vs Unitree docs) - Droni installs, we do not open wrists.
- **Vision:** zzr-CO greeting (person detect), mikeDK1/unitree-r1-gemini (Gemini on frames), Spur r1cam (reference). R1 camera API via SDK VideoClient not found in repos swept => ask.
- **AI voice:** IdlebBack r1_chat (local Q&A) as skeleton; swap in LT STT -> LLM -> ElevenLabs WAV -> PlayStream (16 kHz) per radar. LDRQ idea: LLM only emits a plan, deterministic checker + operator confirm. ros-claw/unitree-sdk2-mcp for LLM tool-calling (check safety first).

## Dead ends
- unitree_rl_gym: no R1, last push 2025-07-25. unitree_rl_lab: no R1 deploy (G1 29/23dof, H1_2). BeyondMimic official repo not found by name (404); forks are G1/other. KungFuBot, ASAP, PHC, HumanoidVerse: not swept for R1 (no R1 hits in code search) = unverified.
- GMR "r1" = Galaxea R1 Pro. lizuju = Linker Hand O6, not Revo2. gh search "ArmActionClient" / "rt/audio_msg" returned 0 repos (code search is limited).
- WebRTC driver (legion1581) is unofficial; may break on OTA. Not jailbreak, but not supported by Unitree.
- Not covered: Gitee, Bilibili, Unitree support site (JS-rendered). Official unitree_sdk2 R1 docs for hand wiring: not found.

## Install-on-R1 one-liners
- SDK C++: `git clone https://github.com/unitreerobotics/unitree_sdk2 && cd unitree_sdk2 && mkdir build && cd build && cmake .. && make` then `./bin/r1_arm_action_example <iface> --list` (flag per radar; verify on unit)
- BrainCo SDK: `git clone https://github.com/BrainCoTech/brainco-hand-sdk` (Python 3.9-3.12; Linux x86_64/aarch64)
- HanlongLi: `scripts/deploy_jetson.sh unitree@192.168.123.164` (from its README)
- MuJoCo R1: `git clone https://github.com/unitreerobotics/unitree_mujoco` -> unitree_robots/r1
- Spur sim: `git clone https://github.com/cooplabs/spur && cd spur && bash scripts/demo.sh`

## Findings log (raw, appended as found)

### Batch 1 (gh search repos, run 2026-10-23). NEW vs radar = marked NEW
| Repo | What | Label | Pushed | Stars | Lic | Cat | Verdict |
|---|---|---|---|---|---|---|---|
| github.com/kedianwen/LDRQ | R1 walking policy, asymmetric PPO Isaac Lab -> onboard Jetson Orin (NEW) | R1 named, unverified on hw | 2026-10-22 | 3 | Apache-2.0 | sim/RL | WATCH |
| github.com/cooplabs/spur | "Spur": open-source real-time controller + MuJoCo sim for R1 (NEW) | R1 named, hw unverified | 2026-10-21 | 7 | Apache-2.0 | sim/infra | WATCH (read first) |
| github.com/HanlongLi/hands | R1 + BrainCo Revo2 control stack, live webcam hand teleop (NEW) | R1 named, hw unverified | 2026-10-17 | 1 | none | hands/teleop | TRY (read) |
| github.com/dshifrin5/unitree-r1-brainco-hands | DIY Revo2 retrofit on R1 (known) | R1 1 owner | 2026-09-03 | 1 | none | hands | SKIP (Droni installs) |
| github.com/Mmaotttt/unitree_sdk2-modified | Teach/playback + calligraphy on R1 (known) | R1 | 2026-09-11 | 0 | BSD-3 | teach | TRY |
| github.com/kanakpandit17/robotics-lab | R1 + NEURA arms, VR (NEW) | R1 named | 2026-10-11 | 1 | none | teleop | WATCH |
| github.com/Yveline-Chen/Robocup-humanoid-SoccerTrain | R1 RoboCup soccer sim in Unity (NEW) | sim | 2026-09-03 | 1 | none | sim | SKIP |
| github.com/parthkgupta11-hue/r1-jetson-orin-nano-mount | 3D-print Jetson Orin Nano mount for R1 (NEW) | R1 | 2026-07-06 | 0 | other | infra | WATCH (payload/kids rules) |
| github.com/BrainCoTech/unitree-g1-brainco-hand | Official tutorial Revo2 on G1 | G1-only | 2026-10-12 | 29 | none | hands | WATCH (wiring ideas) |
| github.com/BrainCoTech/stark-serialport-example | Revo SDK example (serial/Modbus) | vendor | 2026-05-27 | 29 | none | hands | TRY (hand moves) |
| github.com/BrainCoTech/revo2_description_ros1 | Revo2 URDF + meshes | vendor | 2026-08-20 | 2 | Apache-2.0 | sim | WATCH |
| github.com/isri-aist/revo2_isaac_description | Revo2 Isaac Sim models | sim | 2026-10-04 | 0 | BSD-2 | sim | WATCH |
| github.com/Hakurei-Ma-risa/revo2-d435i-mujoco-teleop | Revo2 MuJoCo webcam teleop, ROS2 | hands-only | 2026-09-14 | 0 | Apache-2.0 | hands | WATCH |
| github.com/wsdd2/Vision_Sync_Dexterous_Hand | MediaPipe hand-skeleton -> dex hand, WebUI, Revo2 example | hands-only | 2026-08-31 | 1 | MIT | hands | TRY (no robot needed) |

### Deep reads (README, 2026-10-23)
- **cooplabs/spur** (https://github.com/cooplabs/spur): v0.1.1 early. R1 + 2x Dex3-1 (NOT Revo2). Runs on one real R1 per README; C++ rt core on rt/lowcmd 500 Hz, hot-standby "r1guard", MuJoCo sim `r1sim`, head camera `r1cam`, hands `r1hands`. Sim quickstart: `git clone https://github.com/cooplabs/spur && cd spur && bash scripts/demo.sh` (needs uv + C++17). Replaces Unitree's own balance controller = risky on our unit; use SIM + SAFETY.md as reference only. Verdict: WATCH (sim TRY on laptop).
- **kedianwen/LDRQ** (https://github.com/kedianwen/LDRQ): R1 walking policy trained in Isaac Lab, TensorRT on onboard Orin NX, 79.7 s walking w/o gantry, backward/sideways v2, English commands -> plan via small LLM on robot (77/80 held-out). Releases tarball for R1 EDU. Replaces onboard locomotion = voids safe default; WATCH. Idea worth stealing: LLM -> checked plan -> operator confirm.
- **HanlongLi/hands** (https://github.com/HanlongLi/hands): R1 EDU + Revo2 Basic. Hands via RS485 USB adapters into Jetson (192.168.123.164), bc-stark-sdk, Mac browser panel w/ sliders/presets/E-stop, MediaPipe webcam teleop, stall latch. Level 1 "ready for hardware" (mock+sim only; NOT run on a real R1 per README); levels 2-3 untested. Normalized joint order thumb,thumb_aux,index,middle,ring,pinky 0=open..1=closed = same as Unitree G1_Brainco datasets. Verdict: TRY with Droni-installed Revo2 (best hand-moves starting point).

### Batch 2: R1 apps, voice, retargeting, classroom (2026-10-23)
| Repo | What | Label | Pushed | Stars | Lic | Cat | Verdict |
|---|---|---|---|---|---|---|---|
| github.com/IdlebBack/R1-EDU-Robot | NEW. Welcome-robot C++ progs on unitree_sdk2: r1_chat (wake word + local Q&A file), r1_welcome_hotkey (keys 1-6 canned greetings), r1_remote_voice (remote combo + auto voice), r1_wave_welcome, head tools. Windows+VirtualBox Ubuntu 22.04, robot main PC 192.168.123.161. Copy into unitree_sdk2/example/r1/ + CMake target | R1 EDU real use | 2026-09-04 | 1 | none | voice/events | TRY (closest to our event use) |
| github.com/zzr-CO/Unitree_R1_Interactive_Greeting | NEW. Vision person detect -> morning greeting TTS + official arm action + BrainCo hand gesture combo | R1 + BrainCo | 2026-06-15 | 3 | none | vision/hands/voice | TRY (read README; fetch failed via API) |
| github.com/HenrickTeng/r1-agent-motion | NEW. Classroom Agent platform: teacher PC approves, compiles motion, re-checks in MuJoCo, gateway executes deterministic. No LowCmd from models, upper body/head/short slow walk only, NO dance. Models from unitree_rl_mjlab | R1, handoff doc says real-robot link partly unproven | 2026-10-08 | 0 | none | voice/AI/edu/sim | TRY idea (safety architecture for kids) |
| github.com/LZX968/GMR_R1 | NEW. Fork-backup of YanjieZe/GMR with R1 retargeting (SMPL-X -> R1) + SONIC SMPL; patches + R1 assets only | R1 retarget sim only | 2026-08-30 | 0 | MIT | dance | WATCH (retarget ok; no R1 whole-body tracker deployed) |
| github.com/JuanCruzz7/Unitree-R1-overview | NEW. Video -> arm + Revo2 hand retargeting (MediaPipe, ROS2, Gazebo/MuJoCo); docs+demos only, code private; sign-language goal | R1+Revo2 sim | 2026-10-06 | 1 | none | hands/vision | WATCH |
| github.com/fatima-at/R1-mpc-deepmimic | NEW. CEM-MPC -> DeepMimic walking in MuJoCo for R1 | sim only | 2026-08-26 | 0 | BSD-3 | dance/RL | SKIP (research) |
| github.com/OWFoundation/r1-skills | "Physical skills for Unitree R1" (README unreadable via API) | unverified | 2026-08-23 | 0 | MIT | skills | WATCH |
| github.com/lizuju/unitree-r1-a7-linker-o6 | Unofficial R1-A7 + Linker Hand O6, Isaac Lab + XR teleop | other hand | 2026-09-14 | 4 | - | teleop | SKIP for Revo2 |
| github.com/Syszhao/Unitree_R1_WALK | R1 walking from unitree_lab (CN) | sim | 2026-02-09 | 5 | - | RL | SKIP |
| github.com/legion1581/unitree_webrtc_connect | Go2/G1/R1 WebRTC driver (known) | R1 listed | 2026-08-17 | 417 | - | infra | WATCH (unofficial) |
| github.com/legion1581/unitree_ui | NEW. Browser control UI Go2/G1/R1 | R1 listed | 2026-09-30 | 73 | - | infra | WATCH |
| github.com/legion1581/unitree-mujoco-web | NEW. Unitree RL policies in browser (MuJoCo WASM + onnxruntime) | sim | 2026-09-30 | 15 | - | sim | WATCH (kid-demo sim, no robot) |
| github.com/ros-claw/unitree-sdk2-mcp | NEW. MCP server for Unitree via DDS incl. R1 | R1 listed | 2026-04-16 | 4 | - | AI/infra | WATCH (LLM tool-calling; check safety) |
| github.com/ros-claw/unitree-mujoco-mcp | NEW. MuJoCo sim MCP, incl R1 | sim | 2026-04-16 | 6 | - | sim/AI | WATCH |
| github.com/mikeDK1/unitree-r1-gemini | Gemini on R1 EDU (known) | R1 | 2026-08-24 | 1 | - | vision/AI | WATCH |
