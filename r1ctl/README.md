# r1ctl — one controller for R1 + Revo2 hands

**Dry-run by default. Nothing moves without `--live` + typing GO.** Tests: 14/14 pass (Ubuntu 20.04, Python 3.8).

## Cheat-sheet (on the robot's PC2)
```bash
r1ctl doctor                       # what's ready / missing
r1ctl list                         # everything installed
r1ctl --live play hello            # play a dance
r1ctl --live hand right peace      # hand pose (or 6 numbers 0..1)
r1ctl --live say "Hello Vilnius"   # robot voice (--voice eleven = Lithuanian via ElevenLabs)
r1ctl --live event demo            # show menu: 1-9 actions · S stop · H hands open · Q quit
r1ctl --live agent host            # AI host, type to it (add --mic for the robot's ears)
r1ctl --live vision run rock_paper_scissors   # camera games
r1ctl --live arm record mywave 8 right        # move the arm by hand 8 s → arm/mywave
```

## Add a new… (3 lines each)
- **Dance:** copy `library/dances/hello.yaml` → edit steps → `r1ctl install mydance.yaml`. Steps: `fsm · loco · arm_preset · arm_pose · arm_traj · hand · grab · release · wait · say · audio · led · random · parallel · dance`.
- **Hand move:** add a line under `poses:` in a `kind: hands` YAML (6 numbers: thumb, thumb-rotate, index, middle, ring, pinky) → `r1ctl install`.
- **Arm move:** `r1ctl --live arm record <name> <sec> [left|right|both]` (on the gantry, arm goes soft, you move it) → use `- arm_traj: <name>` in a dance.
- **Event show:** copy `library/events/demo.yaml`, map keys 1–9 to dances → `r1ctl --live event <name>`.
- **Vision skill:** folder with `skill.yaml` + `skill.py` (`class Skill: setup(ctx)`, `on_frame(frame, ctx) -> [steps]`) → `r1ctl install <folder>`.
- **AI personality:** copy `library/agents/host/`, edit `persona.yaml` (personality, jokes, language, `commands:` whitelist) → `r1ctl install <folder>`.
- **From GitHub:** `r1ctl install https://github.com/<someone>/<pack>` installs every valid file it finds.

## Safety (built in)
- Every file is checked before it runs. Walking-off commands (`damp`, `zero_torque`) can't be put in files.
- Hand values clamped 0..1. Arm speed capped at 2 rad/s, smooth start, control handed back at the end.
- **Ctrl-C** = stop + hands open slowly. Only one r1ctl at a time (lock file).
- The AI can only trigger names in its `commands:` list, never raw joint values.
- ⛔ No blades or tools in the hands. Throws = soft objects only, adult-operated, never at people. Kids behind 2 m.

## Setup on PC2 (once)
```bash
sudo apt install python3-yaml python3-opencv && pip3 install mediapipe   # vision optional
# keys (never paste in chat):  ~/.config/anthropic/api_key  ·  ~/.config/elevenlabs/key
# edit config.yaml: iface (ip -br link), camera, eleven_voice
```

## ⚠️ Not yet verified on our robot
1. Hands: 0 = open / 1 = closed · Revo2 Pro may need hardware type TOUCH in the hand service
2. FSM 601 = dance 1 · arm preset ids (run `r1_arm_action_example <iface> --list`)
3. Joint signs in `arm/wave_demo.csv` (authored, not recorded): **record your own arm moves first**
4. ASR text format on `rt/audio_msg` · R1 head camera source (use a USB webcam until known)
5. A7 arms (extra wrist joints) not driven by r1_arm
