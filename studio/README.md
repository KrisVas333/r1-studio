# R1 Studio — program and drive the Unitree R1 from a browser

**Status:** ✅ works in the simulator on the Mac (tested in Chrome 2026-10-23) · ⚠️ not yet run on the real robot.

## Start
```bash
# Mac, simulator only (nothing moves):
~/r1/sim/.venv/bin/python ~/r1/studio/server.py          # open http://localhost:8080 in Chrome

# Real robot: after ~/r1/deploy.sh, on PC2 (ssh unitree@192.168.123.164)
python3 ~/r1-kit/studio/server.py --live [--camera 0]    # open http://192.168.123.164:8080 on the Mac
```
Then click **🤖 Robot**, type GO. Space = STOP everywhere.

## Tabs
| Tab | What |
|---|---|
| Blocks (left) | Scratch/SPIKE-style program. ▶ Run highlights the running block. 💾 Save → robot library (plays from `r1ctl` too) |
| 🎛️ Deck | 45 preset moves (Emotions · Reactions · Viral · Movies · Fight · Objects) + factory dances/gestures. Click = play, ＋ = add block, keys 1–0 = emotions |
| 👁️ Camera | Mac webcam or robot/server camera · hand signs, 80 objects, colors, body pose · "what do you see?" |
| 🎮 Drive | Telepresence MVP: WASD/QE walk, gamepad, hand buttons, camera picture-in-picture |
| 💬 AI | Claude host (personas host / sassy), auto emotions while talking, Operator mode (you type, robot speaks), 🎙️ hold to talk through the robot (robot voice effect) |
| 🎚️ Joints | Sliders for 13 arm/waist/head joints + 12 fingers, Choregraphe-style keyframe timeline → save as arm move |
| </> Code · 📜 Log | What the robot receives · what happened |

## Voice
Kris Pro voice (ElevenLabs `eleven_v4_turbo`) + `robotize()` tin-can effect (pitch −8 %, 55 Hz ring mod, 7/13 ms comb) in `r1ctl/r1ctl.py`. Settings: `r1ctl/config.yaml` (`eleven_voice`, `voice_fx: robot|none`). On PC2 copy the key: `scp ~/.config/elevenlabs/key unitree@192.168.123.164:~/.config/elevenlabs/key`. AI key: `~/.config/anthropic/api_key` (same on PC2).

## Moves
`tools/make_moves.py` writes the deck (arm keyframes → `r1ctl/library/arm/m_*.csv` + `dances/*.yaml`) and checks every move on **Unitree's R1 MuJoCo model**: joint limits, arm-body/arm-arm contact, speed. A path fixer swings arms outward around the body; a pose fixer turns forearms out until clear. 45/45 pass. Upper body only: legs stay with Unitree's balance controller.

## ⚠️ Unverified on the real robot
1. **Joint directions = Unitree's model.** Elbow measured on the model: **+1.4 straight, 0 = 90°, −0.95 folded** (>+1.5 bends backwards: never). First live test: one pose on the gantry.
2. Revo2 Pro hands: 0 = open guess; Unitree's hand service is written for Revo2 Basic (Pro may need TOUCH type).
3. Factory dance / gesture ids (601…, 27…) from community sources: run `r1_arm_action_example <iface> --list`.
4. Robot head camera: no official R1 camera API found. `--camera` takes any OpenCV source (USB webcam works).
5. Follow-person and copy-my-arms: experimental, 2D estimates. Clear floor, adult on STOP.
6. Hand timing inside moves (e.g. soft toss release) is approximate.
7. Head joints (nod/turn) are sent but not shown in the simulator (not in Unitree's model).

## Safety built in
Dry-run unless 🤖 Robot + GO · Space/Stop = halt + hands open · arm speed ≤ 2 rad/s, smooth ramps, control handed back · AI only triggers whitelisted moves · no walking-off commands in files · no blades, soft objects only, kids behind 2 m.

## 🧘 Yoga app (branch `joga`)
`server.py` also serves the r1-joga app at `/joga/` (`--joga <dir>`, config `joga_dir`, or auto: `~/r1-kit/r1-joga`, `<kit>/r1-joga`). `deploy.sh` copies `r1-joga/` to PC2 and runs `r1ctl install` on its `export/` (moves `joga_l<level>_<pose>`). Dry-run steps are now logged. Guide: r1-joga `INSTALL.md`.
