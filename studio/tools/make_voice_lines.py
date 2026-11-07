"""Makes every spoken line ahead of time, so the robot speaks with no internet.
Run on the Mac (needs the ElevenLabs key): ~/r1/sim/.venv/bin/python studio/tools/make_voice_lines.py
Files land in r1ctl/cache; deploy.sh copies them to the robot."""
import glob
import json
import os
import re
import sys

R1 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(R1, "r1ctl"))
import r1ctl  # noqa: E402

cfg = r1ctl.config()
moves = {}
for p in glob.glob(os.path.join(r1ctl.LIB, "dances", "*.yaml")):
    def walk(steps):
        for s in steps:
            k, a = next(iter(s.items()))
            if k == "say":
                moves[a["text"] if isinstance(a, dict) else a] = 1
            elif k in ("parallel", "random"):
                walk(a)
            elif k == "repeat":
                walk(a["steps"])
    walk(r1ctl.load_yaml(p).get("steps", []))
quick = json.load(open(os.path.join(R1, "studio", "web", "lines.json")))["quick"]
lt = [t for t in list(moves) + quick if not t.isascii()] + ["Viso gero!", "Dar kartą?"]
jobs = [(t, "robot") for t in dict.fromkeys(list(moves) + quick)] + [(t, "none") for t in dict.fromkeys(lt)]
before = set(os.listdir(r1ctl.CACHE))
bad = 0
for text, fx in jobs:
    try:
        if not r1ctl.eleven_wav(cfg, text, fx=fx):
            bad += 1
            print("no voice:", text)
    except Exception as e:  # keep going, report at the end; the error text never holds the key
        bad += 1
        print("failed:", text, "·", type(e).__name__, getattr(e, "code", ""))
print("%d lines · %d new files · %d failed" % (len(jobs), len(set(os.listdir(r1ctl.CACHE)) - before), bad))
