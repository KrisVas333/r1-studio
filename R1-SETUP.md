# R1 EDU Pro + Revo2 hands: terminal control setup

**Updated:** 2026-10-23 · kit folder: `~/r1`

## How it fits together

```
Mac terminal ──Ethernet──► R1 PC2 (Jetson, 192.168.123.164) ──DDS──► motors + hands
   (SSH only)               runs every program            rt/arm_sdk, rt/brainco/left|right
```
The Unitree SDK runs on **Linux only**, so the Mac never controls the robot directly. It is the keyboard: you SSH into the robot's own computer (PC2) and run programs there.

## ✅ Already done on this Mac
- Colima + Docker installed · image `r1-dev` = Ubuntu 20.04 + GCC 9.4 (same as PC2) + official SDK
- Cloned: `unitree_sdk2` (official) · `unitree_sdk2-modified` (teach/playback) · `brainco_hand_service` · `unitree-r1-brainco-hands` (retrofit notes)
- **All builds green** (aarch64 = robot CPU)
- Fixed a bug in the modified repo (`lococlient` typo on line 1 of `r1_loco_client_example.cpp`)
- New tool **`hand_cli`**: type `open / fist / point / peace / thumb / pinch / set … / state`

## Safety first (every session)
- Robot on the **gantry/hoist** for any first motion. Adult holds the **remote (e-stop: L2+B damping ⚠️ check your card)**.
- 2 m clear, no kids near it. Revo2 grips 50 N: **no fingers or hands inside the robot's hand.**
- Run **one** control program at a time.

## Step by step

**1. Cable.** USB-C Ethernet adapter → cable → the R1's developer Ethernet port. Power the robot on, stand it up with the remote (hold rear handle, R2+A).

**2. Network.**
```bash
cd ~/r1 && ./connect.sh          # lists adapters, find the new "USB 10/100/1000 LAN" device, e.g. en7
./connect.sh en7                 # sets Mac to 192.168.123.222, pings .161 and .164
```

**3. Log in to PC2.**
```bash
ssh unitree@192.168.123.164      # default password often "123" ⚠️ confirm with Droni
ip -br link                      # note the UP interface: eth0 or eth10 → call it IFACE below
ls /dev/ttyUSB* /dev/ttyCH343USB* 2>/dev/null   # hands visible?
ls ~/brainco_hand_service ~/stark-serialport-example   # factory hand software?
groups | grep dialout || sudo usermod -aG dialout unitree   # then log out + in
```

**4. Put our code on the robot** (from the Mac):
```bash
cd ~/r1 && ./deploy.sh           # copies to ~/r1-kit on PC2 and builds there
```

**5. First arm test** (on PC2, robot standing, built-in controller running):
```bash
cd ~/r1-kit/unitree_sdk2/build/bin
./r1_arm_action_example IFACE --list     # photo this list → wiki
./r1_arm_action_example IFACE --id 27    # handshake gesture
./r1_arm_action_example IFACE --id 99    # release arm
```

**6. Hands.** Terminal A:
```bash
cd ~/brainco_hand_service/bin && sudo ./brainco_hand_server --network IFACE
```
If it finds no hand and your ports are `/dev/ttyUSB*` (not `ttyCH343USB*`), edit the port filter in `main.cpp` per retrofit notes §15, then rebuild. Terminal B:
```bash
cd ~/r1-kit/brainco_hand_service/bin
./hand_cli left IFACE            # then: open, fist, point, state, quit
./hand_cli right IFACE
```
⚠️ 0 = open / 1 = closed is read from Unitree's test, not yet seen on our unit. First command: `open`.

**7. Teach by hand** (right arm goes limp, you move it, it replays):
```bash
cd ~/r1-kit/unitree_sdk2-modified/build/bin
./r1_loco_client --network_interface=IFACE --start   # locomotion mode first
./r1_teach_playback IFACE        # record | stop | play | playslow | save wave1 | load wave1 | quit
```

**8. Walk / stand / move:** `./r1_loco_client --network_interface=IFACE --<cmd>` with cmd = `damp` · `start` · `stand_up` · `sit` · `squat` · `stop_move` · `zero_torque` · `get_fsm_id` · `set_fsm_id=601` (dance 1 ⚠️) · `move="0.2 0 0"` (vx vy yaw). **`damp` = go limp: only on the gantry.**

## Compile on the Mac (optional, checks code before deploy)
```bash
colima start
docker run --rm -it -v ~/r1:/r1 r1-dev bash
```

## Open questions (⚠️)
- SSH password, remote e-stop combo, firmware version → Droni
- Are the hands already wired to PC2 at the factory (EDU Pro), or is it the DIY retrofit layout?
- Which interface name PC2 uses (eth0 vs eth10)

## Step 9 — r1ctl (dances · hands · voice · vision · AI host)
Full guide: `~/r1/r1ctl/README.md`. After `./deploy.sh`, on PC2:
```bash
r1ctl doctor          # fix every ❌ that matters for today
r1ctl list
r1ctl play hello      # dry run first: prints what it WOULD do
r1ctl --live hand right open      # first live command (gantry, remote in hand)
r1ctl --live event demo           # the show menu
```
Research: `~/r1/research/` (GitHub map · G1→R1 + simulators · forums/events + tomorrow checklist).

## Step 10 — Preview in the simulator first (Mac)
`~/r1/preview <dance>` → video + ✅/❌ check on Unitree's official R1 model. `~/r1/preview <dance> live` = 3D window. Details: `~/r1/sim/README.md`.
