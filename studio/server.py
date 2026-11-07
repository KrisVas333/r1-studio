#!/usr/bin/env python3
"""R1 Studio server — serves the browser app and runs block programs through r1ctl.

    python3 server.py                 # simulator only (Mac or robot), http://localhost:8080
    python3 server.py --live          # on the robot's PC2: blocks can drive the real R1
    python3 server.py --camera 0      # stream an OpenCV camera to the app (robot or USB cam)
    python3 server.py --joga ~/r1-kit/r1-joga   # also serve the R1 yoga app at /joga/ (auto-found if omitted)
    python3 server.py --live --pin 4821         # every action needs the PIN. STOP never does.

R1 Remote (phone-sized controller + 3D emulator): /phone.html. https://<robot>:8443/phone.html is the
same page with the microphone allowed: browsers block mics on plain http.

Only Python stdlib + PyYAML (+ OpenCV for --camera). Open the printed address in Chrome.
"""
import argparse
import concurrent.futures
import errno
import glob
import hashlib
import json
import os
import posixpath
import re
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
import wave
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

HERE = os.path.dirname(os.path.realpath(__file__))
WEB = os.path.join(HERE, "web")
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "r1ctl"))
import r1ctl  # noqa: E402

STATE = {"live": False, "robot": None, "log": [], "busy": threading.Lock(), "camera": None, "joga": None,
         "pin": None, "health": (0, None), "https_port": None, "armed": 0}  # armed = time of the last move, 0 = not armed
# deploy.sh mirrors the code folders with --delete, so anything made on the robot lives outside them
DATA = os.path.expanduser(os.environ.get("R1_DATA", "~/r1-data"))
SOUNDS = os.path.join(DATA, "sounds")     # uploaded music + effects
BUILTIN = os.path.join(HERE, "sounds")    # the kit that ships with the app
VERIFIED = os.path.join(DATA, "verified.json")  # moves a human watched on the real robot
MAX_UPLOAD = 40 * 1024 * 1024  # 20 min of 16 kHz mono
SAFE = os.path.join(HERE, "arm_safe.json")  # arm files that passed Unitree's body shapes, written by tools/make_moves.py
IDLE_DISARM = 15 * 60  # seconds
QUIET = ("say", "audio", "led", "wait")  # steps that move nothing, so they need no arming
SLOWS = {"arm_traj", "hand", "grab", "release"}  # what half speed really slows down
NEVER_LIVE = {"arm_pose": "single arm poses skip the safety check", "loco": "walk with the hardware remote",
              "ai": "the AI host cannot drive the robot yet"}
MODES = {0: "limp (zero torque)", 1: "damping", 4: "locked stance", 811: "walking mode", 816: "arms mode, no walking"}


def find_joga(cli=None):
    """R1 yoga app folder: --joga, then config `joga_dir`, then ~/r1-kit/r1-joga, <kit>/r1-joga, sibling clone."""
    cands = [cli, r1ctl.config().get("joga_dir"), "~/r1-kit/r1-joga",
             os.path.join(os.path.dirname(HERE), "r1-joga"), os.path.join(os.path.dirname(os.path.dirname(HERE)), "r1-joga")]
    for c in cands:
        if c and os.path.isfile(os.path.join(os.path.expanduser(c), "index.html")):
            return os.path.realpath(os.path.expanduser(c))
    return None


def log(line):
    STATE["log"].append({"t": time.time(), "line": str(line)})
    del STATE["log"][:-300]
    print(line, flush=True)


def arm_csv(name):
    rows = []
    for line in open(r1ctl.find_item("arm", name)):
        try:
            v = [float(c) for c in line.strip().split(",")]
        except ValueError:
            continue
        if len(v) == 14:
            rows.append(v)
    return rows


def library():
    lib = r1ctl.list_library()
    dances = {}
    for name in lib["dances"]:
        data = r1ctl.load_yaml(r1ctl.find_item("dances", name))
        dances[name] = {"title": data.get("title", name), "steps": data.get("steps", []),
                        "category": data.get("category"), "emoji": data.get("emoji", ""), "seconds": data.get("seconds")}
    personas = {}
    for name in lib["agents"]:
        p = r1ctl.load_yaml(os.path.join(r1ctl.find_item("agents", name), "persona.yaml"))
        personas[name] = {"name": p.get("name", name), "commands": p.get("commands", {}), "greeting": p.get("greeting", ""),
                          "language": p.get("language", "English")}
    return {"dances": dances, "hands": r1ctl.hand_poses(), "arm": lib["arm"], "personas": personas,
            "emotions": list(r1ctl.EMOTIONS), "uncleared": [a for a in lib["arm"] if not cleared(a)]}


class Camera:
    """Background OpenCV grabber → latest JPEG for the MJPEG endpoint."""

    def __init__(self, source):
        try:
            import cv2
        except ImportError:
            raise r1ctl.StepError("OpenCV is missing on the robot. Installing it needs internet. No move needs a camera.")
        self.cv2, self.jpeg, self.source = cv2, None, source
        self.cap = cv2.VideoCapture(int(source) if str(source).isdigit() else source)
        if not self.cap.isOpened():
            raise r1ctl.StepError("camera '%s' did not open" % source)
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while True:
            ok, frame = self.cap.read()
            if ok:
                self.jpeg = self.cv2.imencode(".jpg", frame, [self.cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()
            else:
                time.sleep(0.5)
            time.sleep(1 / 20)


class Player:
    """One sound at a time on the robot speaker, apart from moves, so music can run under a dance."""

    def __init__(self):
        self.p, self.name = None, None

    def play(self, path, name):
        self.stop()
        cfg = r1ctl.config()
        self.p = subprocess.Popen([os.path.join(cfg["bin"], "r1_say"), cfg["iface"], "wav", path],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.name = name
        log("🔊 %s" % name)

    def say(self, text):
        """The robot's built-in English voice, for a typed line with no ready-made audio."""
        self.stop()
        cfg = r1ctl.config()
        self.p = subprocess.Popen([os.path.join(cfg["bin"], "r1_say"), cfg["iface"], "tts", "1", text],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.name = text[:40]
        log("🔊 %s" % self.name)

    def stop(self):
        p, self.p, self.name = self.p, None, None
        if p and p.poll() is None:
            p.send_signal(signal.SIGINT)  # r1_say tells the audio service to stop, then exits
            try:
                p.wait(1.5)
            except subprocess.TimeoutExpired:
                p.kill()

    def playing(self):
        return self.name if self.p and self.p.poll() is None else None


PLAYER = Player()


def clean_name(name):
    return "".join(c for c in str(name) if c.isalnum() or c in "_- ").strip()[:48]


def sound_path(name):
    """A stored sound by name. clean_name first: names come from the browser."""
    name = clean_name(name)
    for folder in (SOUNDS, BUILTIN):
        p = os.path.join(folder, name + ".wav")
        if name and os.path.exists(p):
            return p
    raise r1ctl.StepError("no sound called %s" % name)


def sound_list():
    out = []
    for folder, mine in ((SOUNDS, True), (BUILTIN, False)):
        for p in sorted(glob.glob(os.path.join(folder, "*.wav"))):
            try:
                with wave.open(p) as w:
                    secs = w.getnframes() / float(w.getframerate())
            except (wave.Error, EOFError):
                continue
            out.append({"name": os.path.basename(p)[:-4], "secs": round(secs, 1), "mine": mine})
    return out


def save_wav(path, pcm):
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(pcm)
    os.replace(tmp, path)


def verified():
    try:
        with open(VERIFIED) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def probe(argv, timeout=4):
    """Run a read-only helper → (ok, stdout). Nothing here moves the robot."""
    try:
        r = subprocess.run([str(a) for a in argv], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=timeout, universal_newlines=True)
        return r.returncode == 0, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False, ""


def online(host="api.elevenlabs.io"):
    try:
        socket.create_connection((host, 443), timeout=1.5).close()
        return True
    except OSError:
        return False


def health():
    """Every link the operator depends on: green, or one plain sentence saying what to do."""
    t, last = STATE["health"]
    if last and (time.time() - t < 6 or STATE["busy"].locked()):
        return last  # never start DDS programs in the middle of a move
    cfg = r1ctl.config()
    sim = "Emulator: no robot connected"
    items = []

    def item(id_, label, state, note, fix=""):
        items.append({"id": id_, "label": label, "state": state, "note": note, "fix": fix})

    if STATE["live"]:
        arm, hand, say = [os.path.join(cfg["bin"], n) for n in ("r1_arm", "r1_hand", "r1_say")]
        loco = os.path.join(cfg["sdk_bin"], "r1_loco_client")
        i = cfg["iface"]
        with concurrent.futures.ThreadPoolExecutor(5) as ex:
            jobs = {"fsm": ex.submit(probe, [loco, "--network_interface=" + i, "--get_fsm_id"]),
                    "arm": ex.submit(probe, [arm, i, "state"]), "left": ex.submit(probe, [hand, i, "left", "state"]),
                    "right": ex.submit(probe, [hand, i, "right", "state"]), "vol": ex.submit(probe, [say, i, "getvolume"])}
        res = {k: v.result() for k, v in jobs.items()}
        m = re.search(r"fsm_id:\s*(-?\d+)", res["fsm"][1])
        mode = int(m.group(1)) if m else None
        fix = ("" if m and mode not in (0, 1, 816) else
               "Is the robot on and past the 1 minute boot? Server must run on the robot itself." if not m else
               "Stand it up with the remote first." if mode in (0, 1) else
               "Our arm moves switch the robot to this mode. The remote will not walk it now. Unitree's known bug, "
               "issue 182. A restart should bring walking back.")
        item("robot", "Robot", "bad" if not m else "warn" if fix else "ok",
             "Mode %d: %s" % (mode, MODES.get(mode, "not in our list")) if m else "No answer from the robot", fix)
        good = res["arm"][0] and len(res["arm"][1].split()) == 13
        built = os.path.exists(arm)
        item("arms", "Arms", "ok" if good else "bad", "13 joints reading" if good else "No joint data",
             "" if good else "Another control program may hold the arms. Stop it, then press Refresh." if built else
             "The arm program was not built. Run deploy.sh again and read its last lines.")
        hs = probe(["pgrep", "-f", "brainco_hand_server"])[0]
        for side in ("left", "right"):
            ok = res[side][0]
            item("hand_" + side, side.capitalize() + " hand", "ok" if ok else "bad", "Answering" if ok else "No answer",
                 "" if ok else ("Check the hand cable and power." if hs else
                                "Start it in a second window: cd ~/r1-kit/brainco_hand_service/bin && sudo ./brainco_hand_server --network " + i))
        vm = re.search(r"volume (\d+)", res["vol"][1])
        item("speaker", "Robot speaker", "ok" if vm else "bad", "Volume %s" % vm.group(1) if vm else "Audio service did not answer",
             "" if vm else "Press Refresh. If it stays red, use a Bluetooth speaker on the laptop.")
        STATE["volume"] = int(vm.group(1)) if vm else None
    else:
        for id_, label in (("robot", "Robot"), ("arms", "Arms"), ("hand_left", "Left hand"),
                           ("hand_right", "Right hand"), ("speaker", "Robot speaker")):
            item(id_, label, "sim", sim)
        STATE["volume"] = None
    cam, devs = STATE["camera"], sorted(glob.glob("/dev/video*"))
    if cam and cam.jpeg:
        item("camera", "Camera", "ok", "Live picture")
    elif cam:
        item("camera", "Camera", "warn", "Started, no picture yet", "Wait 5 seconds, or try the next camera number.")
    elif devs:
        item("camera", "Camera", "warn", "Found %d, not started" % len(devs), "Open the Camera tab and press Start.")
    else:
        item("camera", "Camera", "sim" if not STATE["live"] else "warn", "None found on the server",
             "Plug a USB webcam into the robot computer. No move needs a camera, so you can film with a phone.")
    net = online()
    key = bool(r1ctl.read_secret("ELEVENLABS_API_KEY", "~/.config/elevenlabs/key"))
    ready = len([p for p in glob.glob(os.path.join(r1ctl.CACHE, "*.wav")) if not os.path.basename(p).startswith("voice_")])
    if net and key:
        item("voice", "Voice", "ok", "%d lines ready, new lines work" % ready)
    else:
        item("voice", "Voice", "warn", "%d lines ready. New typed lines off" % ready,
             "Ready lines and the Talk button still work. Typed lines need %s." % (
                 "the voice key on the robot" if net else "internet on the robot"))
    item("internet", "Internet", "ok" if net else "warn", "Online" if net else "Offline",
         "" if net else "Fine for moves, ready lines, sounds and Talk.")
    ai = bool(r1ctl.read_secret("ANTHROPIC_API_KEY", "~/.config/anthropic/api_key"))
    item("ai", "AI host", "ok" if ai and net else "warn", "Ready" if ai and net else "Off",
         "" if ai and net else "Needs a key and internet on the robot. Optional.")
    out = {"items": items, "live": STATE["live"], "volume": STATE.get("volume"), "camera_devices": devs}
    STATE["health"] = (time.time(), out)
    return out


def say_now(data):
    """Speak right away through the soundboard player, so a line never waits for a move to end."""
    text = str(data.get("text", "")).strip()[:400]
    if not text:
        raise r1ctl.StepError("nothing to say")
    if not (data.get("live") and STATE["live"]):
        return {"ok": True, "live": False}
    cfg = r1ctl.config()
    if data.get("voice") != "robot":
        try:
            wav = r1ctl.eleven_wav(cfg, text, fx=data.get("fx"))
        except OSError:  # no internet on the robot and the line is not ready-made
            wav = None
        if wav:
            PLAYER.play(wav, text[:40])
            return {"ok": True, "live": True}
        if not text.isascii():  # the built-in voice is English only
            raise r1ctl.StepError("no voice for this line: it is not ready-made and the robot has no internet or key")
    PLAYER.say(text)
    return {"ok": True, "live": True}


def stop_everything():
    """STOP button. Disarms, ends the running move for good, then sends stop commands from a fresh Robot."""
    STATE["armed"] = 0
    r = STATE["robot"]
    if r:
        r.abort()
    PLAYER.stop()
    if STATE["live"]:
        ARM.interrupt()
        fresh = r1ctl.Robot(r1ctl.config(), live=True, log=log)
        threading.Thread(target=fresh.safe_stop, daemon=True).start()
    log("🛑 STOP")


class Handler(SimpleHTTPRequestHandler):
    # explicit types: Windows registries often map .js to text/plain, which breaks ES modules
    extensions_map = dict(SimpleHTTPRequestHandler.extensions_map, **{
        ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json", ".mp3": "audio/mpeg",
        ".wav": "audio/wav", ".wasm": "application/wasm", ".svg": "image/svg+xml", ".css": "text/css"})

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB, **kw)

    def translate_path(self, path):
        """/joga/... → the r1-joga folder (read-only static files); everything else → studio/web."""
        p = path.split("?", 1)[0].split("#", 1)[0]
        if STATE["joga"] and (p == "/joga" or p.startswith("/joga/")):
            rel = p[len("/joga"):] or "/"
            full = os.path.realpath(super().translate_path(rel).replace(os.path.realpath(WEB), STATE["joga"], 1))
            if full == STATE["joga"] or full.startswith(STATE["joga"] + os.sep):
                return full
            return os.path.join(STATE["joga"], "__nope__")
        return super().translate_path(path)

    def log_message(self, *a):
        pass

    def end_headers(self):
        # browsers must re-check the app files, or an update (e.g. a new language) shows the old page
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        # Three pages can drive the robot. On the real robot only this one has the preview and the half-speed rule.
        clean = posixpath.normpath("/" + unquote(re.split(r"[?#]", self.path)[0]).lstrip("/"))
        if STATE["live"] and (clean in ("/", "/index.html", "/joga") or clean.startswith("/joga/")):
            self.send_response(302)
            self.send_header("Location", "/phone.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if self.path == "/api/status":
            cfg = r1ctl.config()
            return self.send_json({
                "live_allowed": STATE["live"], "camera": STATE["camera"] is not None, "iface": cfg["iface"],
                "ai_key": bool(r1ctl.read_secret("ANTHROPIC_API_KEY", "~/.config/anthropic/api_key")),
                "eleven": bool(cfg.get("eleven_voice")) and bool(r1ctl.read_secret("ELEVENLABS_API_KEY", "~/.config/elevenlabs/key")), "host": socket.gethostname(),
                "pin": bool(STATE["pin"]), "https_port": STATE["https_port"], "verified": verified_now(), "playing": PLAYER.playing(),
                "armed": is_armed()})
        if self.path == "/api/health":
            return self.send_json(health())
        if self.path == "/api/sounds":
            return self.send_json({"sounds": sound_list(), "playing": PLAYER.playing()})
        if self.path.startswith("/api/sound?"):
            try:
                return self.send_file(sound_path(parse_qs(urlparse(self.path).query).get("name", [""])[0]))
            except r1ctl.StepError as e:
                return self.send_json({"error": str(e)}, 404)
        if self.path == "/api/library":
            return self.send_json(library())
        if self.path.startswith("/api/arm/"):  # noqa: E501 (recorded / keyframed arm moves)
            try:
                return self.send_json(arm_csv(self.path.split("/")[-1]))
            except r1ctl.StepError as e:
                return self.send_json({"error": str(e)}, 404)
        if self.path.startswith("/api/tts?"):
            q = parse_qs(urlparse(self.path).query)
            text = q.get("text", [""])[0][:400]
            try:
                path = r1ctl.eleven_wav(r1ctl.config(), text, fx=q.get("fx", [None])[0]) if text else None
            except OSError:
                path = None
            if not path:
                return self.send_json({"error": "no ready-made voice for this line"}, 404)
            return self.send_file(path)
        if self.path.startswith("/api/log"):
            since = float(self.path.split("since=")[-1]) if "since=" in self.path else 0
            return self.send_json([e for e in STATE["log"] if e["t"] > since])
        if self.path.split("?")[0] == "/api/camera.mjpg":
            if not STATE["camera"]:
                return self.send_json({"error": "no camera on server"}, 404)
            if STATE["pin"] and parse_qs(urlparse(self.path).query).get("pin", [""])[0] != STATE["pin"]:
                return self.send_json({"error": "PIN needed"}, 403)
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    j = STATE["camera"].jpeg
                    if j:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + j + b"\r\n")
                    time.sleep(1 / 15)
            except OSError:  # browser closed the stream
                return
        return super().do_GET()

    def send_file(self, path):
        data = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        # STOP needs no PIN, ever: anyone standing there must be able to stop the robot
        if STATE["pin"] and self.path != "/api/stop" and self.headers.get("X-R1-Pin") != STATE["pin"]:
            return self.send_json({"error": "PIN needed"}, 403)
        try:
            if self.path.startswith("/api/voice"):
                return self.voice()
            if self.path.startswith("/api/sound_upload"):
                return self.send_json(upload_sound(self))
            data = self.body()
            if self.path == "/api/step":
                return self.send_json(run_step(data))
            if self.path == "/api/stop":
                stop_everything()
                return self.send_json({"ok": True})
            if self.path == "/api/arm":
                if str(data.get("go", "")).strip().upper() != "GO":
                    raise r1ctl.StepError("type GO to arm")
                STATE["armed"] = time.time()
                log("🟥 armed")
                return self.send_json({"ok": True, "armed": True})
            if self.path == "/api/say":
                return self.send_json(say_now(data))
            if self.path == "/api/sound_play":
                path = sound_path(data.get("name"))
                if not (data.get("live") and STATE["live"]):
                    return self.send_json({"ok": True, "live": False})
                PLAYER.play(path, data["name"])
                return self.send_json({"ok": True, "live": True})
            if self.path == "/api/sound_stop":
                PLAYER.stop()
                return self.send_json({"ok": True})
            if self.path == "/api/sound_delete":
                p = os.path.join(SOUNDS, clean_name(data.get("name")) + ".wav")
                if not os.path.exists(p):
                    raise r1ctl.StepError("only your uploads can be deleted")
                os.remove(p)
                return self.send_json({"ok": True})
            if self.path == "/api/volume":
                level = max(0, min(100, int(data.get("level", 50))))
                if STATE["live"]:
                    cfg = r1ctl.config()
                    if not probe([os.path.join(cfg["bin"], "r1_say"), cfg["iface"], "volume", level])[0]:
                        raise r1ctl.StepError("the speaker did not answer")
                return self.send_json({"ok": True, "level": level, "live": STATE["live"]})
            if self.path == "/api/verified":
                v, name = verified(), clean_name(data.get("name"))
                speed = max(0.25, min(1.0, float(data.get("speed", 0.5))))
                old = v.get(name, {})
                if old.get("ok") and data.get("ok") and old.get("sha") == fingerprint(name):
                    speed = max(speed, old.get("speed", 0.5))  # a slow rerun must not undo a full-speed check
                v[name] = {"ok": bool(data.get("ok")), "t": time.time(), "speed": speed, "sha": fingerprint(name)}
                os.makedirs(DATA, exist_ok=True)
                with open(VERIFIED, "w") as f:
                    json.dump(v, f, ensure_ascii=False, indent=1)
                return self.send_json({"ok": True, "verified": verified_now()})
            if self.path == "/api/camera_start":
                STATE["camera"] = Camera(data.get("source", 0))
                STATE["health"] = (0, None)
                return self.send_json({"ok": True})
            if self.path == "/api/end":
                if STATE["busy"].locked():  # the pill now says test mode, so nothing may keep moving
                    stop_everything()
                    return self.send_json({"ok": True, "stopped": True})
                STATE["armed"] = 0
                if STATE["live"]:
                    ARM.release()
                return self.send_json({"ok": True})
            if self.path == "/api/arm_save":
                return self.send_json(save_arm(data))
            if self.path == "/api/save":
                return self.send_json(save_dance(data))
            if self.path == "/api/ai":
                persona = r1ctl.load_yaml(os.path.join(r1ctl.find_item("agents", data.get("persona", "host")),
                                                       "persona.yaml"))
                if data.get("language") in ("Lithuanian", "English"):  # the Studio's "AI answers in" choice
                    persona["language"] = data["language"]
                key = r1ctl.read_secret("ANTHROPIC_API_KEY", "~/.config/anthropic/api_key")
                out = r1ctl.llm_reply(r1ctl.config(), persona, data.get("history", []), data["text"], key)
                out["mock"] = not key
                log("🤖 %s" % out.get("reply", ""))
                return self.send_json(out)
            return self.send_json({"error": "unknown endpoint"}, 404)
        except r1ctl.StepError as e:
            return self.send_json({"error": str(e)}, 400)
        except Exception as e:  # keep the server alive for the class
            log("❌ %s" % e)
            return self.send_json({"error": str(e)}, 500)


class ArmHold:
    """One long-lived `r1_arm serve` so the arm stays where the blocks put it between steps."""

    def __init__(self):
        self.p = None
        self.stopping = None

    def send(self, line):
        import subprocess
        if not self.p or self.p.poll() is not None:
            cfg = r1ctl.config()
            self.p = subprocess.Popen([os.path.join(cfg["bin"], "r1_arm"), cfg["iface"], "serve"],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True)
            self.p.stdout.readline()  # "ready"
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()
        while True:
            out = self.p.stdout.readline()
            if not out or out.strip() in ("done",) or out.startswith("error"):
                if out.startswith("error"):
                    raise r1ctl.StepError(out.strip())
                return

    def interrupt(self):
        """Stop key: Ctrl-C the arm process once. It walks home and hands control back by itself.
        A second signal would cut that walk short, and people tap STOP twice."""
        import signal
        if self.p and self.p.poll() is None and self.p is not self.stopping:
            self.stopping = self.p
            self.p.send_signal(signal.SIGINT)

    def release(self):
        if self.p and self.p.poll() is None:
            self.send("release")


ARM = ArmHold()


def upload_sound(handler):
    """Browser sends 16 kHz mono 16-bit PCM, so any file the browser can decode works and the robot needs no ffmpeg."""
    n = int(handler.headers.get("Content-Length") or 0)
    if not 0 < n <= MAX_UPLOAD:
        raise r1ctl.StepError("sound must be under 20 minutes")
    name = clean_name(parse_qs(urlparse(handler.path).query).get("name", [""])[0])
    if not name:
        raise r1ctl.StepError("give the sound a name")
    os.makedirs(SOUNDS, exist_ok=True)
    save_wav(os.path.join(SOUNDS, name + ".wav"), handler.rfile.read(n))
    log("💾 sound saved: %s" % name)
    return {"ok": True, "name": name}


def _voice(handler):
    """Talk button. Mic audio plays once, goes through PLAYER so STOP cuts it, and is not kept."""
    n = int(handler.headers.get("Content-Length") or 0)
    if n > 4 * 1024 * 1024:  # 2 minutes
        raise r1ctl.StepError("that message is too long: keep it under 2 minutes")
    pcm = handler.rfile.read(n)
    fx = "none" if "fx=none" in handler.path else "robot"
    out = r1ctl.robotize(pcm, 16000, fx)
    os.makedirs(r1ctl.CACHE, exist_ok=True)
    PLAYER.stop()
    for old in glob.glob(os.path.join(r1ctl.CACHE, "voice_*.wav")):
        os.remove(old)
    path = os.path.join(r1ctl.CACHE, "voice_%d.wav" % int(time.time() * 1000))
    save_wav(path, out)
    if "live=1" in handler.path and STATE["live"]:
        PLAYER.play(path, "talk")
    handler.send_file(path)


Handler.voice = _voice


def is_armed():
    """Armed by a typed GO. STOP, End and 15 idle minutes clear it, whatever any page thinks."""
    if STATE["armed"] and time.time() - STATE["armed"] > IDLE_DISARM:
        STATE["armed"] = 0
        log("Disarmed: 15 minutes idle")
    return bool(STATE["armed"])


def leaves(steps, depth=0):
    """Every plain step inside a program, through dances, shows, repeats and parallels: (kind, arg)."""
    if depth > 8:
        raise r1ctl.StepError("program nests too deep")
    for s in steps:
        kind, arg = next(iter(s.items()))
        if kind in ("parallel", "random"):
            yield from leaves(arg, depth + 1)
        elif kind == "repeat":
            yield from leaves(arg["steps"], depth + 1)
        elif kind == "dance":
            doc = r1ctl.load_yaml(r1ctl.find_item("dances", arg))
            r1ctl.validate_steps(doc.get("steps"), arg)
            yield from leaves(doc["steps"], depth + 1)
        else:
            yield kind, arg


def fingerprint(name):
    """The move a human watched: its file and every arm file in it. Change any byte and the check is void."""
    h = hashlib.sha1()
    try:
        h.update(open(r1ctl.find_item("dances", name), "rb").read())
        for kind, arg in leaves([{"dance": name}]):
            if kind == "arm_traj":
                h.update(open(r1ctl.find_item("arm", arg if isinstance(arg, str) else arg["file"]), "rb").read())
    except (r1ctl.StepError, OSError):
        h.update(str(name).encode())  # hand tiles and factory moves have no file
    return h.hexdigest()[:16]


def verified_now():
    return {k: v for k, v in verified().items() if v.get("sha") == fingerprint(k)}


def named_parts(step):
    """Move names a step plays, shows unpacked. None if it plays anything else."""
    if "dance" in step:
        subs = r1ctl.load_yaml(r1ctl.find_item("dances", step["dance"])).get("steps", [])
        return named_parts({"repeat": {"steps": subs}}) if all("dance" in x for x in subs) else [step["dance"]]
    if "repeat" in step and all("dance" in x for x in step["repeat"]["steps"]):
        return [n for x in step["repeat"]["steps"] for n in named_parts(x)]
    return None


def cleared(file):
    """Moves built in the app are checked there before saving. The rest must match the file that passed Unitree's body shapes."""
    if file.startswith("u_"):
        return True
    try:
        with open(SAFE) as f:
            good = json.load(f)
        return good.get(file) == hashlib.sha1(open(r1ctl.find_item("arm", file), "rb").read()).hexdigest()[:16]
    except (OSError, ValueError, r1ctl.StepError):
        return False


def gate(step):
    """Last word before the real robot moves. Every page and script comes through here. → the top speed allowed."""
    plain = list(leaves([step]))
    moving = [k for k, _ in plain if k not in QUIET]
    if not moving:
        return False, 1.0
    if not is_armed():
        raise r1ctl.StepError("Not armed. Type GO first. STOP and 15 idle minutes disarm the robot.")
    for kind, arg in plain:
        if kind in NEVER_LIVE:
            raise r1ctl.StepError("not on the real robot: %s" % NEVER_LIVE[kind])
        if kind == "arm_traj":
            a = {"file": arg} if isinstance(arg, str) else arg
            if not cleared(a["file"]):
                raise r1ctl.StepError("%s did not pass the body check, so it cannot run" % a["file"])
            if float(a.get("speed", 1.0)) > 1:
                raise r1ctl.StepError("%s: speed above 1 is not allowed" % a["file"])
    if not set(moving) & SLOWS:
        return True, 1.0  # Unitree's own moves have no slow mode: half speed would only stretch the waits around them
    seen = verified_now()
    parts = named_parts(step)
    return True, 1.0 if parts and all(seen.get(n, {}).get("ok") for n in parts) else 0.5


def run_step(data):
    """Run one step on the robot (live) or just validate + log it (sim)."""
    step = data["step"]
    r1ctl.validate_steps([step], "block")
    live = bool(data.get("live")) and STATE["live"]
    if not live:
        log("🧪 dry-run step (nothing moves): %s" % json.dumps(step, ensure_ascii=False))
        robot = r1ctl.Robot(r1ctl.config(), live=False, log=lambda *a: None)
        if "ai" not in step:
            r1ctl.play_steps(robot, [step])  # catches missing files and unknown poses before the real run
        return {"ok": True, "live": False, "warnings": robot.warnings}
    moving, cap = gate(step)
    if not STATE["busy"].acquire(timeout=0.1):
        raise r1ctl.StepError("robot is busy with another step")
    try:
        robot = r1ctl.Robot(r1ctl.config(), live=True, log=log)
        want = max(0.25, min(1.0, float(data.get("speed", 1.0))))
        robot.speed = min(want, cap)
        if want > cap:
            factory = {k for k, _ in leaves([step])} & {"fsm", "arm_preset"}
            robot.warn("Not yet seen on the real robot, so our part ran at half speed. Unitree's own moves do not slow down"
                       if factory else "Not yet seen on the real robot, so it ran at half speed")
        STATE["robot"] = robot
        if moving:
            if not is_armed():  # STOP landed while this step was on its way in
                raise r1ctl.StepError("Stopped. Type GO to move again.")
            STATE["armed"] = time.time()
        kind, arg = next(iter(step.items()))
        if kind == "arm_pose":
            ARM.send("pose " + " ".join("%.4f" % v for v in arg["q"]) + " %.2f" % arg.get("max_vel", 0.8))
            return {"ok": True, "live": True}
        if kind == "arm_traj":
            a = arg if isinstance(arg, dict) else {"file": arg}
            ARM.send("traj %s %.2f" % (r1ctl.find_item("arm", a["file"]), a.get("speed", 1.0) * robot.speed))
            return {"ok": True, "live": True, "warnings": robot.warnings}
        if kind in ("arm_preset", "fsm", "loco", "dance", "ai"):
            ARM.release()  # factory motions need the arm back
        r1ctl.play_steps(robot, [step])
        return {"ok": True, "live": True, "ai": robot.last_ai, "warnings": robot.warnings,
                "stopped": robot.stopped.is_set()}
    finally:
        STATE["busy"].release()


def own_name(raw):
    """Anything made in the app starts with u_: it can never replace a library move, and deploy leaves it alone."""
    name = "".join(c for c in str(raw or "") if c.isalnum() or c in "_-").lower()
    if not name:
        raise r1ctl.StepError("give it a name")
    return name if name.startswith("u_") else "u_" + name


def save_arm(data):
    """Keyframe timeline from the Joints tab → library/arm/<name>.csv (same format as r1_arm record)."""
    name = own_name(data.get("name"))
    rows = data.get("rows", [])
    if len(rows) < 2:
        raise r1ctl.StepError("needs at least 2 frames")
    path = r1ctl.lib_path("arm", name + ".csv")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("t,lsp,lsr,lsy,le,lwr,rsp,rsr,rsy,re,rwr,waist_yaw,head_pitch,head_yaw\n")
        for r in rows:
            f.write(",".join("%.4f" % float(v) for v in r) + "\n")
    try:
        r1ctl.check_csv(tmp)
    except r1ctl.StepError:
        os.remove(tmp)
        raise
    os.replace(tmp, path)
    log("💾 saved arm/%s (%d frames)" % (name, len(rows)))
    return {"ok": True, "name": name}


def save_dance(data):
    name = own_name(data.get("name"))
    doc = {"kind": "dance", "title": data.get("title", name), "steps": data["steps"]}
    if data.get("emoji"):
        doc["emoji"] = data["emoji"]
    r1ctl.validate_file("dances", doc, name)
    import yaml
    path = r1ctl.lib_path("dances", name + ".yaml")
    with open(path, "w") as f:
        f.write("# made in R1 Studio\n")
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False)
    if data.get("blocks"):
        os.makedirs(os.path.join(HERE, "projects"), exist_ok=True)
        json.dump(data["blocks"], open(os.path.join(HERE, "projects", name + ".json"), "w"))
    log("💾 saved dances/%s" % name)
    return {"ok": True, "name": name}


class QuietHTTPS(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # browsers drop connections at the certificate warning


def start_https(bind, port):
    """Same app over https with a self-made certificate: the browser warns once, then the mic works."""
    d = os.path.join(DATA, "tls")
    cert, key = os.path.join(d, "cert.pem"), os.path.join(d, "key.pem")
    try:
        if not os.path.exists(cert):
            os.makedirs(d, exist_ok=True)
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "3650", "-subj",
                            "/CN=r1-remote", "-keyout", key, "-out", cert], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.chmod(key, 0o600)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        srv = QuietHTTPS((bind, port), Handler)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True, do_handshake_on_connect=False)
    except (OSError, subprocess.CalledProcessError, ssl.SSLError) as e:
        print("   ⚠️ https off, so the Talk button will not work: %s" % e)
        return False
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    STATE["https_port"] = port
    return True


def main():
    signal.signal(signal.SIGINT, signal.default_int_handler)  # started with & or nohup, children would ignore STOP
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="allow driving the real robot (run this on PC2)")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--camera", default=None, help="OpenCV source: 0, a URL or a file")
    ap.add_argument("--joga", default=None, help="r1-joga folder to serve at /joga/ (default: auto-find)")
    ap.add_argument("--pin", default=None, help="every action needs this PIN; STOP never does")
    ap.add_argument("--https-port", type=int, default=8443, help="same app over https, needed for the mic (0 = off)")
    ap.add_argument("--bind", default=None, help="address to listen on (default: this computer only in emulator mode)")
    a = ap.parse_args()
    STATE["live"] = a.live
    STATE["pin"] = a.pin
    STATE["joga"] = find_joga(a.joga)
    bind = a.bind or ("0.0.0.0" if a.live else "127.0.0.1")
    if a.camera is not None:
        try:
            STATE["camera"] = Camera(a.camera)
        except r1ctl.StepError as e:
            print("   ⚠️ camera off: %s" % e)
    try:
        srv = ThreadingHTTPServer((bind, a.port), Handler)
    except OSError as e:
        if e.errno != errno.EADDRINUSE:
            raise
        sys.exit("R1 Remote is already running here, so just reload the page.\n"
                 "To start it fresh: pkill -f server.py, then run this line again.")
    ips = sorted({i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)} | {"127.0.0.1"})
    print("🤖 R1 Studio · %s mode" % ("LIVE ROBOT" if a.live else "SIMULATOR"))
    for ip in ips:
        print("   📱 R1 Remote: http://%s:%d/phone.html" % (ip, a.port))
    if a.https_port and start_https(bind, a.https_port):
        print("   🎙️ With the mic: https://<address above>:%d/phone.html (browser warns once: Advanced, Proceed)" % a.https_port)
    if a.live and not a.pin:
        print("   ⚠️ No PIN: anyone who can reach this address can move the robot. Cable only, or add --pin 4821")
    if a.live:
        print("   Old Studio and the yoga page are switched off here: only R1 Remote drives the real robot.")
        print(r1ctl.SAFETY)
    elif STATE["joga"]:
        print("   🧘 yoga app: http://127.0.0.1:%d/joga/  (%s)" % (a.port, STATE["joga"]))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
