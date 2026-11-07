# G1 -> R1 portability + official simulators (2026-10-23)
Scout: Sonnet 5.5. Status: DRAFT, appended as found. Labels: ✅ R1-verified (in local SDK) · 🟡 G1-only · ⚠️ unverified.

## A1. Local SDK diff (✅ verified from ~/r1/unitree_sdk2, HEAD dated 2026-10-15)
| Item | G1 | R1 | Portable? |
|---|---|---|---|
| Low-level topics | rt/lowcmd, rt/lowstate (hg LowCmd_/LowState_) | same rt/lowcmd, rt/lowstate + rt/secondary_imu (torso IMU) | ✅ same msg types (idl/hg) |
| Arm-only DDS | rt/arm_sdk | rt/arm_sdk (r1_arm_sdk_dds_example) | ✅ same topic, different joint indices |
| Motors | 29 (G1_NUM_MOTOR) | 26 indexed (0-25) = 12 leg + 2 waist (roll,yaw) + 5+5 arm (sh pitch/roll/yaw, elbow, wrist roll) + 2 head. +12 hand DOF = 38 | ❌ index map differs; arm is 5-DOF (wrist roll only), waist 2 not 3 |
| Joint order | legs 0-11, waist yaw/roll/pitch 12-14, arms 15-28 (7-DOF) | legs 0-11, waist roll/yaw 12-13, L arm 14-18, R arm 19-23, head 24-25 | needs joint map |
| Ankle | PR/AB modes | PR/AB modes (parallel A/B) | similar |
| Loco client | g1 LocoClient, service "sport", API 7101.. | r1 LocoClient, service "sport", SetFsmId/SetVelocity; Start()=fsm 811, Damp=1, StandUp=4, ZeroTorque=0 | ⚠️ same service name, different FSM ids: use r1 header |
| Arm action client | g1_arm_action_client | r1_arm_action_example; SDK comment: "do not replace with G1's client; same service name+API ids but different action ID list and more error codes" | ✅ own client |
| Audio | g1 audio client | r1/audio client + example | ✅ own client |
| Video / vision | g1 none in SDK | none in r1 headers (⚠️ use realsense/head cam via own stack) | n/a |
| Dex3 hand example | example/g1/dex3 | NOT in example/r1 | 🟡 G1-only (Dex3-1). Kris has BrainCo Revo2 -> use BrainCo SDK |
| g1d (AGV/dual) / agv | present | absent | 🟡 G1-only |
Gotchas: R1 headers include `dds_wrapper/robots/r1/r1.h` yet r1_arm_sdk example still uses g1::subscription::LowState (generic hg wrapper, works because same msg type).

## B. Official simulators — R1 model? (GitHub API, checked 2026-10-23)
| Repo | R1 asset? | last push | Notes |
|---|---|---|---|
| unitree_ros (github.com/unitreerobotics/unitree_ros) | ✅ robots/r1_description/R1.urdf, r1_a5_description, r1_a7_description, r1_air, r1_7a, r1d; also g1_with_brainco_hand | 2026-10-23 (r1_description touched same day) | URDF+meshes, Revo-hand G1 variant exists. |
| unitree_mujoco (…/unitree_mujoco) | ✅ unitree_robots/r1/{R1_C++.xml, scene.xml, meshes} (C++ sim only; python sim lists go2/b2/b2w/h1) | 2026-09-07 (r1 dir 2026-05-18) | Uses rt/lowcmd/lowstate over DDS = same SDK code runs against sim. README is apt/Linux-oriented; macOS ⚠️ unverified (MuJoCo+GLFW+CycloneDDS build on Mac is possible, not documented). |
| unitree_rl_mjlab (…/unitree_rl_mjlab) | ✅ task Unitree-R1-Flat (velocity), src/assets/robots/unitree_r1/xmls/r1.xml, deploy/robots/r1/main.cpp (sim2real C++ deploy, touched 2026-03-19) | 2026-04-13 | mjlab = MuJoCo-Warp. Needs Ubuntu 22.04 + NVIDIA GPU (setup_en.md). Motion tracking (BeyondMimic) tasks only G1 / G1-23dof, NOT R1. |
| unitree_rl_lab (Isaac Lab 2.3 / Isaac Sim 5.1) | ❌ README: Go2, H1, G1-29dof only | 2026-05-25 | Linux+NVIDIA. |
| unitree_rl_gym (Isaac Gym legged_gym) | ❌ no R1 hit | 2025-07-25 (stale) | Isaac Gym is deprecated. Skip. |
| unitree_sim_isaaclab | ❌ no R1 hit in repo search; G1 teleop/data-gen focus | 2026-03-30 | ⚠️ search-code only, not full README read. |
| unitree_model (HF-style asset repo) | ❌ B2 G1 Go2 H1 H2 H2_Plus only | 2026-06-01 | |
| unitree_IL_lerobot | ⚠️ G1 (Dex3/Inspire) focus | 2026-05-25 | |
| xr_teleoperate | ⚠️ G1/H1/H1_2 | 2026-09-07 | |
URLs: https://github.com/unitreerobotics/{unitree_ros,unitree_mujoco,unitree_rl_mjlab,unitree_rl_lab,unitree_rl_gym,unitree_sim_isaaclab,unitree_model}

More B facts (2026-10-23):
- MuJoCo Menagerie (https://github.com/google-deepmind/mujoco_menagerie, push 2026-10-20): unitree_a1, g1, go1, go2, h1, z1. ❌ no R1.
- NVIDIA Isaac-GR00T (https://github.com/NVIDIA/Isaac-GR00T, push 2026-10-22): ⚠️ not checked for R1; embodiments are NVIDIA-defined (G1 etc.).
- mjlab (https://github.com/mujocolab/mjlab, push 2026-10-21): "requires an NVIDIA GPU for training. macOS is supported for evaluation only." (README line 19) -> Mac can PLAY a trained R1 policy, not train.
- R1_C++.xml in unitree_mujoco has ~25 actuated joints matching SDK indices (waist roll/yaw, 5-DOF arms). It also lists a waist_pitch joint ⚠️ (unclear if actuated). Hands: ⚠️ no Revo2 in R1 MJCF seen. BrainCo hand URDF: https://github.com/BrainCoTech/revo2_description (2026-08-20).
- Unitree LAFAN1 retarget dataset is G1-only (referenced in https://github.com/HybridRobotics/whole_body_tracking README).

## A2. Port matrix (G1 asset -> R1)
| G1 asset | Verdict | Effort | GPU | Evidence / risk |
|---|---|---|---|---|
| unitree_sdk2 high-level loco client | needs config: use r1 client (fsm ids differ: Start=811) | h | none | ✅ local SDK r1_loco_client.hpp |
| arm_action preset gestures | works via R1 own client only (R1 action list differs) | h | none | ✅ SDK comment in r1_arm_action_example.cpp |
| rt/arm_sdk arm trajectories (own code) | needs joint map: R1 arm 5-DOF/side, idx 14-23; no wrist pitch/yaw | 1-2 d | none | ✅ SDK r1_arm_sdk_dds_example.cpp. Custom G1 7-DOF arm motions need IK/retarget to 5-DOF |
| Audio client | works via r1 audio client | h | none | ✅ |
| G1 Dex3 examples | won't work (Dex3 hardware). Revo2 uses BrainCo SDK | d | none | 🟡 BrainCoTech/unitree-g1-brainco-hand is G1-only (README says "adapting Revo2 to G1", uses G1 arm_sdk, 23/29 DOF) -> hand-control layer (Stark SDK, ros2_stark_ws) reusable, arm/body layer is not ⚠️ |
| xr_teleoperate | ⚠️ G1/H1/H1_2 only; R1 would need IK for 5-DOF arm + URDF (r1_a5/a7 URDF exist) | weeks | none (Mac ok for IK) | 🟡 |
| unitree_IL_lerobot / G1 datasets | datasets 🟡 G1-only (Dex3 toasted bread); code is framework: needs R1 action/state spaces, own data | weeks | GPU to train | ⚠️ |
| G1 velocity RL policy (any repo) | won't work as-is: different joint count/order/gains. Official path = RETRAIN: unitree_rl_mjlab Unitree-R1-Flat + deploy/robots/r1 | days (train hrs on GPU) | NVIDIA | ✅ exists in mjlab; risk: first custom low-level policy on a real humanoid -> gantry/harness, E-stop, warranty risk, don't ship without Unitree support |
| Motion tracking / dance (BeyondMimic whole_body_tracking, mjlab Tracking tasks) | G1 only; R1 needs own tracking env + retargeted motion | weeks | NVIDIA | 🟡 mjlab tracking tasks list only G1/G1-23dof |
| GMR retargeting | no Unitree R1 in assets (list: g1, g1 hands, h1, h1_2, h2, + others; Galaxea R1 Pro is NOT Unitree R1). Could add R1 xml (they accept contributions) | days | none (CPU) | ✅ checked https://github.com/YanjieZe/GMR assets list |
| LAFAN1 / AMASS-G1 datasets | motion data is human->G1; re-retarget to R1 via GMR once R1 added | days | none | ⚠️ |
| PHC / ASAP / KungfuBot / HumanoidVerse / TWIST | G1 specific envs, Isaac/IsaacGym; ASAP last push 2026-01-06, PHC 2025-08-21 | weeks, not worth | NVIDIA | 🟡/⚠️ not individually verified |
| GR00T | ⚠️ policy model, embodiment-specific finetune w/ R1 data; no ready R1 | weeks | big GPU | ⚠️ |
| Vision / voice examples | G1 SDK has none; use R1 audio + own camera stack | d | Jetson | ✅ |
| Unitree RL on Mac | MuJoCo viewer yes; mjlab train no | - | - | ✅ mjlab README |

## Realistic path for Kris
TL;DR: R1 IS in Unitree's official sims (unitree_mujoco, unitree_ros URDFs, unitree_rl_mjlab). Isaac-based repos have NO R1. Port nothing G1-specific blindly.
This week on the Mac (no GPU):
1. Clone unitree_mujoco, open unitree_robots/r1/scene.xml with `pip install mujoco` + `python -m mujoco.viewer` (viewer path = safe, ⚠️ C++ simulate/DDS bridge on macOS untested; python sim doesn't list R1).
2. Use r1_description/R1.urdf (or a5/a7 variants) to preview arm/dance joint trajectories (index map 14-23) and check limits before sending to rt/arm_sdk on the robot.
3. Use the robot's built-in arm_action list (r1_arm_action_example --list) for ready gestures; build Revo2 finger code from BrainCo SDK (hand layer only).
Cloud GPU (rent 1 NVIDIA box, Ubuntu 22.04, driver >=550): only if you want a custom walking policy: `train.py Unitree-R1-Flat` in unitree_rl_mjlab, then play on Mac. Budget: ⚠️ unverified.
Leave alone: Isaac Gym/unitree_rl_gym (stale 2025-07), unitree_rl_lab (no R1), G1 dance pipelines (BeyondMimic/ASAP/PHC/TWIST), G1 LAFAN1 data, GR00T, deploying any custom low-level locomotion policy (gantry + expert + warranty check with Unitree first).
Free fun: contribute an R1 asset to GMR (Yanjie Ze accepts new robots) -> dances from video later, CPU only.
