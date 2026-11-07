"""Builds the shareable R1 Remote demo: one HTML file, no server, no robot.

The same phone.html, with fetch() answered from data packed into the page. Moves, voice lines and effects
come from a throwaway emulator server, so the demo always shows what the app really has.
Run:  ~/r1/sim/.venv/bin/python tools/build_demo.py <out.html>
"""
import base64
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.dirname(HERE)
WEB = os.path.join(STUDIO, "web")
R1 = os.path.dirname(STUDIO)
ESBUILD = os.path.expanduser("~/promo-video/node_modules/.bin/esbuild")
PORT = 8191
LIMIT = 15.9 * 1024 * 1024


def get(path):
    return urllib.request.urlopen("http://127.0.0.1:%d%s" % (PORT, path), timeout=30).read()


def mp3(wav_bytes, kbps):
    """→ a data: URI. Voice stays at 16 kHz mono, so a low bitrate is enough."""
    with tempfile.TemporaryDirectory() as t:
        a, b = os.path.join(t, "a.wav"), os.path.join(t, "b.mp3")
        with open(a, "wb") as f:
            f.write(wav_bytes)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a, "-b:a", "%dk" % kbps, b], check=True)
        return "data:audio/mpeg;base64," + base64.b64encode(open(b, "rb").read()).decode()


def said(steps, out):
    for s in steps:
        k, a = next(iter(s.items()))
        if k == "say":
            out.append(a["text"] if isinstance(a, dict) else a)
        elif k in ("parallel", "random"):
            said(a, out)
        elif k == "repeat":
            said(a["steps"], out)
    return out


def arm_files(steps, out):
    for s in steps:
        k, a = next(iter(s.items()))
        if k == "arm_traj":
            out.add(a if isinstance(a, str) else a["file"])
        elif k in ("parallel", "random"):
            arm_files(a, out)
        elif k == "repeat":
            arm_files(a["steps"], out)
    return out


def collect():
    lib = json.loads(get("/api/library"))
    sounds = [s for s in json.loads(get("/api/sounds"))["sounds"] if s["secs"] <= 15]
    arm = {}
    for d in lib["dances"].values():
        for f in arm_files(d["steps"], set()):
            arm[f] = json.loads(get("/api/arm/" + urllib.parse.quote(f)))
    quick = json.load(open(os.path.join(WEB, "lines.json")))["quick"]
    lines = dict.fromkeys(quick + [t for d in lib["dances"].values() for t in said(d["steps"], [])])
    voices = {}
    for t in lines:
        for fx in ("robot", "none"):
            try:
                voices[t + "|" + fx] = mp3(get("/api/tts?" + urllib.parse.urlencode({"text": t, "fx": fx})), 24)
            except urllib.error.HTTPError:
                pass
    fx = {s["name"]: mp3(get("/api/sound?" + urllib.parse.urlencode({"name": s["name"]})), 40) for s in sounds}
    return lib, arm, sounds, quick, voices, fx


SHIM = """
(() => {
  const D = %s, real = window.fetch.bind(window);
  const ok = (body) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  const bad = (msg) => new Response(JSON.stringify({ error: msg }), { status: 400, headers: { "Content-Type": "application/json" } });
  const unzip = async (b64) => {
    const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    return new Response(new Blob([bin]).stream().pipeThrough(new DecompressionStream("gzip")));
  };
  window.R1_DEMO = {
    audio(path) {
      const u = new URL(path, "http://x"), t = u.searchParams.get("text"), n = u.searchParams.get("name");
      if (n) return D.fx[n] || "";
      return D.voices[t + "|" + (u.searchParams.get("fx") || "robot")] || D.voices[t + "|robot"] || "";
    },
  };
  window.fetch = async (input, opt) => {
    const path = String(input.url || input);
    if (path.endsWith("r1.bin")) return unzip(D.bin);
    if (path.endsWith("r1.json")) return ok(D.model);
    if (path.endsWith("lines.json")) return ok({ quick: D.quick });
    if (path.endsWith("poses.json")) return ok(D.poses);
    if (path.startsWith("/api/arm/")) { const f = decodeURIComponent(path.slice(9)); return D.arm[f] ? ok(D.arm[f]) : bad("no such move"); }
    if (path === "/api/library") return ok(D.lib);
    if (path === "/api/status") return ok({ live_allowed: false, camera: false, pin: false, https_port: null, verified: {}, playing: null });
    if (path === "/api/health") return ok({ items: [["robot", "Robot"], ["arms", "Arms"], ["hand_left", "Left hand"], ["hand_right", "Right hand"], ["speaker", "Robot speaker"], ["camera", "Camera"]].map(([id, label]) => ({ id, label, state: "sim", note: "Demo: no robot here" })), volume: 70, camera_devices: [] });
    if (path === "/api/sounds") return ok({ sounds: D.sounds, playing: null });
    if (path === "/api/say" || path === "/api/step" || path === "/api/stop" || path === "/api/end" || path === "/api/sound_stop") return ok({ ok: true, live: false, warnings: [] });
    if (path === "/api/volume") return ok({ ok: true, live: false, level: JSON.parse(opt.body).level });
    if (path.startsWith("/api/")) return bad("This works in the app connected to the robot");
    return real(input, opt);
  };
})();
"""


def main():
    out = sys.argv[1]
    env = dict(os.environ, R1_DATA=tempfile.mkdtemp())
    srv = subprocess.Popen([sys.executable, os.path.join(STUDIO, "server.py"), "--port", str(PORT), "--https-port", "0"],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                get("/api/status")
                break
            except OSError:
                time.sleep(0.1)
        lib, arm, sounds, quick, voices, fx = collect()
    finally:
        srv.terminate()
        shutil.rmtree(env["R1_DATA"], ignore_errors=True)

    html = open(os.path.join(WEB, "phone.html"), encoding="utf-8").read()
    css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    body = re.search(r"<body>(.*?)<script type=\"module\">", html, re.S).group(1)
    code = re.search(r"<script type=\"module\">(.*?)</script>", html, re.S).group(1)
    r = subprocess.run([ESBUILD, "--bundle", "--format=iife", "--minify", "--target=es2020", "--log-level=warning",
                        "--alias:three=" + os.path.join(WEB, "vendor", "three.module.js"),
                        "--loader=js", "--charset=utf8"], input=code.encode(), capture_output=True, cwd=WEB)
    if r.returncode:
        sys.exit(r.stderr.decode())
    bundle = r.stdout.decode()
    data = {"lib": lib, "arm": arm, "sounds": sounds, "quick": quick, "voices": voices, "fx": fx,
            "poses": json.load(open(os.path.join(WEB, "poses.json"))),
            "model": json.load(open(os.path.join(WEB, "model", "r1.json"))),
            "bin": base64.b64encode(gzip.compress(open(os.path.join(WEB, "model", "r1.bin"), "rb").read(), 9)).decode()}
    extra = ":root{color-scheme:light}header{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}.tabs{margin:0 -16px;padding:0 16px}main{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}"
    page = ("<title>R1 Remote Demo</title>\n<style>%s\n%s</style>\n%s\n<script>%s</script>\n<script>%s</script>\n"
            % (css, extra, body, SHIM % json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
               bundle.replace("</script", "<\\/script")))
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    size = os.path.getsize(out)
    print("%s  %.1f MB  %d moves · %d arm files · %d voice clips · %d effects" % (out, size / 1048576, len(lib["dances"]), len(arm), len(voices), len(fx)))
    if size > LIMIT:
        sys.exit("too big for an artifact")


if __name__ == "__main__":
    main()
