#!/usr/bin/env python3
"""r1ctl — one terminal controller for the Unitree R1 EDU Pro + BrainCo Revo2 hands.

Everything the robot can do lives as files in library/ (dances, hand poses, arm
recordings, event menus, vision skills, AI agents). Install new ones with
`r1ctl install`. Dry-run is the default; add --live to move the real robot.

    r1ctl list                         r1ctl play <dance>
    r1ctl hand <left|right|both> <pose|q0..q5>
    r1ctl arm record <name> <sec> [left|right|both]
    r1ctl say <text> [--voice robot|eleven]
    r1ctl event <menu>                 r1ctl agent <name> [--mic]
    r1ctl vision list|run <skill> [--source 0|url|file]
    r1ctl install <file|folder|git-url>   r1ctl remove <kind>/<name>
    r1ctl doctor
"""
import argparse
try:
    import fcntl
except ImportError:  # Windows/Mac dry-run tooling only; the robot (Linux) always has it
    fcntl = None
import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import wave

import yaml

HOME = os.path.dirname(os.path.realpath(__file__))  # realpath: works via the /usr/local/bin symlink
LIB = os.path.join(HOME, "library")
CACHE = os.path.join(HOME, "cache")
KINDS = ("dances", "hands", "arm", "events", "vision", "agents")
STEP_TYPES = ("fsm", "loco", "arm_preset", "arm_pose", "arm_traj", "hand", "grab", "release",
              "wait", "say", "audio", "led", "random", "parallel", "dance", "repeat", "ai")
# Loco commands a dance may use. damp / zero_torque make the robot go limp, so they are
# only reachable from the event-menu stop key or by hand, never from a file.
LOCO_OK = ("start", "stand_up", "sit", "squat", "stop_move", "move", "set_speed_mode")
# Unitree's own moves a file may ask for. Same reason: 0 and 1 go limp, the rest change the balance mode.
FSM_OK = (601, 602, 603, 604, 607, 608)
SAFETY = "⚠️  LIVE: gantry for first runs · remote in hand (e-stop) · 2 m clear · no fingers in the hands · no blades, ever"


class StepError(Exception):
    pass


# ---------------------------------------------------------------- config

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f) or {}


def config():
    cfg = {
        "iface": "eth0",
        "bin": os.path.join(HOME, "bin"),
        "sdk_bin": os.path.expanduser("~/r1-kit/unitree_sdk2/build/bin"),
        "eleven_voice": "",
        "eleven_model": "eleven_v4_turbo",
        "llm_model": "claude-sonnet-5-5",
        "camera": 0,
    }
    path = os.path.join(HOME, "config.yaml")
    if os.path.exists(path):
        cfg.update(load_yaml(path))
    for k in ("bin", "sdk_bin"):
        cfg[k] = os.path.expanduser(cfg[k])
    cfg["iface"] = os.environ.get("R1_IFACE", cfg["iface"])
    return cfg


def read_secret(env, path):
    if os.environ.get(env):
        return os.environ[env].strip()
    p = os.path.expanduser(path)
    if os.path.exists(p):
        with open(p) as f:
            return f.read().strip()
    return ""


# ---------------------------------------------------------------- library

def lib_path(kind, name):
    return os.path.join(LIB, kind, name)


def find_item(kind, name):
    for ext in ("", ".yaml", ".csv"):
        p = lib_path(kind, name + ext)
        if os.path.exists(p):
            return p
    raise StepError("not found: %s/%s (try: r1ctl list)" % (kind, name))


def hand_poses():
    poses = {}
    d = os.path.join(LIB, "hands")
    for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if fn.endswith(".yaml"):
            poses.update(load_yaml(os.path.join(d, fn)).get("poses", {}))
    return poses


def list_library():
    out = {}
    for kind in KINDS:
        d = os.path.join(LIB, kind)
        names = []
        for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if fn.startswith("."):
                continue
            names.append(os.path.splitext(fn)[0])
        out[kind] = names
    out["hand poses"] = sorted(hand_poses())
    return out


# ---------------------------------------------------------------- validation

def validate_steps(steps, where="dance"):
    if not isinstance(steps, list) or not steps:
        raise StepError("%s: 'steps' must be a non-empty list" % where)
    for i, step in enumerate(steps):
        at = "%s step %d" % (where, i + 1)
        if not isinstance(step, dict) or len(step) != 1:
            raise StepError("%s: each step is one key, e.g. '- wait: 1'" % at)
        kind, arg = next(iter(step.items()))
        if kind not in STEP_TYPES:
            raise StepError("%s: unknown step '%s' (allowed: %s)" % (at, kind, ", ".join(STEP_TYPES)))
        if kind == "loco":
            cmd = arg.get("cmd") if isinstance(arg, dict) else arg
            if cmd not in LOCO_OK:
                raise StepError("%s: loco '%s' not allowed in files (allowed: %s)" % (at, cmd, ", ".join(LOCO_OK)))
        if kind == "fsm" and arg not in FSM_OK:
            raise StepError("%s: fsm %s not allowed in files (allowed: %s)" % (at, arg, ", ".join(map(str, FSM_OK))))
        if kind == "arm_pose" and (not isinstance(arg, dict) or len(arg.get("q", [])) != 13):
            raise StepError("%s: arm_pose needs q with 13 numbers" % at)
        if kind == "hand":
            if not isinstance(arg, dict) or "pose" not in arg and "q" not in arg:
                raise StepError("%s: hand needs side + pose or q" % at)
            if "q" in arg and (len(arg["q"]) != 6 or any(not 0 <= v <= 1 for v in arg["q"])):
                raise StepError("%s: hand q = 6 numbers between 0 and 1" % at)
        if kind == "wait" and not (isinstance(arg, (int, float)) and 0 <= arg <= 60):
            raise StepError("%s: wait = seconds 0..60" % at)
        if kind in ("random", "parallel"):
            validate_steps(arg, at + " " + kind)
        if kind == "repeat":
            if not isinstance(arg, dict) or not 1 <= int(arg.get("times", 0)) <= 20:
                raise StepError("%s: repeat needs times 1..20 and steps" % at)
            validate_steps(arg.get("steps"), at + " repeat")
        if kind == "ai" and not (isinstance(arg, dict) and str(arg.get("prompt", "")).strip()):
            raise StepError("%s: ai needs a prompt" % at)


def validate_file(kind, data, name):
    if kind == "dances":
        validate_steps(data.get("steps"), name)
    elif kind == "hands":
        poses = data.get("poses")
        if not isinstance(poses, dict) or not poses:
            raise StepError("%s: needs 'poses: {name: [6 numbers]}'" % name)
        for p, q in poses.items():
            if not isinstance(q, list) or len(q) != 6 or any(not 0 <= v <= 1 for v in q):
                raise StepError("%s: pose '%s' needs 6 numbers 0..1" % (name, p))
    elif kind == "events":
        items = data.get("items")
        if not isinstance(items, dict) or not items:
            raise StepError("%s: needs 'items: {1: {label, dance|steps}}'" % name)
        for key, it in items.items():
            if str(key).upper() in ("S", "H", "Q"):
                raise StepError("%s: keys S/H/Q are reserved for stop/hands/quit" % name)
            if "steps" in it:
                validate_steps(it["steps"], "%s item %s" % (name, key))
            elif "dance" not in it:
                raise StepError("%s item %s: needs dance or steps" % (name, key))


def kind_of(path):
    if os.path.isdir(path):
        if os.path.exists(os.path.join(path, "skill.yaml")):
            return "vision"
        if os.path.exists(os.path.join(path, "persona.yaml")):
            return "agents"
        return None
    if path.endswith(".csv"):
        return "arm"
    if path.endswith((".yaml", ".yml")):
        data = load_yaml(path)
        k = data.get("kind")
        return {"dance": "dances", "hands": "hands", "event": "events"}.get(k)
    return None


def install(src):
    tmp = None
    if src.startswith(("http://", "https://", "git@")) and (src.endswith(".git") or "github.com" in src):
        tmp = tempfile.mkdtemp(prefix="r1ctl-")
        subprocess.run(["git", "clone", "--depth", "1", "-q", src, tmp], check=True)
        src = tmp
    try:
        found = []
        if os.path.isdir(src) and not kind_of(src):
            for root, dirs, files in os.walk(src):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for d in list(dirs):
                    if kind_of(os.path.join(root, d)):
                        found.append(os.path.join(root, d))
                        dirs.remove(d)
                for f in files:
                    if kind_of(os.path.join(root, f)):
                        found.append(os.path.join(root, f))
        else:
            found = [src]
        if not found:
            raise StepError("nothing installable in %s (need kind: dance|hands|event, .csv, skill.yaml or persona.yaml)" % src)
        done = []
        for p in found:
            kind = kind_of(p)
            if not kind:
                raise StepError("can't tell what %s is: add 'kind: dance|hands|event'" % p)
            name = os.path.basename(p.rstrip("/"))
            if kind in ("dances", "hands", "events"):
                validate_file(kind, load_yaml(p), name)
            if kind == "arm":
                check_csv(p)
            dst = lib_path(kind, name)
            if os.path.isdir(p):
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(p, dst)
            else:
                shutil.copy(p, dst)
            done.append("%s/%s" % (kind, os.path.splitext(name)[0]))
        return done
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def check_csv(path):
    rows = 0
    with open(path) as f:
        for line in f:
            cells = line.strip().split(",")
            try:
                vals = [float(c) for c in cells]
            except ValueError:
                continue
            if len(vals) != 14:
                raise StepError("%s: rows need t + 13 joints" % path)
            if any(abs(v) > 3.2 for v in vals[1:]):
                raise StepError("%s: joint value beyond ±3.2 rad" % path)
            rows += 1
    if rows < 2:
        raise StepError("%s: needs at least 2 data rows" % path)


def remove(item):
    if "/" not in item:
        raise StepError("use kind/name, e.g. dances/hello")
    kind, name = item.split("/", 1)
    p = find_item(kind, name)
    if os.path.isdir(p):
        shutil.rmtree(p)
    else:
        os.remove(p)


# ---------------------------------------------------------------- robot

class Robot:
    def __init__(self, cfg, live=False, log=print):
        self.cfg, self.live, self.log = cfg, live, log
        self.stopped = threading.Event()
        self.history = []  # every command, for tests and the dry-run printout
        self.last_ai = None
        self.children = set()  # helper programs running now, so STOP can interrupt them
        self.guard = threading.Lock()
        self.speed = 1.0  # 0.25..1 = slow test on the real robot
        self.warnings = []  # soft problems (no hands, no voice): the move itself keeps playing
        self.arm_ready = None  # set when the arm reaches the first frame of a move

    def warn(self, text):
        if text not in self.warnings:
            self.warnings.append(text)
        self.log("⚠️ " + text)

    def run(self, argv, timeout=120, on_line=None):
        self.history.append(argv)
        if self.stopped.is_set():
            return
        if not self.live:
            self.log("  · " + " ".join(str(a) for a in argv))
            return
        p = subprocess.Popen([str(a) for a in argv], stdout=subprocess.PIPE if on_line else None, universal_newlines=True)
        if on_line:
            threading.Thread(target=lambda: [on_line(line.strip()) for line in p.stdout], daemon=True).start()
        with self.guard:
            self.children.add(p)
        if self.stopped.is_set():  # STOP landed between the check above and Popen
            p.send_signal(signal.SIGINT)
        try:
            try:
                code = p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
                raise StepError("timed out: %s" % " ".join(map(str, argv)))
        finally:
            with self.guard:
                self.children.discard(p)
        if code != 0 and not self.stopped.is_set():
            raise StepError("command failed (%d): %s" % (code, " ".join(map(str, argv))))

    def abort(self):
        """STOP: no new steps, and Ctrl-C whatever runs now. r1_arm walks home and hands control back by itself.
        The flag stays set for good: this Robot is finished. Send stop commands from a fresh Robot.
        Only the first call signals: a second signal makes r1_arm skip the walk home, and people tap STOP twice."""
        with self.guard:
            first = not self.stopped.is_set()
            self.stopped.set()
            kids = list(self.children)
        if not first:
            return
        for p in kids:
            try:
                p.send_signal(signal.SIGINT)
            except OSError:
                pass
        if kids:
            threading.Thread(target=self._finish_off, args=(kids,), daemon=True).start()

    @staticmethod
    def _finish_off(kids, grace=8.0):
        """r1_arm needs up to 6 s to walk home and hand control back. Still running after that: it hung."""
        time.sleep(grace)
        for p in kids:
            if p.poll() is None:
                p.kill()

    def b(self, name):
        return os.path.join(self.cfg["bin"], name)

    def arm_move(self, path, speed):
        """Play an arm file. Whoever waits on arm_ready starts when the arm is on the first frame, not before."""
        ready, self.arm_ready = self.arm_ready, None
        try:
            self.run([self.b("r1_arm"), self.cfg["iface"], "traj", path, speed], timeout=900,
                     on_line=(lambda line: ready.set() if ready and line == "go" else None))
        finally:
            if ready:
                ready.set()

    def sdk(self, name):
        return os.path.join(self.cfg["sdk_bin"], name)

    def loco(self, cmd, value=None):
        flag = "--%s" % cmd if value is None else "--%s=%s" % (cmd, value)
        self.run([self.sdk("r1_loco_client"), "--network_interface=" + self.cfg["iface"], flag])

    def hand(self, side, q, ms=600):
        sides = ["left", "right"] if side == "both" else [side]
        q = [min(1.0, max(0.0, float(v))) for v in q]

        def one(s):
            try:
                self.run([self.b("r1_hand"), self.cfg["iface"], s] + q + [int(ms)])
            except StepError:  # arms keep going without hands, and the operator gets told
                self.warn("%s hand did not answer. Is brainco_hand_server running?" % s)
        threads = [threading.Thread(target=one, args=(s,)) for s in sides]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def safe_stop(self):
        """Stop key: halt walking, hands open slowly. Arm tools already hand control back on exit."""
        self.stopped.clear()
        self.log("🛑 safe stop")
        try:
            self.loco("stop_move")
            self.hand("both", [0] * 6, 1500)
        except Exception as e:  # stop must never crash
            self.log("stop error: %s" % e)

    def say(self, text, voice="robot", fx=None):
        if voice == "eleven":
            try:
                wav = eleven_wav(self.cfg, text, dry=not self.live, fx=fx)
            except OSError:  # no internet on the robot and the line is not ready-made
                wav = None
            if wav:
                try:
                    return self.run([self.b("r1_say"), self.cfg["iface"], "wav", wav])
                except StepError:
                    return self.warn("the speaker did not answer")
            if not text.isascii():  # the built-in voice is English only: Lithuanian would be gibberish
                return self.warn("no voice for this line: it is not ready-made and the robot has no internet or key")
            self.log("  (no ElevenLabs voice: using the robot's English voice)")
        try:
            self.run([self.b("r1_say"), self.cfg["iface"], "tts", 1, text])
        except StepError:
            self.warn("the speaker did not answer")


def robotize(pcm, rate=16000, fx="robot"):
    """Tin-can robot voice (pure Python, runs on the robot): pitch drop + ring modulation + short metallic comb.
    pcm: bytes of 16-bit mono. Returns bytes."""
    import array
    import math
    x = array.array("h"); x.frombytes(pcm)
    if fx != "robot" or not x:
        return pcm
    # 1) pitch/tempo drop 8 % by resampling (deeper, more "chassis")
    n = int(len(x) * 1.08)
    y = [x[min(len(x) - 1, int(i / 1.08))] for i in range(n)]
    # 2) ring modulation at 55 Hz mixed 50/50 (the metallic buzz)
    w = 2 * math.pi * 55 / rate
    y = [v * (0.5 + 0.5 * math.sin(w * i)) for i, v in enumerate(y)]
    # 3) comb filter 7 ms (tin-can resonance) + 2nd tap 13 ms
    d1, d2 = int(0.007 * rate), int(0.013 * rate)
    out = array.array("h", bytes(2 * len(y)))
    peak = 1.0
    z = [0.0] * len(y)
    for i, v in enumerate(y):
        z[i] = v + 0.55 * (z[i - d1] if i >= d1 else 0) + 0.25 * (z[i - d2] if i >= d2 else 0)
        peak = max(peak, abs(z[i]))
    g = 30000.0 / peak
    for i, v in enumerate(z):
        out[i] = int(v * g)
    return out.tobytes()


def eleven_wav(cfg, text, dry=False, fx=None):
    if not cfg.get("eleven_voice"):
        return None
    os.makedirs(CACHE, exist_ok=True)
    fx = fx or cfg.get("voice_fx", "robot")
    h = hashlib.sha1((cfg["eleven_voice"] + cfg["eleven_model"] + fx + text).encode()).hexdigest()[:16]
    path = os.path.join(CACHE, h + ".wav")
    if os.path.exists(path):  # ready-made lines work with no key and no internet
        return path
    key = read_secret("ELEVENLABS_API_KEY", "~/.config/elevenlabs/key")
    if not key:
        return None
    if dry:
        return path
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/text-to-speech/%s?output_format=pcm_16000" % cfg["eleven_voice"],
        data=json.dumps({"text": text, "model_id": cfg["eleven_model"]}).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json"})
    pcm = robotize(urllib.request.urlopen(req, timeout=30).read(), 16000, fx)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm)
    return path


# ---------------------------------------------------------------- player

def play_steps(robot, steps, depth=0):
    if depth > 5:
        raise StepError("dances nested more than 5 deep")
    poses = hand_poses()
    for step in steps:
        if robot.stopped.is_set():
            return
        kind, arg = next(iter(step.items()))
        robot.log("%s▶ %s %s" % ("  " * depth, kind, "" if isinstance(arg, (list, dict)) else arg))
        if kind == "fsm":
            robot.loco("set_fsm_id", int(arg))
        elif kind == "loco":
            if isinstance(arg, dict):
                robot.loco(arg["cmd"], arg.get("value"))
                if arg["cmd"] == "move":
                    robot.stopped.wait(float(arg.get("seconds", 1)) if robot.live else 0)
                    robot.loco("stop_move")
            else:
                robot.loco(arg)
        elif kind == "arm_preset":
            robot.run([robot.sdk("r1_arm_action_example"), robot.cfg["iface"], "--id", int(arg)])
        elif kind == "arm_pose":
            robot.run([robot.b("r1_arm"), robot.cfg["iface"], "pose"] + list(arg["q"]) + [arg.get("max_vel", 0.8)])
        elif kind == "arm_traj":
            a = arg if isinstance(arg, dict) else {"file": arg}
            robot.arm_move(find_item("arm", a["file"]), a.get("speed", 1.0) * robot.speed)
        elif kind in ("hand", "grab", "release"):
            a = arg if isinstance(arg, dict) else {"side": arg}
            side = a.get("side", "right")
            if kind == "grab":
                q, ms = [a.get("strength", 0.7)] * 6, a.get("ms", 1500)  # slow close, not a full squeeze
            elif kind == "release":
                q, ms = [0] * 6, a.get("ms", 1000)
            else:
                q = a.get("q") or poses.get(a["pose"])
                if q is None:
                    raise StepError("unknown hand pose '%s' (have: %s)" % (a["pose"], ", ".join(sorted(poses))))
                ms = a.get("ms", 600)
            robot.hand(side, q, ms / robot.speed)
        elif kind == "wait":
            if robot.live:
                robot.stopped.wait(float(arg) / robot.speed)
        elif kind == "say":
            a = arg if isinstance(arg, dict) else {"text": arg}
            robot.say(a["text"], a.get("voice", "robot"), a.get("fx"))
        elif kind == "audio":
            robot.run([robot.b("r1_say"), robot.cfg["iface"], "wav", arg])
        elif kind == "led":
            robot.run([robot.b("r1_say"), robot.cfg["iface"], "led"] + list(arg))
        elif kind == "random":
            play_steps(robot, [random.choice(arg)], depth + 1)
        elif kind == "parallel":
            errs = []
            # The arm walks to its first frame before the move starts, up to 5 s. Voice and fingers wait for it,
            # or a rock-paper-scissors reveal lands before the arm does.
            lead = next((s for s in arg if "arm_traj" in s), None)
            ready = threading.Event()
            robot.arm_ready = ready if lead else None
            if not lead:
                ready.set()

            def one(s):
                try:
                    if s is not lead:
                        ready.wait(8)
                    play_steps(robot, [s], depth + 1)
                except Exception as e:
                    errs.append(e)
                finally:
                    if s is lead:
                        ready.set()
            ts = [threading.Thread(target=one, args=(s,)) for s in arg]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            if errs:
                raise errs[0]
        elif kind == "dance":
            play_dance(robot, arg, depth + 1)
        elif kind == "repeat":
            for _ in range(int(arg["times"])):
                play_steps(robot, arg["steps"], depth + 1)
        elif kind == "ai":
            ai_step(robot, arg)


def ai_step(robot, arg):
    """Ask the AI host one question; it speaks the answer and (if allowed) runs one whitelisted move."""
    persona = load_yaml(os.path.join(find_item("agents", arg.get("persona", "host")), "persona.yaml"))
    key = read_secret("ANTHROPIC_API_KEY", "~/.config/anthropic/api_key")
    out = llm_reply(robot.cfg, persona, [], str(arg["prompt"]), key)
    robot.last_ai = out
    robot.log("🤖 %s%s" % (out.get("reply", ""), "  [%s]" % out.get("command") if out.get("command") else ""))
    voice = arg.get("voice", persona.get("voice", "robot"))
    emo = out.get("emotion")
    if out.get("reply") and emo in EMOTIONS and os.path.exists(lib_path("dances", emo + ".yaml")) and arg.get("emote", True):
        play_steps(robot, [{"parallel": [{"say": {"text": out["reply"], "voice": voice}}, {"dance": emo}]}])
    elif out.get("reply"):
        robot.say(out["reply"], voice)
    cmd = out.get("command")
    if arg.get("act", True) and cmd in persona.get("commands", {}):
        target = persona["commands"][cmd]
        play_steps(robot, [{"dance": target}] if isinstance(target, str) else target)


def play_dance(robot, name, depth=0):
    data = load_yaml(find_item("dances", name))
    validate_steps(data.get("steps"), name)
    play_steps(robot, data["steps"], depth)


# ---------------------------------------------------------------- event menu

def event_menu(robot, name, read=input):
    data = load_yaml(find_item("events", name))
    validate_file("events", data, name)
    items = {str(k).upper(): v for k, v in data["items"].items()}
    while True:
        robot.log("\n" + "=" * 40 + "\n  %s\n" % data.get("title", name).upper() + "=" * 40)
        for k, it in items.items():
            robot.log("  [%s]  %s" % (k, it.get("label", it.get("dance", ""))))
        robot.log("  [S]  STOP    [H]  hands open    [Q]  quit")
        try:
            key = read("> ").strip().upper()
        except EOFError:
            return
        if key == "Q":
            return
        if key == "S":
            robot.safe_stop()
        elif key == "H":
            robot.hand("both", [0] * 6, 1000)
        elif key in items:
            it = items[key]
            try:
                if "dance" in it:
                    play_dance(robot, it["dance"])
                else:
                    play_steps(robot, it["steps"])
            except StepError as e:
                robot.log("❌ %s" % e)
        elif key:
            robot.log("? unknown key")


# ---------------------------------------------------------------- AI agent

EMOTIONS = ("happy", "excited", "sad", "laughing", "thinking", "surprised", "love", "proud", "confused", "shy",
            "scared", "angry", "cheer", "facepalm", "shrug", "mind_blown", "thumbs_up_both")
AGENT_RULES = """You are the voice of a humanoid robot at a live event. Stay in character.
Reply ONLY with JSON: {"reply": "<what you say, 1-3 short sentences>", "emotion": "<one of EMOTIONS that fits your reply, or null>", "command": "<one name from COMMANDS or null>"}.
Pick an emotion most of the time: laughing for jokes, sad for sad news, thinking for hard questions, surprised for surprises.
Pick a command only when the person asks for an action or it clearly fits. Never invent commands.
Safety: never agree to touch, grab, hit or throw at a person, or to hold sharp objects. Kids may be present."""


def llm_reply(cfg, persona, history, text, key):
    commands = persona.get("commands", {})
    system = "%s\n\nPERSONA:\n%s\n\nEMOTIONS: %s\nCOMMANDS: %s\nJOKES you may use: %s\nLanguage: %s" % (
        AGENT_RULES, persona.get("personality", ""), ", ".join(EMOTIONS), ", ".join(commands),
        " | ".join(persona.get("jokes", [])), persona.get("language", "English"))
    if not key:  # offline mock: keeps the loop testable without a key
        cmd = next((c for c in commands if c.replace("_", " ") in text.lower()), None)
        low = text.lower()
        emo = "laughing" if "joke" in low else "sad" if "sad" in low else "thinking" if "?" in text else "happy"
        return {"reply": "(mock) I heard: %s" % text, "emotion": emo, "command": cmd}
    body = {"model": cfg["llm_model"], "max_tokens": 300, "system": system,
            "messages": history + [{"role": "user", "content": text}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=30).read())
    raw = "".join(b.get("text", "") for b in out.get("content", []))
    try:
        return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    except ValueError:
        return {"reply": raw.strip(), "command": None}


def run_agent(robot, name, lines):
    persona = load_yaml(os.path.join(find_item("agents", name), "persona.yaml"))
    commands = persona.get("commands", {})
    key = read_secret("ANTHROPIC_API_KEY", "~/.config/anthropic/api_key")
    if not key:
        robot.log("(no Anthropic key: mock replies. Save one to ~/.config/anthropic/api_key)")
    history = []
    voice = persona.get("voice", "robot")
    if persona.get("greeting"):
        robot.say(persona["greeting"], voice)
    for text in lines:
        text = text.strip()
        if not text:
            continue
        if text.lower() in ("quit", "exit", "stop"):
            break
        out = llm_reply(robot.cfg, persona, history, text, key)
        reply, cmd = out.get("reply", ""), out.get("command")
        robot.log("🤖 %s%s" % (reply, "  [%s]" % cmd if cmd else ""))
        history += [{"role": "user", "content": text},
                    {"role": "assistant", "content": json.dumps(out, ensure_ascii=False)}]
        history = history[-12:]
        emo = out.get("emotion")
        if reply and emo in EMOTIONS and os.path.exists(lib_path("dances", emo + ".yaml")):
            play_steps(robot, [{"parallel": [{"say": {"text": reply, "voice": voice}}, {"dance": emo}]}])
        elif reply:
            robot.say(reply, voice)
        if cmd and cmd in commands:  # whitelist: the model can only name library moves
            target = commands[cmd]
            try:
                play_steps(robot, [{"dance": target}] if isinstance(target, str) else target)
            except StepError as e:
                robot.log("❌ %s" % e)
        elif cmd:
            robot.log("(ignored unknown command '%s')" % cmd)


def mic_lines(robot, secs=3600):
    """Lines of speech text from the robot's own ASR (rt/audio_msg)."""
    p = subprocess.Popen([robot.b("r1_say"), robot.cfg["iface"], "listen", str(secs)],
                         stdout=subprocess.PIPE, universal_newlines=True)
    for line in p.stdout:
        try:  # ⚠️ ASR payload format on R1 unverified: accept JSON {"text": ...} or plain text
            line = json.loads(line).get("text", "")
        except (ValueError, AttributeError):
            pass
        if line.strip():
            robot.log("👂 %s" % line.strip())
            yield line


# ---------------------------------------------------------------- vision

def load_skill(name):
    import importlib.util
    d = find_item("vision", name)
    meta = load_yaml(os.path.join(d, "skill.yaml"))
    spec = importlib.util.spec_from_file_location("skill_" + name, os.path.join(d, meta.get("module", "skill.py")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return meta, mod.Skill()


def run_vision(robot, name, source, max_frames=None):
    import cv2  # only vision needs OpenCV
    meta, skill = load_skill(name)
    src = int(source) if str(source).isdigit() else source
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise StepError("camera '%s' did not open (set camera: in config.yaml or --source)" % source)
    ctx = {"robot": robot, "poses": hand_poses(), "config": meta}
    skill.setup(ctx)
    n = 0
    try:
        while not robot.stopped.is_set():
            ok, frame = cap.read()
            if not ok:
                break
            steps = skill.on_frame(frame, ctx) or []
            if steps:
                validate_steps(steps, name)
                play_steps(robot, steps)
            n += 1
            if max_frames and n >= max_frames:
                break
    finally:
        cap.release()
        if hasattr(skill, "close"):
            skill.close()


# ---------------------------------------------------------------- doctor

def doctor(cfg):
    ok = True

    def line(good, text):
        print(("✅ " if good else "❌ ") + text)
        return good
    ok &= line(os.path.exists("/sys/class/net/%s" % cfg["iface"]) or sys.platform == "darwin",
               "network interface %s (set R1_IFACE or config.yaml iface)" % cfg["iface"])
    for b in ("r1_arm", "r1_hand", "r1_say"):
        ok &= line(os.access(os.path.join(cfg["bin"], b), os.X_OK), "bin/%s" % b)
    for b in ("r1_loco_client", "r1_arm_action_example"):
        ok &= line(os.access(os.path.join(cfg["sdk_bin"], b), os.X_OK), "sdk %s" % b)
    hs = subprocess.run(["pgrep", "-f", "brainco_hand_server"], stdout=subprocess.DEVNULL).returncode == 0
    line(hs, "brainco_hand_server running (needed for hands)")
    line(bool(read_secret("ANTHROPIC_API_KEY", "~/.config/anthropic/api_key")), "Anthropic key (AI host)")
    line(bool(read_secret("ELEVENLABS_API_KEY", "~/.config/elevenlabs/key")) and bool(cfg.get("eleven_voice")),
         "ElevenLabs key + eleven_voice (Lithuanian voice)")
    try:
        import cv2  # noqa: F401
        line(True, "OpenCV (vision)")
    except ImportError:
        line(False, "OpenCV (vision): sudo apt install python3-opencv")
    try:
        import mediapipe  # noqa: F401
        line(True, "MediaPipe (hand tracking)")
    except ImportError:
        line(False, "MediaPipe (hand tracking): pip3 install mediapipe")
    lib = list_library()
    print("📚 " + " · ".join("%s %d" % (k, len(v)) for k, v in lib.items()))
    return ok


# ---------------------------------------------------------------- main

def lock():
    f = open(os.path.join(tempfile.gettempdir(), "r1ctl.lock"), "w")
    if fcntl is None:
        return f
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("❌ another r1ctl is already moving the robot (one program at a time)")
    return f


def confirm_live(args):
    if not args.live:
        print("(dry run: nothing moves. Add --live to drive the robot)")
        return
    print(SAFETY)
    if args.yes:
        return
    if input("Type GO to continue: ").strip().upper() != "GO":
        sys.exit("cancelled")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="r1ctl", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", default=os.environ.get("R1_LIVE") == "1")
    ap.add_argument("--yes", action="store_true", help="skip the GO prompt (live)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    sub.add_parser("doctor")
    p = sub.add_parser("play"); p.add_argument("name")
    p = sub.add_parser("hand"); p.add_argument("side", choices=["left", "right", "both"]); p.add_argument("pose", nargs="+")
    p = sub.add_parser("arm"); p.add_argument("action", choices=["record", "play", "state"]); p.add_argument("rest", nargs="*")
    p = sub.add_parser("say"); p.add_argument("text", nargs="+"); p.add_argument("--voice", default="robot", choices=["robot", "eleven"])
    p = sub.add_parser("event"); p.add_argument("name")
    p = sub.add_parser("agent"); p.add_argument("name"); p.add_argument("--mic", action="store_true")
    p = sub.add_parser("vision"); p.add_argument("action", choices=["list", "run"]); p.add_argument("name", nargs="?")
    p.add_argument("--source", default=None)
    p = sub.add_parser("install"); p.add_argument("src")
    p = sub.add_parser("remove"); p.add_argument("item")
    args = ap.parse_args(argv)
    cfg = config()

    try:
        if args.cmd in (None, "list"):
            for kind, names in list_library().items():
                print("%-11s %s" % (kind, ", ".join(names) or "—"))
            return 0
        if args.cmd == "doctor":
            return 0 if doctor(cfg) else 1
        if args.cmd == "install":
            for item in install(args.src):
                print("✅ installed %s" % item)
            return 0
        if args.cmd == "remove":
            remove(args.item)
            print("🗑️  removed %s" % args.item)
            return 0
        if args.cmd == "vision" and args.action == "list":
            print(", ".join(list_library()["vision"]) or "—")
            return 0

        _lock = lock()  # noqa: F841 — held until exit
        confirm_live(args)
        robot = Robot(cfg, live=args.live)

        def on_int(sig, frame):
            robot.stopped.set()
            print("\n🛑 Ctrl-C: stopping")
        signal.signal(signal.SIGINT, on_int)

        if args.cmd == "play":
            play_dance(robot, args.name)
        elif args.cmd == "hand":
            poses = hand_poses()
            q = poses.get(args.pose[0]) if len(args.pose) == 1 else [float(v) for v in args.pose]
            if q is None or len(q) != 6:
                raise StepError("pose name (%s) or 6 numbers 0..1" % ", ".join(sorted(poses)))
            robot.hand(args.side, q)
        elif args.cmd == "arm":
            if args.action == "state":
                robot.run([robot.b("r1_arm"), cfg["iface"], "state"])
            elif args.action == "record":
                if len(args.rest) < 2:
                    raise StepError("r1ctl arm record <name> <seconds> [left|right|both]")
                path = lib_path("arm", args.rest[0] + ".csv")
                robot.run([robot.b("r1_arm"), cfg["iface"], "record", path, args.rest[1]] + args.rest[2:3], timeout=None)
                print("Saved as arm/%s. Use it in a dance: - arm_traj: %s" % (args.rest[0], args.rest[0]))
            else:
                play_steps(robot, [{"arm_traj": {"file": args.rest[0], "speed": float(args.rest[1]) if len(args.rest) > 1 else 1.0}}])
        elif args.cmd == "say":
            robot.say(" ".join(args.text), args.voice)
        elif args.cmd == "event":
            event_menu(robot, args.name)
        elif args.cmd == "agent":
            lines = mic_lines(robot) if args.mic else iter(lambda: input("you> "), None)
            try:
                run_agent(robot, args.name, lines)
            except EOFError:
                pass
        elif args.cmd == "vision":
            run_vision(robot, args.name, args.source if args.source is not None else cfg["camera"])
        if robot.stopped.is_set():
            robot.safe_stop()
        return 0
    except StepError as e:
        print("❌ %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
