#!/usr/bin/env python3
"""R1 Mac-direct bridge: talk to the Unitree R1 from a Mac over the Ethernet cable, no EDU backpack (PC2).

    ~/r1/.venv-sdk/bin/python ~/r1/studio/mac_bridge.py --iface en16                    # read-only (default)
    ~/r1/.venv-sdk/bin/python ~/r1/studio/mac_bridge.py --iface en16 --allow-commands   # voice / LED / volume possible

Read-only by default: it only subscribes to robot topics and asks the voice service for its volume.
Commands (POST /say, /led, /volume) need BOTH:
  1. the bridge started with --allow-commands, and
  2. an armed token: POST /arm {"go": "GO"} returns it; send it as header X-R1-Arm. It expires after 10 idle minutes.
POST /stop (or /disarm) drops the token at once. Arms, hands and walking are not here on purpose
(first arm_sdk publish while walking locks the R1 in FSM 816 until reboot).

Default address is 127.0.0.1:8090. --bind 0.0.0.0 (phone on the same Wi-Fi) needs --pin; every request
except /stop then needs header X-R1-Pin. R1 Studio talks to this bridge with `server.py --bridge`.
"""
import argparse
import json
import os
import secrets
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8090
ARM_IDLE = 600          # seconds an armed token lives without use
FRESH = 2.0             # a topic is "live" if it spoke within this many seconds
VOLUME_EVERY = 10.0     # GetVolume at most this often
MAX_TEXT = 300

# (topic, idl module, type name) we subscribe to. Read-only.
TOPICS = [
    ("rt/odommodestate", "unitree_go", "SportModeState_"),
    ("rt/lf/odommodestate", "unitree_go", "SportModeState_"),
    ("rt/wirelesscontroller", "unitree_go", "WirelessController_"),
    ("rt/servicestate", "std_msgs", "String_"),
    ("rt/multiplestate", "std_msgs", "String_"),
]


def _r(x, n=3):
    try:
        return [round(float(v), n) for v in x]
    except TypeError:
        return round(float(x), n)


class DdsLink:
    """The real robot over CycloneDDS. Only the three command methods ever send anything that acts."""

    def __init__(self, iface, allow_commands=False):
        self.iface, self.allow = iface, allow_commands
        self.lock = threading.Lock()
        self.seen = {}      # topic -> {"n", "t", "msg"}
        self.discovered = set()
        self.audio = None
        self.error = None

    def start_async(self, every=3.0):
        """Keep trying until the cable's network port exists, so the bridge can be started before plugging in."""
        def loop():
            while self.audio is None:
                try:
                    socket.if_nametoindex(self.iface)
                except OSError:
                    self.error = "%s not found: plug in the robot cable (USB-Ethernet adapter)" % self.iface
                    time.sleep(every)
                    continue
                try:
                    self.start()
                    self.error = None
                    print("✅ DDS up on %s" % self.iface, flush=True)
                except Exception as e:
                    self.error = "DDS start failed on %s: %s" % (self.iface, e)
                    time.sleep(every)
        threading.Thread(target=loop, daemon=True).start()

    def start(self):
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber, ChannelFactory
        import importlib
        ChannelFactoryInitialize(0, self.iface)
        self.subs = []
        for topic, mod, name in TOPICS:
            T = getattr(importlib.import_module("unitree_sdk2py.idl.%s.msg.dds_" % mod), name)
            s = ChannelSubscriber(topic, T)
            s.Init(self._cb(topic), 1)
            self.subs.append(s)
        try:  # which topics have a writer right now (DDS discovery, read-only)
            from cyclonedds.builtin import BuiltinTopicDcpsPublication
            from cyclonedds.sub import DataReader
            dp = getattr(ChannelFactory, "_ChannelFactory__participant")
            self.pubs = DataReader(dp, BuiltinTopicDcpsPublication)
            threading.Thread(target=self._discover, daemon=True).start()
        except Exception as e:  # discovery is a nice-to-have
            self.error = "discovery off: %s" % e
        from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient
        self.audio = AudioClient()
        self.audio.SetTimeout(3.0)
        self.audio.Init()

    def _cb(self, topic):
        def cb(msg):
            with self.lock:
                s = self.seen.setdefault(topic, {"n": 0, "t": 0, "msg": None})
                s["n"] += 1
                s["t"] = time.time()
                s["msg"] = msg
        return cb

    def _discover(self):
        while True:
            try:
                for p in self.pubs.take(N=500):
                    if getattr(p, "topic_name", "").startswith("rt/"):
                        with self.lock:
                            self.discovered.add(p.topic_name)
            except Exception:
                pass
            time.sleep(2)

    def snapshot(self):
        with self.lock:
            return {k: dict(v) for k, v in self.seen.items()}, sorted(self.discovered)

    def get_volume(self):
        if self.audio is None:
            return None
        code, data = self.audio.GetVolume()
        return (data or {}).get("volume") if code == 0 else None

    # ---- the only three calls that act on the robot. Bridge.command() gates them; this is the second lock.
    def _check(self):
        if not self.allow:
            raise PermissionError("commands are off")

    def say(self, text):
        self._check()
        return self.audio.TtsMaker(text, 0)

    def led(self, r, g, b):
        self._check()
        return self.audio.LedControl(r, g, b)

    def set_volume(self, n):
        self._check()
        return self.audio.SetVolume(n)


class Refused(Exception):
    def __init__(self, msg, code=403):
        super().__init__(msg)
        self.code = code


class Bridge:
    def __init__(self, link, allow_commands=False, pin=None, clock=time.time):
        self.link, self.allow, self.pin, self.clock = link, allow_commands, pin, clock
        self.token, self.token_t = None, 0
        self.vol, self.vol_t = None, 0
        self.lock = threading.Lock()
        self.history = []   # last commands, for the log and the tests

    # ------------------------------------------------------------ read
    def state(self):
        now = self.clock()
        seen, discovered = self.link.snapshot()
        topics = {k: {"messages": v["n"], "age_s": round(now - v["t"], 2) if v["t"] else None} for k, v in seen.items()}
        fresh = [k for k, v in seen.items() if v["t"] and now - v["t"] < FRESH]
        connected = bool(fresh)
        out = {"connected": connected, "iface": getattr(self.link, "iface", None),
               "commands_allowed": self.allow, "armed": self.armed(),
               "topics": topics, "topics_seen": len(discovered), "topic_names": discovered,
               "last_update_age_s": min((topics[k]["age_s"] for k in fresh), default=None)}
        odom = (seen.get("rt/odommodestate") or {}).get("msg") or (seen.get("rt/lf/odommodestate") or {}).get("msg")
        if odom is not None:
            out["odom"] = {"mode": getattr(odom, "mode", None), "gait": getattr(odom, "gait_type", None),
                           "position": _r(getattr(odom, "position", [])), "velocity": _r(getattr(odom, "velocity", [])),
                           "yaw_speed": _r(getattr(odom, "yaw_speed", 0)), "body_height": _r(getattr(odom, "body_height", 0)),
                           "rpy": _r(getattr(getattr(odom, "imu_state", None), "rpy", []) or [])}
        rc = (seen.get("rt/wirelesscontroller") or {}).get("msg")
        if rc is not None:
            out["remote"] = {"keys": getattr(rc, "keys", 0), "sticks": _r([rc.lx, rc.ly, rc.rx, rc.ry], 2)}
        for k in ("rt/servicestate", "rt/multiplestate"):
            m = (seen.get(k) or {}).get("msg")
            if m is not None:
                out[k.split("/")[-1]] = str(getattr(m, "data", ""))[:300]
        if connected and now - self.vol_t > VOLUME_EVERY:   # GetVolume is a read
            self.vol_t = now
            try:
                self.vol = self.link.get_volume()
            except Exception as e:
                out["volume_error"] = str(e)
        out["volume"] = self.vol if connected else None
        if getattr(self.link, "error", None):
            out["note"] = self.link.error
        return out

    # ------------------------------------------------------------ arming
    def armed(self):
        return bool(self.token) and self.clock() - self.token_t < ARM_IDLE

    def arm(self, go):
        if not self.allow:
            raise Refused("Commands are off. Start the bridge with --allow-commands.")
        if str(go or "").strip().upper() != "GO":
            raise Refused("type GO to arm", 400)
        with self.lock:
            self.token, self.token_t = secrets.token_hex(12), self.clock()
        print("🟥 bridge armed", flush=True)
        return self.token

    def disarm(self):
        with self.lock:
            had, self.token = self.token, None
        if had:
            print("🟩 bridge disarmed", flush=True)

    # ------------------------------------------------------------ act (gated twice: here and in the link)
    def command(self, kind, data, token):
        if not self.allow:
            raise Refused("Commands are off. Start the bridge with --allow-commands.")
        with self.lock:
            if not (self.armed() and token and secrets.compare_digest(str(token), self.token)):
                raise Refused("Not armed: POST /arm with GO first, then send the token as X-R1-Arm.")
            self.token_t = self.clock()
        if getattr(self.link, "audio", None) is None:
            raise Refused("robot not connected: no DDS link yet", 503)
        if kind == "say":
            text = " ".join(str(data.get("text", "")).split())[:MAX_TEXT]
            if not text:
                raise Refused("nothing to say", 400)
            args = (text,)
            code = self.link.say(text)
        elif kind == "led":
            args = tuple(max(0, min(255, int(data.get(k, 0)))) for k in ("r", "g", "b"))
            code = self.link.led(*args)
        elif kind == "volume":
            args = (max(0, min(100, int(data.get("n", data.get("level", 50))))),)
            code = self.link.set_volume(*args)
            if code == 0:
                self.vol, self.vol_t = args[0], self.clock()
        else:
            raise Refused("unknown command", 404)
        self.history.append((kind, args, code))
        print("🔊 %s %s → %s" % (kind, args, code), flush=True)
        if code != 0:
            raise Refused("robot answered code %s" % code, 502)
        return {"ok": True, "code": code, "kind": kind}


def make_handler(bridge):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send_json(self, obj, code=200):
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def pin_ok(self):
            return not bridge.pin or self.headers.get("X-R1-Pin") == bridge.pin

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/health":
                return self.send_json({"ok": True})
            if not self.pin_ok():
                return self.send_json({"error": "PIN needed"}, 403)
            if path == "/state":
                try:
                    return self.send_json(bridge.state())
                except Exception as e:
                    return self.send_json({"connected": False, "error": str(e)}, 500)
            return self.send_json({"error": "unknown endpoint"}, 404)

        def do_POST(self):
            path = self.path.split("?")[0]
            if path in ("/stop", "/disarm"):   # never needs a PIN: anyone nearby may stop it
                bridge.disarm()
                return self.send_json({"ok": True, "armed": False})
            if not self.pin_ok():
                return self.send_json({"error": "PIN needed"}, 403)
            try:
                n = int(self.headers.get("Content-Length") or 0)
                data = json.loads(self.rfile.read(min(n, 65536)) or b"{}") if n else {}
                if not isinstance(data, dict):
                    raise ValueError("JSON object expected")
                if path == "/arm":
                    return self.send_json({"ok": True, "armed": True, "token": bridge.arm(data.get("go"))})
                if path in ("/say", "/led", "/volume"):
                    return self.send_json(bridge.command(path[1:], data, self.headers.get("X-R1-Arm")))
                return self.send_json({"error": "unknown endpoint"}, 404)
            except Refused as e:
                return self.send_json({"error": str(e)}, e.code)
            except (ValueError, TypeError) as e:
                return self.send_json({"error": "bad request: %s" % e}, 400)
            except Exception as e:
                return self.send_json({"error": str(e)}, 500)
    return H


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--iface", default="en16", help="Mac network port with the robot cable (ifconfig: 192.168.123.x)")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--bind", default="127.0.0.1", help="0.0.0.0 = reachable from the Wi-Fi (needs --pin)")
    ap.add_argument("--pin", default=None, help="every request except /stop needs header X-R1-Pin")
    ap.add_argument("--allow-commands", action="store_true", help="let armed requests use voice, LED and volume")
    a = ap.parse_args(argv)
    if a.bind not in ("127.0.0.1", "localhost") and not a.pin:
        sys.exit("--bind %s opens the bridge to the network: add --pin 4821 (any number you choose)." % a.bind)
    link = DdsLink(a.iface, a.allow_commands)
    link.start_async()
    bridge = Bridge(link, a.allow_commands, a.pin)
    srv = ThreadingHTTPServer((a.bind, a.port), make_handler(bridge))
    print("🤖 R1 Mac bridge · %s · http://%s:%d/state · commands %s" % (
        a.iface, a.bind, a.port, "ALLOWED (arm with GO)" if a.allow_commands else "OFF (read-only)"), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
