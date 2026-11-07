"""Mac-direct bridge (mac_bridge.py) and its Studio wiring. A fake link stands in for the robot: nothing reaches DDS."""
import json
import os
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import mac_bridge  # noqa: E402


class FakeAudio:
    """Stands in for unitree_sdk2py AudioClient. Records every call."""

    def __init__(self):
        self.calls = []

    def TtsMaker(self, text, speaker):
        self.calls.append(("tts", text, speaker))
        return 0

    def LedControl(self, r, g, b):
        self.calls.append(("led", r, g, b))
        return 0

    def SetVolume(self, n):
        self.calls.append(("setvol", n))
        return 0

    def GetVolume(self):
        self.calls.append(("getvol",))
        return 0, {"volume": 77}


class Odom:
    mode, gait_type, yaw_speed, body_height = 1, 0, 0.0, 0.7
    position, velocity = [0.1, 0.2, 0.0], [0.0, 0.0, 0.0]


class FakeLink(mac_bridge.DdsLink):
    """The real DdsLink class (so its own allow-check is tested) with fake audio and fake topic data."""

    def __init__(self, allow=False, fresh=True):
        super().__init__("fake0", allow)
        self.audio = FakeAudio()
        if fresh:
            self.seen["rt/odommodestate"] = {"n": 500, "t": time.time(), "msg": Odom()}
        self.discovered = {"rt/odommodestate", "rt/api/voice/request"}

    def start(self):
        raise AssertionError("tests never start DDS")


def serve(bridge):
    srv = mac_bridge.ThreadingHTTPServer(("127.0.0.1", 0), mac_bridge.make_handler(bridge))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def call(base, path, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, headers=dict({"Content-Type": "application/json"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


ACTS = ("tts", "led", "setvol")


def acted(link):
    return [c for c in link.audio.calls if c[0] in ACTS]


class BridgeTests(unittest.TestCase):
    def test_import_needs_no_sdk(self):
        self.assertNotIn("unitree_sdk2py", sys.modules)

    def test_state_read_only(self):
        link = FakeLink()
        s = mac_bridge.Bridge(link).state()
        self.assertTrue(s["connected"])
        self.assertEqual(s["odom"]["mode"], 1)
        self.assertEqual(s["volume"], 77)
        self.assertEqual(s["topics_seen"], 2)
        self.assertFalse(s["commands_allowed"])
        self.assertEqual(acted(link), [])

    def test_state_not_connected_when_stale(self):
        link = FakeLink(fresh=False)
        link.seen["rt/odommodestate"] = {"n": 3, "t": time.time() - 30, "msg": Odom()}
        s = mac_bridge.Bridge(link).state()
        self.assertFalse(s["connected"])
        self.assertIsNone(s["volume"])
        self.assertEqual(link.audio.calls, [])  # no GetVolume when the robot is silent

    def test_volume_read_is_cached(self):
        link = FakeLink()
        b = mac_bridge.Bridge(link)
        b.state(), b.state(), b.state()
        self.assertEqual(link.audio.calls.count(("getvol",)), 1)

    def test_default_refuses_every_command(self):
        link = FakeLink()
        srv, base = serve(mac_bridge.Bridge(link))
        for path, body in (("/say", {"text": "hi"}), ("/led", {"r": 255}), ("/volume", {"n": 10}), ("/arm", {"go": "GO"})):
            code, out = call(base, path, body)
            self.assertEqual(code, 403, path)
            self.assertIn("--allow-commands", out["error"])
        self.assertEqual(acted(link), [])
        srv.shutdown(); srv.server_close()

    def test_allowed_but_not_armed_refuses(self):
        link = FakeLink(allow=True)
        srv, base = serve(mac_bridge.Bridge(link, allow_commands=True))
        code, out = call(base, "/say", {"text": "hi"})
        self.assertEqual(code, 403)
        self.assertTrue(out["error"].startswith("Not armed"))
        code, out = call(base, "/say", {"text": "hi"}, {"X-R1-Arm": "guess"})
        self.assertEqual(code, 403)
        self.assertEqual(call(base, "/arm", {"go": "nope"})[0], 400)
        self.assertEqual(acted(link), [])
        srv.shutdown(); srv.server_close()

    def test_armed_commands_reach_the_fake(self):
        link = FakeLink(allow=True)
        srv, base = serve(mac_bridge.Bridge(link, allow_commands=True))
        code, out = call(base, "/arm", {"go": "go"})
        self.assertEqual(code, 200)
        h = {"X-R1-Arm": out["token"]}
        self.assertEqual(call(base, "/say", {"text": "  Hello\n kids  "}, h)[0], 200)
        self.assertEqual(call(base, "/led", {"r": 300, "g": -5, "b": 40}, h)[0], 200)
        self.assertEqual(call(base, "/volume", {"n": 150}, h)[0], 200)
        self.assertEqual(call(base, "/say", {"text": "   "}, h)[0], 400)
        self.assertEqual(acted(link), [("tts", "Hello kids", 0), ("led", 255, 0, 40), ("setvol", 100)])
        # STOP drops the token at once
        self.assertEqual(call(base, "/stop", {})[0], 200)
        self.assertEqual(call(base, "/say", {"text": "again"}, h)[0], 403)
        self.assertEqual(len(acted(link)), 3)
        srv.shutdown(); srv.server_close()

    def test_token_expires(self):
        now = [1000.0]
        link = FakeLink(allow=True)
        b = mac_bridge.Bridge(link, allow_commands=True, clock=lambda: now[0])
        tok = b.arm("GO")
        now[0] += mac_bridge.ARM_IDLE + 1
        with self.assertRaises(mac_bridge.Refused):
            b.command("say", {"text": "late"}, tok)
        self.assertEqual(acted(link), [])

    def test_link_has_its_own_lock(self):
        link = FakeLink(allow=False)
        b = mac_bridge.Bridge(link, allow_commands=True)  # even if the bridge gate is wrongly open
        tok = b.arm("GO")
        with self.assertRaises(PermissionError):
            b.command("say", {"text": "hi"}, tok)
        self.assertEqual(acted(link), [])

    def test_pin(self):
        link = FakeLink(allow=True)
        srv, base = serve(mac_bridge.Bridge(link, allow_commands=True, pin="4821"))
        self.assertEqual(call(base, "/state")[0], 403)
        self.assertEqual(call(base, "/state", headers={"X-R1-Pin": "4821"})[0], 200)
        self.assertEqual(call(base, "/arm", {"go": "GO"})[0], 403)
        self.assertEqual(call(base, "/stop", {})[0], 200)  # STOP never needs a PIN
        self.assertEqual(call(base, "/health")[0], 200)
        srv.shutdown(); srv.server_close()

    def test_no_robot_yet(self):
        link = FakeLink(allow=True, fresh=False)
        link.audio, link.error = None, "fake0 not found: plug in the robot cable (USB-Ethernet adapter)"
        b = mac_bridge.Bridge(link, allow_commands=True)
        s = b.state()
        self.assertFalse(s["connected"])
        self.assertIn("plug in", s["note"])
        with self.assertRaises(mac_bridge.Refused) as e:
            b.command("say", {"text": "hi"}, b.arm("GO"))
        self.assertEqual(e.exception.code, 503)

    def test_waits_for_missing_port(self):
        link = mac_bridge.DdsLink("nosuchport0")
        link.start = lambda: self.fail("must not start DDS without the port")
        link.start_async(every=0.05)
        time.sleep(0.2)
        self.assertIn("nosuchport0 not found", link.error)

    def test_open_bind_needs_pin(self):
        with self.assertRaises(SystemExit):
            mac_bridge.main(["--bind", "0.0.0.0"])


class StudioWiringTests(unittest.TestCase):
    """server.py --bridge: the Studio speaks and reads state through a bridge that runs on a fake link."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("R1_DATA", os.path.join(os.environ.get("TMPDIR", "/tmp"), "r1-bridge-test"))
        import server
        cls.server = server
        cls.link = FakeLink(allow=True)
        cls.bsrv, cls.base = serve(mac_bridge.Bridge(cls.link, allow_commands=True))
        cls.ssrv = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.sbase = "http://127.0.0.1:%d" % cls.ssrv.server_address[1]
        threading.Thread(target=cls.ssrv.serve_forever, daemon=True).start()

    def setUp(self):
        self.server.STATE.update(bridge=self.base, bridge_token=None, live=False, pin=None, armed=0)
        self.link.audio.calls.clear()

    def tearDown(self):
        self.server.STATE.update(bridge=None, bridge_token=None)

    def test_status_reports_mode(self):
        self.assertEqual(call(self.sbase, "/api/status")[1]["mode"], "mac")
        self.server.STATE["bridge"] = None
        self.assertEqual(call(self.sbase, "/api/status")[1]["mode"], "sim")

    def test_state_proxy(self):
        code, s = call(self.sbase, "/api/bridge/state")
        self.assertEqual(code, 200)
        self.assertTrue(s["bridge"] and s["connected"])

    def test_dead_bridge_is_not_a_crash(self):
        self.server.STATE["bridge"] = "http://127.0.0.1:9"
        code, s = call(self.sbase, "/api/bridge/state")
        self.assertEqual(code, 200)
        self.assertFalse(s["bridge"])
        code, out = call(self.sbase, "/api/say", {"text": "hi", "voice": "robot"})
        self.assertEqual(code, 400)
        self.assertIn("bridge not running", out["error"])

    def test_robot_voice_needs_go_then_reaches_robot(self):
        code, out = call(self.sbase, "/api/say", {"text": "hello", "voice": "robot"})
        self.assertEqual(code, 400)
        self.assertTrue(out["error"].startswith("Not armed"))
        self.assertEqual(acted(self.link), [])
        self.assertEqual(call(self.sbase, "/api/arm", {"go": "GO"})[1]["bridge_armed"], True)
        code, out = call(self.sbase, "/api/say", {"text": "hello", "voice": "robot"})
        self.assertEqual((code, out.get("via")), (200, "bridge"))
        self.assertEqual(acted(self.link), [("tts", "hello", 0)])
        call(self.sbase, "/api/stop", {})
        time.sleep(0.3)
        self.assertEqual(call(self.sbase, "/api/say", {"text": "again", "voice": "robot"})[0], 400)

    def test_kris_voice_stays_on_the_mac(self):
        call(self.sbase, "/api/arm", {"go": "GO"})
        code, out = call(self.sbase, "/api/say", {"text": "labas", "voice": "eleven"})
        self.assertEqual((code, out.get("live")), (200, False))
        self.assertEqual(acted(self.link), [])

    def test_led_and_volume_via_studio(self):
        self.assertEqual(call(self.sbase, "/api/bridge/led", {"r": 0, "g": 0, "b": 255})[0], 400)  # not armed
        call(self.sbase, "/api/bridge/arm", {"go": "GO"})
        self.assertEqual(call(self.sbase, "/api/bridge/led", {"r": 0, "g": 0, "b": 255})[0], 200)
        self.assertEqual(call(self.sbase, "/api/volume", {"level": 60})[1]["via"], "bridge")
        self.assertEqual(acted(self.link), [("led", 0, 0, 255), ("setvol", 60)])

    def test_bridge_endpoints_off_without_bridge(self):
        self.server.STATE["bridge"] = None
        self.assertEqual(call(self.sbase, "/api/bridge/say", {"text": "x"})[0], 400)
        self.assertEqual(call(self.sbase, "/api/say", {"text": "x", "voice": "robot"})[1].get("live"), False)
        self.assertEqual(acted(self.link), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
