# R1 Studio research — social robots + robot control apps (2026-10-23)
Status: PARTIAL. Written from background knowledge; NO live web sources fetched (stalled). Everything below is ⚠️ unverified unless stated. No URLs verified, no follower numbers asserted.

## TL;DR
- Copy Choregraphe's model (timeline of poses + behavior boxes + dialog), but dress it in SPIKE/Scratch UX (word+icon blocks, big colors, highlight-on-run).
- Social-robot virality = talking back + personality + dances, mostly teleop/LLM hybrid. R1 can do dances + LLM chat via built-in speaker/mic.
- Safety for kids: LLM only picks from whitelisted actions (function calling), persona prompt, filler phrases for latency, push-to-talk.

## 1. Visual programming patterns worth copying (⚠️ from memory)
| Tool | Pattern to copy |
|---|---|
| Choregraphe (Aldebaran, NAO/Pepper) | Box library (drag boxes, connect in/out ports = flow); Timeline box with keyframes per joint; Pose library (save/recall poses); Dialog editor (topics/concepts); virtual robot 3D view; robot-view panel. Aldebaran went bankrupt 2025, assets bought by Hanson/United Robotics group ⚠️ verify; no clear successor |
| LEGO SPIKE (Prime/Essential) | Word blocks (beginner) vs icon blocks (young); color-coded categories; running block highlighted; sensor "wait until" hat/blocks; big Run button; one-screen simple |
| Scratch 3 | Stack blocks snap, shape = type; palette left, stage right; sprite = robot view; "when flag clicked" |
| Sphero Edu | Draw (path) / Blocks / Text levels = progression ladder |
| Misty Studio | Block + skills library; face/LED expression picker |
| Furhat | Blockly-based gestures + speech blocks ⚠️ |
| UBTECH uCode/Walker | Action-frame editor: pose snapshot per frame, play preview; servo-drag teaching |
| Unitree community | Mostly SDK/ROS, few web UIs — gap R1 Studio can fill ⚠️ |

## 2. Social humanoids (⚠️ all unverified; no follower counts given)
- Jake the Rizzbot (Unitree G1 with mask/costume, Austin, roasts/flirts in public; reportedly teleop + AI voice mix) ⚠️
- Ameca (Engineered Arts): LLM + expressive face; not transferable (face hardware)
- Unitree H1/G1 viral clips: dances, kung-fu, boxing, Spring Gala 2025 dance (pre-scripted/RL) ⚠️
- Viral drivers: personality/voice, talking back, dancing in sync, public interaction, mask/costume.
- Transfers to R1: LLM persona via speaker+mic, dance/gesture library, costume/mask on head (2-DOF only), Revo2 hand gestures (wave, high-five, rock-paper-scissors). Doesn't: expressive face, locomotion tricks beyond R1 limits.

## 3. LLM-agent patterns safe for kids
- Function calling to whitelist: say(text), play_action(id), set_led, wave... never raw joints.
- Persona system prompt + content filter before TTS; max length; refuse list.
- Latency: instant filler ("hmm, let me think"), stream TTS by sentence, pre-baked gestures during thinking.
- Push-to-talk (button/clap) preferred in noisy events; wake word optional.
- Operator "kill/stop" always visible; human-approve mode for risky actions.

## 4. Browser tech (⚠️ unverified for R1)
| Item | Note |
|---|---|
| Blockly | Best for custom block set, JSON block defs, code generators, highlightBlock for run-highlight. ✅ well known |
| scratch-blocks | Scratch look, but poorly maintained; 🟡 prefer Blockly with Scratch-like renderer ("zelos") |
| three.js + urdf-loader (gkjohnson) | Loads URDF + STL/DAE meshes; joint angles settable → live digital twin. ✅ known; ⚠️ R1 URDF availability |
| MediaPipe tasks-vision GestureRecognizer | Runs in browser WASM, webcam hand gestures → trigger actions. ✅ known |
| Robot camera → browser | MJPEG/WebRTC via small bridge on robot PC; Unitree VideoClient is G1/Go2 SDK 🟡 G1-only; R1 ⚠️ unverified |

## Top 10 features to copy into R1 Studio
1. Blockly blocks with word+icon labels, color categories, SPIKE-style (SPIKE/Scratch)
2. Highlight currently running block + big Run/Stop (Scratch/SPIKE)
3. Always-visible red STOP button (safety)
4. Pose library: save/recall poses via sliders (Choregraphe/uCode)
5. Timeline/keyframe editor for gestures + hands (Choregraphe)
6. 3D digital twin with URDF live preview before running on robot (three.js)
7. "Say" block with LLM-persona toggle; whitelisted-action function calling
8. Dance/gesture library one-click (event mode "performance deck")
9. Progression modes: Buttons → Blocks → Text (Sphero Edu)
10. Event/Kids mode: push-to-talk, content filter, operator approval, camera gesture trigger (MediaPipe)

---
## VERIFIED ADDITIONS (web, 2026-10-23)
### Jake the Rizzbot (Unitree G1, Austin)
- Remotely operated via wireless controller, not autonomous; operator nearby; human choreographs gestures+speech; sources differ on detail, speech stack unconfirmed. Unitree PR calls it a G1 "operated by users".
  - https://interestingengineering.com/innovation/jake-the-rizzbot-austin-robot
  - https://texascapitalnews.substack.com/p/austins-viral-rizzbot-raises-smilesand
  - https://en.prnasia.com/releases/global/unitree-g1-humanoid-robot-warmly-welcomed-and-captivates-audiences-worldwide-with-viral-moments-500657.shtml
  - https://languagelog.ldc.upenn.edu/nll/?p=70140 (teleop = inference)
- Follower counts: ⚠️ not found. Lesson: virality = Gen-Z flirt/roast banter + public street interaction, with a human in the loop. LESSON for R1: "operator-in-the-loop persona" is a legit, honest-if-disclosed model.

### Choregraphe (official Aldebaran docs mirrors)
- Panels: Box libraries, Flow diagram, Timeline, Robot view. Timeline box: motion keyframes + behavior layers; parallel behaviors need separate layers; each behavior keyframe holds its own flow diagram; time cursor; start/end frame; curve editor.
  - https://fileadmin.cs.lth.se/robot/nao/doc/software/choregraphe/panels/timeline_panel.html
  - https://fileadmin.cs.lth.se/robot/nao/doc/software/choregraphe/panels/flow_diagram_panel.html
  - https://fileadmin.cs.lth.se/robot/nao/doc/software/choregraphe/index.html
- ⚠️ Pose library / Dialog editor details not verified in this pass.

### Unitree R1 camera
- No official R1 camera API found. Community lib unitree_webrtc_connect lists R1 video-stream receive as supported (unofficial; check firmware): https://github.com/legion1581/unitree_webrtc_connect  -> 🟡 community-claimed R1; ⚠️ not R1-verified by us.
- R1 EDU has Jetson Orin NX dev computer at 192.168.123.164 (change default creds); binocular depth cam 1280x1088 RGB: https://www.docs.mybotshop.de/r1.html , https://humanoid.guide/product/unitree-r1/
- Practical plan: run own small MJPEG/WebRTC bridge on the Jetson (read camera there) -> browser. ⚠️ untested.

## Gaps (not researched): Furhat/Misty/Sphero/SPIKE specifics, MediaPipe/urdf-loader versions, follower counts, other viral robots.
