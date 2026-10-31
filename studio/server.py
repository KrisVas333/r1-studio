#!/usr/bin/env python3
"""R1 Studio server — serves the browser app and runs block programs through r1ctl.

    python3 server.py                 # simulator only (Mac or robot), http://localhost:8080
    python3 server.py --live          # on the robot's PC2: blocks can drive the real R1
    python3 server.py --camera 0      # stream an OpenCV camera to the app (robot or USB cam)
    python3 server.py --joga ~/r1-kit/r1-joga   # also serve the R1 yoga app at /joga/ (auto-found if omitted)

Only Python stdlib + PyYAML (+ OpenCV for --camera). Open the printed address in Chrome.
"""
import argparse
import json
import os
import socket
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.realpath(__file__))
WEB = os.path.join(HERE, "web")
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "r1ctl"))
import r1ctl  # noqa: E402

STATE = {"live": False, "robot": None, "log": [], "busy": threading.Lock(), "camera": None, "joga": None}


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
            "emotions": list(r1ctl.EMOTIONS)}


class Camera:
    """Background OpenCV grabber → latest JPEG for the MJPEG endpoint."""

    def __init__(self, source):
        import cv2
        self.cv2, self.jpeg = cv2, None
        self.cap = cv2.VideoCapture(int(source) if str(source).isdigit() else source)
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while True:
            ok, frame = self.cap.read()
            if ok:
                self.jpeg = self.cv2.imencode(".jpg", frame, [self.cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()
            else:
                time.sleep(0.5)
            time.sleep(1 / 20)


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
        if self.path == "/api/status":
            cfg = r1ctl.config()
            return self.send_json({
                "live_allowed": STATE["live"], "camera": STATE["camera"] is not None, "iface": cfg["iface"],
                "ai_key": bool(r1ctl.read_secret("ANTHROPIC_API_KEY", "~/.config/anthropic/api_key")),
                "eleven": bool(cfg.get("eleven_voice")) and bool(r1ctl.read_secret("ELEVENLABS_API_KEY", "~/.config/elevenlabs/key")), "host": socket.gethostname()})
        if self.path == "/api/library":
            return self.send_json(library())
        if self.path.startswith("/api/arm/"):  # noqa: E501 (recorded / keyframed arm moves)
            try:
                return self.send_json(arm_csv(self.path.split("/")[-1]))
            except r1ctl.StepError as e:
                return self.send_json({"error": str(e)}, 404)
        if self.path.startswith("/api/tts?"):
            from urllib.parse import parse_qs, urlparse
            text = parse_qs(urlparse(self.path).query).get("text", [""])[0][:400]
            path = r1ctl.eleven_wav(r1ctl.config(), text) if text else None
            if not path:
                return self.send_json({"error": "no ElevenLabs key or eleven_voice"}, 404)
            data = open(path, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.startswith("/api/log"):
            since = float(self.path.split("since=")[-1]) if "since=" in self.path else 0
            return self.send_json([e for e in STATE["log"] if e["t"] > since])
        if self.path == "/api/camera.mjpg":
            if not STATE["camera"]:
                return self.send_json({"error": "no camera on server"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    j = STATE["camera"].jpeg
                    if j:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + j + b"\r\n")
                    time.sleep(1 / 15)
            except (BrokenPipeError, ConnectionResetError):
                return
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/voice"):
            return self.voice()
        try:
            data = self.body()
            if self.path == "/api/step":
                return self.send_json(run_step(data))
            if self.path == "/api/stop":
                r = STATE["robot"]
                if r:
                    r.stopped.set()
                    threading.Thread(target=r.safe_stop, daemon=True).start()
                if STATE["live"]:
                    ARM.interrupt()
                log("🛑 STOP from Studio")
                return self.send_json({"ok": True})
            if self.path == "/api/end":
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
        """Stop key: Ctrl-C the arm process, it ramps control back to the robot itself."""
        import signal
        if self.p and self.p.poll() is None:
            self.p.send_signal(signal.SIGINT)

    def release(self):
        if self.p and self.p.poll() is None:
            self.send("release")


ARM = ArmHold()


def _voice(handler):
    import wave
    n = int(handler.headers.get("Content-Length") or 0)
    pcm = handler.rfile.read(n)
    fx = "none" if "fx=none" in handler.path else "robot"
    out = r1ctl.robotize(pcm, 16000, fx)
    os.makedirs(r1ctl.CACHE, exist_ok=True)
    path = os.path.join(r1ctl.CACHE, "voice_%d.wav" % int(time.time() * 1000))
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(out)
    if "live=1" in handler.path and STATE["live"]:
        threading.Thread(target=lambda: r1ctl.Robot(r1ctl.config(), live=True, log=log).run(
            [os.path.join(r1ctl.config()["bin"], "r1_say"), r1ctl.config()["iface"], "wav", path]), daemon=True).start()
    data = open(path, "rb").read()
    handler.send_response(200)
    handler.send_header("Content-Type", "audio/wav")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


Handler.voice = _voice


def run_step(data):
    """Run one step on the robot (live) or just validate + log it (sim)."""
    step = data["step"]
    r1ctl.validate_steps([step], "block")
    live = bool(data.get("live")) and STATE["live"]
    if not live:
        log("🧪 dry-run step (nothing moves): %s" % json.dumps(step, ensure_ascii=False))
        return {"ok": True, "live": False}
    if not STATE["busy"].acquire(timeout=0.1):
        raise r1ctl.StepError("robot is busy with another step")
    try:
        robot = r1ctl.Robot(r1ctl.config(), live=True, log=log)
        STATE["robot"] = robot
        kind, arg = next(iter(step.items()))
        if kind == "arm_pose":
            ARM.send("pose " + " ".join("%.4f" % v for v in arg["q"]) + " %.2f" % arg.get("max_vel", 0.8))
            return {"ok": True, "live": True}
        if kind == "arm_traj":
            a = arg if isinstance(arg, dict) else {"file": arg}
            ARM.send("traj %s %.2f" % (r1ctl.find_item("arm", a["file"]), a.get("speed", 1.0)))
            return {"ok": True, "live": True}
        if kind in ("arm_preset", "fsm", "loco", "dance", "ai"):
            ARM.release()  # factory motions need the arm back
        r1ctl.play_steps(robot, [step])
        return {"ok": True, "live": True, "ai": robot.last_ai}
    finally:
        STATE["busy"].release()


def save_arm(data):
    """Keyframe timeline from the Joints tab → library/arm/<name>.csv (same format as r1_arm record)."""
    name = "".join(c for c in data.get("name", "") if c.isalnum() or c in "_-").lower()
    rows = data.get("rows", [])
    if not name or len(rows) < 2:
        raise r1ctl.StepError("needs a name and at least 2 keyframes")
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
    name = "".join(c for c in data.get("name", "") if c.isalnum() or c in "_-").lower()
    if not name:
        raise r1ctl.StepError("give the program a name")
    doc = {"kind": "dance", "title": data.get("title", name), "steps": data["steps"]}
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="allow driving the real robot (run this on PC2)")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--camera", default=None, help="OpenCV source: 0, a URL or a file")
    ap.add_argument("--joga", default=None, help="r1-joga folder to serve at /joga/ (default: auto-find)")
    a = ap.parse_args()
    STATE["live"] = a.live
    STATE["joga"] = find_joga(a.joga)
    if a.camera is not None:
        STATE["camera"] = Camera(a.camera)
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), Handler)
    ips = sorted({i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)} | {"127.0.0.1"})
    print("🤖 R1 Studio · %s mode" % ("LIVE ROBOT" if a.live else "SIMULATOR"))
    for ip in ips:
        print("   open  http://%s:%d" % (ip, a.port))
    if STATE["joga"]:
        print("   🧘 yoga app: http://<address above>:%d/joga/  (%s)" % (a.port, STATE["joga"]))
    else:
        print("   🧘 yoga app: not found (copy r1-joga to ~/r1-kit/r1-joga or pass --joga <dir>)")
    if a.live:
        print(r1ctl.SAFETY)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
