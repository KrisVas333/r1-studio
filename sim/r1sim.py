#!/usr/bin/env python3
"""r1sim — preview r1ctl dances and arm recordings on the official Unitree R1 MuJoCo model.

Kinematic preview (the body is held standing, arms/waist follow the timeline):
checks joint limits, arm-to-body collisions and joint speed BEFORE anything runs on the robot.

    r1sim check <dance|arm.csv>             report only
    r1sim video <dance|arm.csv> [-o out.mp4] render an MP4 (opens it)
    r1sim view  <dance|arm.csv>             live 3D window (macOS: run with .venv/bin/mjpython)

Factory moves (fsm dances, arm presets) live inside the robot and can't be previewed: the
timeline holds the pose and names them. Hands and head aren't in Unitree's model: shown as text.
"""
import argparse
import os
import subprocess
import sys

import mujoco
import numpy as np
import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
SCENE = os.path.join(HERE, "unitree_mujoco", "unitree_robots", "r1", "scene.xml")
R1CTL = os.path.join(os.path.dirname(HERE), "r1ctl")
sys.path.insert(0, R1CTL)
import r1ctl  # noqa: E402  (library lookup + validation shared with the robot side)

# r1_arm / CSV column order → MuJoCo joint names (None = not in Unitree's model)
COLUMNS = ["left_shoulder_pitch", "left_shoulder_roll", "left_shoulder_yaw", "left_elbow", "left_wrist_roll",
           "right_shoulder_pitch", "right_shoulder_roll", "right_shoulder_yaw", "right_elbow", "right_wrist_roll",
           "waist_yaw", None, None]
FPS = 30
MAX_VEL = 2.0  # rad/s, same cap as r1_arm


class Timeline:
    def __init__(self):
        self.frames = []   # (t, q13)
        self.notes = []    # (t, text)
        self.q = np.zeros(13)
        self.t = 0.0

    def note(self, text):
        self.notes.append((self.t, text))

    def hold(self, secs):
        n = max(1, int(secs * FPS))
        for _ in range(n):
            self.t += 1.0 / FPS
            self.frames.append((self.t, self.q.copy()))

    def move_to(self, target, max_vel=0.8):
        start = self.q.copy()
        dur = max(0.2, float(np.max(np.abs(target - start))) / max_vel)
        n = int(dur * FPS)
        for k in range(1, n + 1):
            s = k / n
            s = s * s * (3 - 2 * s)
            self.q = start + (target - start) * s
            self.t += 1.0 / FPS
            self.frames.append((self.t, self.q.copy()))

    def play_csv(self, path, speed=1.0):
        rows = []
        for line in open(path):
            try:
                v = [float(c) for c in line.strip().split(",")]
            except ValueError:
                continue
            if len(v) == 14:
                rows.append(v)
        rows = np.array(rows)
        self.move_to(rows[0, 1:], 0.6)  # same slow approach r1_arm uses
        t0, tend = rows[0, 0], rows[-1, 0]
        n = int((tend - t0) / speed * FPS)
        for k in range(1, n + 1):
            tt = t0 + k / FPS * speed
            self.q = np.array([np.interp(tt, rows[:, 0], rows[:, 1 + j]) for j in range(13)])
            self.t += 1.0 / FPS
            self.frames.append((self.t, self.q.copy()))


def build(tl, steps, depth=0):
    poses = r1ctl.hand_poses()
    for step in steps:
        kind, arg = next(iter(step.items()))
        if kind == "fsm":
            tl.note("🤖 factory move FSM %s (plays on robot only, ~10 s)" % arg)
            tl.hold(2)
        elif kind == "loco":
            tl.note("🚶 walk/stance: %s" % (arg if not isinstance(arg, dict) else arg.get("cmd")))
            tl.hold(1)
        elif kind == "arm_preset":
            tl.note("🤖 factory arm gesture #%s (robot only)" % arg)
            tl.hold(2)
        elif kind == "arm_pose":
            tl.note("💪 arm pose")
            tl.move_to(np.array(arg["q"], float), arg.get("max_vel", 0.8))
        elif kind == "arm_traj":
            a = arg if isinstance(arg, dict) else {"file": arg}
            tl.note("💪 arm move %s" % a["file"])
            tl.play_csv(r1ctl.find_item("arm", a["file"]), a.get("speed", 1.0))
        elif kind in ("hand", "grab", "release"):
            a = arg if isinstance(arg, dict) else {"side": arg}
            label = a.get("pose") or (kind if kind != "hand" else "q=%s" % a.get("q"))
            if kind == "hand" and a.get("pose") and a["pose"] not in poses:
                tl.note("❌ unknown hand pose %s" % a["pose"])
            tl.note("✋ %s hand: %s" % (a.get("side", "right"), label))
            tl.hold(a.get("ms", 600) / 1000.0)
        elif kind == "wait":
            tl.hold(float(arg))
        elif kind == "say":
            text = arg if isinstance(arg, str) else arg["text"]
            tl.note("🗣️ \"%s\"" % text)
            tl.hold(max(1.0, len(text) / 15.0))  # rough speaking time
        elif kind in ("audio", "led"):
            tl.note("%s %s" % ("🔊" if kind == "audio" else "💡", arg))
        elif kind == "random":
            tl.note("🎲 random pick of %d (previewing all, one after another)" % len(arg))
            build(tl, arg, depth + 1)
        elif kind == "parallel":
            # arm motion runs, other branches (hands, voice) are notes at the same moment
            arms = [s for s in arg if next(iter(s)) in ("arm_traj", "arm_pose")]
            rest = [s for s in arg if s not in arms]
            t0 = tl.t
            for s in rest:
                k, a = next(iter(s.items()))
                tl.notes.append((t0, "∥ %s %s" % (k, a if not isinstance(a, dict) else a.get("pose", a.get("file", "")))))
            build(tl, arms or [{"wait": 0.5}], depth + 1)
        elif kind == "dance":
            tl.note("▶ dance %s" % arg)
            build(tl, r1ctl.load_yaml(r1ctl.find_item("dances", arg))["steps"], depth + 1)


def load_target(name):
    tl = Timeline()
    if name.endswith(".csv") or os.path.exists(name):
        tl.note("💪 arm move %s" % os.path.basename(name))
        tl.play_csv(name)
    else:
        data = r1ctl.load_yaml(r1ctl.find_item("dances", name))
        r1ctl.validate_steps(data["steps"], name)
        build(tl, data["steps"])
    tl.hold(1)
    return tl


class Sim:
    def __init__(self):
        self.m = mujoco.MjModel.from_xml_path(SCENE)
        self.d = mujoco.MjData(self.m)
        self.adr = []
        for c in COLUMNS:
            if c is None:
                self.adr.append(None)
                continue
            j = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_JOINT, c + "_joint")
            self.adr.append((j, self.m.jnt_qposadr[j]))
        mujoco.mj_resetData(self.m, self.d)
        self.base = self.d.qpos.copy()
        self.base[2] = self.standing_height()
        floor = [g for g in range(self.m.ngeom) if self.m.geom_bodyid[g] == 0]
        self.floor = set(floor)

    def standing_height(self):
        self.d.qpos[:] = 0
        self.d.qpos[3] = 1
        mujoco.mj_kinematics(self.m, self.d)
        lowest = min(self.d.geom_xpos[g][2] - self.m.geom_rbound[g] * 0.3 for g in range(self.m.ngeom)
                     if self.m.geom_bodyid[g] != 0)
        return -lowest + 0.02

    def pose(self, q13):
        self.d.qpos[:] = self.base
        for v, a in zip(q13, self.adr):
            if a is not None:
                self.d.qpos[a[1]] = v
        mujoco.mj_forward(self.m, self.d)

    def check(self, tl):
        problems, seen = [], set()
        prev = None
        for t, q in tl.frames:
            for i, a in enumerate(self.adr):
                if a is None:
                    continue
                j = a[0]
                lo, hi = self.m.jnt_range[j]
                if self.m.jnt_limited[j] and not (lo - 1e-3 <= q[i] <= hi + 1e-3):
                    key = ("limit", i)
                    if key not in seen:
                        seen.add(key)
                        problems.append("%5.1fs ❌ %s = %.2f outside %.2f..%.2f" % (t, COLUMNS[i], q[i], lo, hi))
            if prev is not None:
                v = np.max(np.abs(q - prev)) * FPS
                if v > MAX_VEL * 1.05 and ("vel",) not in seen:
                    seen.add(("vel",))
                    problems.append("%5.1fs ⚠️ joint speed %.1f rad/s > %.1f cap (robot will move slower)" % (t, v, MAX_VEL))
            prev = q
            self.pose(q)
            for c in self.d.contact[:self.d.ncon]:
                if c.geom1 in self.floor or c.geom2 in self.floor or c.dist > -0.005:
                    continue
                b1 = mujoco.mj_id2name(self.m, mujoco.mjtObj.mjOBJ_BODY, self.m.geom_bodyid[c.geom1])
                b2 = mujoco.mj_id2name(self.m, mujoco.mjtObj.mjOBJ_BODY, self.m.geom_bodyid[c.geom2])
                if not any(k in (b1 or "") + (b2 or "") for k in ("shoulder", "elbow", "wrist", "hand")):
                    continue
                key = ("hit", b1, b2)
                if key not in seen:
                    seen.add(key)
                    problems.append("%5.1fs ❌ collision %s ↔ %s" % (t, b1, b2))
        self.pose(np.zeros(13))
        base_hits = {(mujoco.mj_id2name(self.m, mujoco.mjtObj.mjOBJ_BODY, self.m.geom_bodyid[c.geom1]),
                      mujoco.mj_id2name(self.m, mujoco.mjtObj.mjOBJ_BODY, self.m.geom_bodyid[c.geom2]))
                     for c in self.d.contact[:self.d.ncon] if c.dist <= -0.005}
        # contacts already present in the neutral pose are model quirks, not dance problems
        return [p for p in problems if not any(a in p and b in p for a, b in base_hits)]


def camera():
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = [0, 0, 0.75]
    cam.distance, cam.azimuth, cam.elevation = 2.6, 160, -10
    return cam


def report(name, tl, problems):
    print("🎬 %s · %.1f s" % (name, tl.t))
    for t, text in tl.notes:
        print("  %5.1fs  %s" % (t, text))
    if problems:
        print("\n".join(["", "PROBLEMS (fix before the robot):"] + ["  " + p for p in problems]))
    else:
        print("\n✅ within joint limits · no arm-body collisions · speeds OK")
    print("⚠️ preview = arms + waist only. Hands, head, factory moves and balance are NOT simulated.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["check", "video", "view"])
    ap.add_argument("target")
    ap.add_argument("-o", "--out")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    try:
        tl = load_target(a.target)
    except r1ctl.StepError as e:
        sys.exit("❌ %s" % e)
    sim = Sim()
    problems = sim.check(tl)
    report(a.target, tl, problems)

    if a.mode == "video":
        import imageio
        out = a.out or os.path.join(HERE, "previews", os.path.splitext(os.path.basename(a.target))[0] + ".mp4")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        sim.m.vis.global_.offwidth, sim.m.vis.global_.offheight = 720, 540
        r = mujoco.Renderer(sim.m, 540, 720)
        cam = camera()
        with imageio.get_writer(out, fps=FPS, quality=7) as w:
            for _, q in tl.frames:
                sim.pose(q)
                r.update_scene(sim.d, cam)
                w.append_data(r.render())
        print("🎞️  %s" % out)
        if not a.no_open and sys.platform == "darwin":
            subprocess.run(["open", out])
    elif a.mode == "view":
        import time
        from mujoco import viewer as mjviewer
        with mjviewer.launch_passive(sim.m, sim.d) as v:
            v.cam.lookat[:], v.cam.distance, v.cam.azimuth, v.cam.elevation = [0, 0, 0.75], 2.6, 160, -10
            while v.is_running():
                for _, q in tl.frames:
                    if not v.is_running():
                        break
                    sim.pose(q)
                    v.sync()
                    time.sleep(1.0 / FPS)
                time.sleep(1)
    return 1 if any("❌" in p for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
