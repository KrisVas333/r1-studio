# R1 Studio — program and drive the Unitree R1 from a browser

Pamoka / tutorial: [docs/TUTORIAL.md](../docs/TUTORIAL.md)

## 🇱🇹 Trumpai lietuviškai
**Kas tai:** naršyklės programa robotui Unitree R1: blokai, judesių mygtukai, kamera, vairavimas, AI vedėjas, sąnariai. Visa sąsaja yra lietuvių ir anglų kalbomis.

**Paleisti (Mac, tik simuliatorius, robotas nejuda):**
```bash
~/r1/sim/.venv/bin/python ~/r1/studio/server.py
```
Atidaryk Chrome: **http://localhost:8080** (Studija) arba **http://localhost:8080/phone.html** (R1 Remote telefonui).

**Kalba:** viršuje dešinėje spausk **LT** arba **EN**. Numatyta kalba yra LT. Pasirinkimas įsimenamas šioje naršyklėje. Puslapis persikrauna, tavo programa lieka.

**AI vedėjas:** skiltyje 💬 AI pasirink „AI atsako: lietuviškai“. Reikia Anthropic rakto (`~/.config/anthropic/api_key`), be jo veikia bandomasis režimas.

**Saugumas:** tikram robotui reikia įrašyti **GO** (tas pats žodis abiem kalbomis). Tarpas arba STOP sustabdo viską.

**Liko angliškai:** judesių ištarti sakiniai (pvz. „Yay! This is the best day ever!“) gyvena r1ctl judesių failuose. Juos keičiant pasikeistų failų parašai, ir su robotu patikrinti judesiai vėl taptų nepatikrinti, todėl jie verčiami atskirai. Serverio pranešimai rodomi lietuviškai per vertimų lentelę `web/js/i18n.js`.

## Language / kalba
All UI text lives in one dictionary, `web/js/i18n.js` (`key: [English, Lithuanian]`). Static HTML uses `data-i18n*` attributes; code calls `t("key")`. The LT | EN switch stores `r1lang` in localStorage and reloads, so Blockly, menus and the Deck rebuild in the new language. Server and r1ctl messages stay English on the wire and are shown in LT through the `srv()` pattern table, so safety checks that match English text (`Not armed`, `half speed`) are unchanged. The AI tab sends `language` (Lithuanian/English) to `/api/ai`, which overrides the persona's `language` for that answer.

**Status:** ✅ works in the simulator on the Mac (tested in Chrome 2026-10-23, LT/EN 2026-11-07) · ⚠️ not yet run on the real robot.

## Start
```bash
# Mac, simulator only (nothing moves):
~/r1/sim/.venv/bin/python ~/r1/studio/server.py          # open http://localhost:8080 in Chrome

# Real robot: after ~/r1/deploy.sh, on PC2 (ssh unitree@192.168.123.164)
python3 ~/r1-kit/studio/server.py --live [--camera 0]    # open http://192.168.123.164:8080 on the Mac
```
Then click **🤖 Robot**, type GO. Space = STOP everywhere.

**One command per mode:** `~/r1/start-robot.sh mac | pc2 [PIN] | event PIN | sim`.

### Mac-direct (no backpack / PC2)
`mac_bridge.py` (run with `~/r1/.venv-sdk/bin/python`, setup: `~/r1/build-cyclonedds.sh`) talks DDS to the robot over the cable (`--iface en16`) and serves `GET /state` plus `POST /say {text}`, `/led {r,g,b}`, `/volume {n}` on 127.0.0.1:8090. Read-only unless started with `--allow-commands`; then a command also needs the token from `POST /arm {"go":"GO"}` in header `X-R1-Arm` (10 idle minutes). `/stop` drops it, no PIN needed. `--bind 0.0.0.0` refuses to start without `--pin`. `server.py --bridge` routes robot-voice lines, the volume slider and `/api/bridge/*` through it, arms it with the same GO, disarms it on STOP/End, and shows a 🟢/🔴 chip in the header (🔊 = robot speaker, 💻 = this computer; click to switch). Unitree's TTS is English/Chinese only. No arm or hand commands here on purpose (FSM 816 lockout). Tests: `tests/test_mac_bridge.py` (fake link, nothing reaches DDS).

## Tabs
| Tab | What |
|---|---|
| Blocks (left) | Scratch/SPIKE-style program. ▶ Run highlights the running block. 💾 Save → robot library (plays from `r1ctl` too) |
| 🎛️ Deck | 51 preset moves (Emotions · Reactions · Viral · Movies · Fight · Objects) + factory dances/gestures. Click = play, ＋ = add block, keys 1–0 = emotions |
| 👁️ Camera | Mac webcam or robot/server camera · hand signs, 80 objects, colors, body pose · "what do you see?" |
| 🎮 Drive | Telepresence MVP: WASD/QE walk, gamepad, hand buttons, camera picture-in-picture |
| 💬 AI | Claude host (personas host / sassy), auto emotions while talking, Operator mode (you type, robot speaks), 🎙️ hold to talk through the robot (robot voice effect) |
| 🎚️ Joints | Sliders for 13 arm/waist/head joints + 12 fingers, Choregraphe-style keyframe timeline → save as arm move |
| </> Code · 📜 Log | What the robot receives · what happened |

## Voice
Kris Pro voice (ElevenLabs `eleven_v4_turbo`) + `robotize()` tin-can effect (pitch −8 %, 55 Hz ring mod, 7/13 ms comb) in `r1ctl/r1ctl.py`. Settings: `r1ctl/config.yaml` (`eleven_voice`, `voice_fx: robot|none`). On PC2 copy the key: `scp ~/.config/elevenlabs/key unitree@192.168.123.164:~/.config/elevenlabs/key`. AI key: `~/.config/anthropic/api_key` (same on PC2).

## Moves
`tools/make_moves.py` writes the deck (arm keyframes → `r1ctl/library/arm/m_*.csv` + `dances/*.yaml`) and checks every arm file on **Unitree's R1 MuJoCo model** plus stand-in hands, row by row: joint limits, contact, speed. Files that pass go into `arm_safe.json`; on the real robot the server refuses the rest (today 59 cleared, 16 refused, all 16 yoga). Shapes only: no physics, no balance test, nothing has run on real hardware yet.

**On the real robot (`--live`) only R1 Remote (`/phone.html`) drives it.** `/` and `/joga/` redirect there. The server, not the page, enforces: typed GO arms it (`/api/arm`) · STOP, End and 15 idle minutes disarm · unseen moves are capped at half speed · a check is tied to the exact file bytes · single poses, walking and AI steps are refused · only `FSM_OK` factory moves. `r1ctl/tests/mock_robot/` is a stand-in robot over real DDS for testing `r1_arm` itself.

Known gaps, reachable only by a crafted POST, no button does them: `u_` moves are trusted, so `/api/arm_save` does not recheck rows · `/api/verified` works with no run · two arm files in one `parallel` are not refused. Anyone who can reach the port can do this, so on Wi-Fi use `--pin`.

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
