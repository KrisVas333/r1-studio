# R1 simulator preview (Mac)

Official Unitree R1 MuJoCo model (`unitreerobotics/unitree_mujoco`, unitree_robots/r1) + `r1sim.py`.
**Preview → fix → then the robot.** Arms + waist move; body held standing.

```bash
~/r1/preview wave_demo          # check + MP4 (opens)
~/r1/preview party              # any r1ctl dance by name
~/r1/preview ~/Desktop/move.csv # any arm recording
~/r1/preview hello live         # 3D window, drag to rotate
```
Checks: joint limits (from Unitree's model) · arm hits body · speed > 2 rad/s.

⚠️ Not simulated: hands (not in Unitree's model: shown as text), head joints, factory dances/gestures
(they live inside the robot), balance/walking. A green preview ≠ safe on the robot: first live run on the gantry.
