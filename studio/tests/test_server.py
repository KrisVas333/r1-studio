"""R1 Remote server, end to end over real HTTP. Fake robot programs stand in for the hardware."""
import json
import os
import shutil
import ssl
import struct
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp()
os.environ["R1_DATA"] = os.path.join(TMP, "data")
import server  # noqa: E402
r1ctl = server.r1ctl
BIN = os.path.join(TMP, "bin")
MARKS = os.path.join(TMP, "ran")
REAL = r1ctl.config
r1ctl.config = lambda: dict(REAL(), bin=BIN, sdk_bin=BIN, iface="eth0")
r1ctl.CACHE = os.path.join(TMP, "cache")


def fake(name, body):
    os.makedirs(BIN, exist_ok=True)
    p = os.path.join(BIN, name)
    with open(p, "w") as f:
        f.write('#!/bin/bash\necho "%s $@" >> %s\n%s\n' % (name, MARKS, body))
    os.chmod(p, 0o755)


def ran():
    if not os.path.exists(MARKS):
        return []
    with open(MARKS) as f:
        return f.read().splitlines()


srv = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def call(path, body=None, headers=None, raw=None, ok=True):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path), data=data, headers=headers or {})
    try:
        out = urllib.request.urlopen(req, timeout=20).read()
    except urllib.error.HTTPError as e:
        if ok:
            raise AssertionError("%s → %s %s" % (path, e.code, e.read()))
        return e.code
    return json.loads(out) if not raw or out[:1] == b"{" else out


def live_on(armed=True):
    server.STATE["live"] = True
    server.STATE["health"] = (0, None)
    if armed:
        call("/api/arm", {"go": "go"})


def seen(name, ok=True, speed=1):
    call("/api/verified", {"name": name, "ok": ok, "speed": speed})


class Base(unittest.TestCase):
    def setUp(self):
        server.STATE.update(live=False, robot=None, pin=None, health=(0, None), armed=0)
        for f in (MARKS, server.VERIFIED):
            if os.path.exists(f):
                os.remove(f)
        for n in ("r1_arm", "r1_hand", "r1_say", "r1_loco_client", "r1_arm_action_example"):
            fake(n, "exit 0")

    def tearDown(self):
        server.PLAYER.stop()


class Emulator(Base):
    def test_status_and_library(self):
        s = call("/api/status")
        self.assertFalse(s["live_allowed"])
        self.assertGreater(len(call("/api/library")["dances"]), 50)

    def test_every_tile_passes_in_test_mode(self):
        for name in call("/api/library")["dances"]:
            r = call("/api/step", {"step": {"dance": name}, "live": False})
            self.assertEqual(r["live"], False, name)
        self.assertEqual(ran(), [], "test mode touched a robot program")

    def test_live_flag_is_ignored_unless_the_server_is_live(self):
        r = call("/api/step", {"step": {"dance": "peekaboo"}, "live": True})
        self.assertFalse(r["live"])
        self.assertEqual(ran(), [])

    def test_unknown_move_is_caught_in_test_mode(self):
        self.assertEqual(call("/api/step", {"step": {"dance": "nope"}, "live": False}, ok=False), 400)

    def test_health_says_emulator(self):
        h = call("/api/health")
        states = {i["id"]: i["state"] for i in h["items"]}
        self.assertEqual(states["robot"], "sim")
        self.assertEqual(states["hand_left"], "sim")


class LiveStop(Base):
    def test_stop_ends_a_dance_at_once_and_opens_the_hands(self):
        live_on()
        fake("r1_arm", "exec sleep 30")
        fake("r1_hand", "sleep 0.1")
        fake("r1_say", "sleep 0.1")
        out, t0 = {}, time.time()
        t = threading.Thread(target=lambda: out.update(call("/api/step", {"step": {"dance": "peekaboo"}, "live": True})))
        t.start()
        time.sleep(0.5)
        call("/api/stop", {})
        t.join(4)
        self.assertFalse(t.is_alive(), "step still running after STOP")
        self.assertLess(time.time() - t0, 3)
        self.assertTrue(out["stopped"])
        time.sleep(0.5)  # the fresh robot's stop commands run in a thread
        log = ran()
        self.assertTrue(any("--stop_move" in l for l in log), log)

    def test_robot_is_usable_again_after_stop(self):
        live_on()
        fake("r1_arm", "exec sleep 30")
        t = threading.Thread(target=lambda: call("/api/step", {"step": {"dance": "peekaboo"}, "live": True}))
        t.start()
        time.sleep(0.4)
        call("/api/stop", {})
        t.join(4)
        fake("r1_arm", "exit 0")
        self.assertEqual(call("/api/step", {"step": {"dance": "found_you"}, "live": True}, ok=False), 400)  # STOP disarmed it
        call("/api/arm", {"go": "GO"})
        self.assertEqual(call("/api/step", {"step": {"dance": "found_you"}, "live": True})["live"], True)

    def test_second_tap_while_moving_is_refused(self):
        live_on()
        fake("r1_arm", "exec sleep 5")
        t = threading.Thread(target=lambda: call("/api/step", {"step": {"dance": "peekaboo"}, "live": True}))
        t.start()
        time.sleep(0.4)
        self.assertEqual(call("/api/step", {"step": {"dance": "found_you"}, "live": True}, ok=False), 400)
        call("/api/stop", {})
        t.join(4)

    def test_no_hands_still_plays_and_reports(self):
        live_on()
        fake("r1_hand", "exit 2")
        r = call("/api/step", {"step": {"dance": "peekaboo"}, "live": True})
        self.assertTrue(r["warnings"])
        self.assertTrue(any(l.startswith("r1_arm") for l in ran()))

    def test_slow_mode_reaches_the_arm_program(self):
        live_on()
        call("/api/step", {"step": {"dance": "peekaboo"}, "live": True, "speed": 0.5})
        self.assertTrue(any(l.startswith("r1_arm") and l.endswith(" 0.5") for l in ran()), ran())

    def test_speed_cannot_exceed_normal(self):
        live_on()
        seen("peekaboo")
        call("/api/step", {"step": {"dance": "peekaboo"}, "live": True, "speed": 5})
        self.assertTrue(any(l.startswith("r1_arm") and l.endswith(" 1.0") for l in ran()), ran())


class Gate(Base):
    """The server has the last word, whatever page or script sends the step."""

    def step(self, step, ok=True, **kw):
        return call("/api/step", dict(step=step, live=True, **kw), ok=ok)

    def test_not_armed_nothing_moves(self):
        live_on(armed=False)
        self.assertEqual(self.step({"dance": "peekaboo"}, ok=False), 400)
        self.assertEqual(self.step({"hand": {"side": "right", "pose": "fist"}}, ok=False), 400)
        self.assertEqual(self.step({"fsm": 601}, ok=False), 400)
        self.assertEqual(ran(), [])

    def test_arming_needs_the_word(self):
        live_on(armed=False)
        self.assertEqual(call("/api/arm", {"go": "yes"}, ok=False), 400)
        self.assertFalse(call("/api/status")["armed"])
        call("/api/arm", {"go": " go "})
        self.assertTrue(call("/api/status")["armed"])

    def test_words_and_lights_need_no_arming(self):
        live_on(armed=False)
        self.assertTrue(self.step({"led": [255, 0, 0]})["live"])
        self.assertTrue(self.step({"wait": 0})["live"])

    def test_stop_and_end_disarm(self):
        for path in ("/api/stop", "/api/end"):
            live_on()
            call(path, {})
            self.assertFalse(call("/api/status")["armed"], path)
            self.assertEqual(self.step({"dance": "peekaboo"}, ok=False), 400, path)

    def test_idle_disarms(self):
        live_on()
        server.STATE["armed"] = time.time() - server.IDLE_DISARM - 1
        self.assertEqual(self.step({"dance": "peekaboo"}, ok=False), 400)
        self.assertEqual(ran(), [])

    def test_unseen_move_runs_at_half_speed_and_says_so(self):
        live_on()
        r = self.step({"dance": "peekaboo"}, speed=1)
        self.assertTrue(any(l.startswith("r1_arm") and l.endswith(" 0.5") for l in ran()), ran())
        self.assertTrue(any("half speed" in w for w in r["warnings"]), r)

    def test_old_pages_send_no_speed_and_still_get_half(self):
        live_on()
        self.step({"dance": "found_you"})
        self.assertTrue(any(l.startswith("r1_arm") and l.endswith(" 0.5") for l in ran()), ran())

    def test_a_no_keeps_it_at_half(self):
        live_on()
        seen("found_you", ok=False)
        self.step({"dance": "found_you"}, speed=1)
        self.assertTrue(any(l.endswith(" 0.5") for l in ran() if l.startswith("r1_arm")), ran())

    def test_show_needs_every_part_seen(self):
        live_on()
        seen("peekaboo")
        show = {"repeat": {"times": 1, "steps": [{"dance": "peekaboo"}, {"dance": "found_you"}]}}
        self.step(show, speed=1)
        self.assertTrue(all(l.endswith(" 0.5") for l in ran() if l.startswith("r1_arm")), ran())
        seen("found_you")
        os.remove(MARKS)
        self.step(show, speed=1)
        self.assertTrue(all(l.endswith(" 1.0") for l in ran() if l.startswith("r1_arm")), ran())

    def test_slow_rerun_keeps_a_full_speed_check(self):
        seen("peekaboo", speed=1)
        seen("peekaboo", speed=0.5)
        self.assertEqual(call("/api/status")["verified"]["peekaboo"]["speed"], 1)

    def test_a_changed_move_must_be_watched_again(self):
        steps = [{"say": "a"}, {"arm_traj": {"file": "m_hello_test"}}]
        arm = r1ctl.lib_path("arm", "m_hello_test.csv")
        shutil.copy(r1ctl.find_item("arm", "m_found_you"), arm)
        self.addCleanup(lambda: os.path.exists(arm) and os.remove(arm))
        name = call("/api/save", {"name": "fp test", "title": "t", "steps": steps})["name"]
        path = r1ctl.lib_path("dances", name + ".yaml")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        seen(name)
        self.assertIn(name, call("/api/status")["verified"])
        with open(arm, "a") as f:
            f.write("9,0,0,0,0,0,0,0,0,0,0,0,0,0\n")
        self.assertNotIn(name, call("/api/status")["verified"])

    def test_saving_can_never_replace_a_library_move(self):
        before = open(r1ctl.find_item("dances", "peekaboo")).read()
        name = call("/api/save", {"name": "peekaboo", "title": "x", "steps": [{"wait": 1}]})["name"]
        path = r1ctl.lib_path("dances", name + ".yaml")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        self.assertEqual(name, "u_peekaboo")
        self.assertEqual(open(r1ctl.find_item("dances", "peekaboo")).read(), before)

    def test_unsafe_kinds_never_run_live(self):
        live_on()
        for bad in ({"arm_pose": {"q": [0] * 13}}, {"loco": "stop_move"}, {"ai": {"prompt": "hi"}},
                    {"parallel": [{"wait": 0}, {"loco": {"cmd": "move", "value": "0 0 0"}}]}):
            self.assertEqual(self.step(bad, ok=False), 400, bad)
        self.assertEqual(ran(), [])

    def test_limp_modes_cannot_be_asked_for(self):
        live_on()
        for mode in (0, 1, 4, 811, 816):
            self.assertEqual(self.step({"fsm": mode}, ok=False), 400, mode)
        self.assertEqual(ran(), [])
        self.assertTrue(self.step({"fsm": 601})["live"])

    def test_an_arm_file_that_failed_the_body_check_is_refused(self):
        live_on()
        self.assertEqual(self.step({"dance": "found_you"})["live"], True)
        keep, server.SAFE = server.SAFE, os.path.join(TMP, "none.json")
        self.addCleanup(lambda: setattr(server, "SAFE", keep))
        os.remove(MARKS)
        self.assertEqual(self.step({"dance": "found_you"}, ok=False), 400)
        self.assertEqual(self.step({"arm_traj": {"file": "m_found_you"}}, ok=False), 400)
        self.assertEqual(ran(), [])

    def test_every_move_we_ship_is_cleared_and_only_yoga_is_not(self):
        out = call("/api/library")["uncleared"]
        self.assertEqual([f for f in out if not f.startswith("joga_")], [])
        self.assertNotIn("joga_l1_tadasana", out)
        self.assertIn("joga_l1_urdhva_hastasana", out)
        self.assertIn("joga_l2_gomukhasana_arms", out)
        self.assertIn("joga_l3_natarajasana", out)

    def test_old_pages_are_closed_on_the_real_robot(self):
        live_on()
        for path in ("/", "/index.html", "/joga/", "/joga"):
            req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path))
            with urllib.request.urlopen(req, timeout=5) as r:
                self.assertTrue(r.geturl().endswith("/phone.html"), path)

    def test_odd_addresses_cannot_reach_the_old_pages(self):
        live_on()
        for path in ("/./", "//index.html", "/%69ndex.html", "/joga//index.html", "/joga/./", "/joga/./index.html",
                     "/joga/index.html/", "/joga/../index.html", "/joga/any.html", "/index.html?x=1"):
            req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path))
            with urllib.request.urlopen(req, timeout=5) as r:
                self.assertTrue(r.geturl().endswith("/phone.html"), path)

    def test_old_pages_stay_open_in_the_emulator(self):
        with urllib.request.urlopen("http://127.0.0.1:%d/" % PORT, timeout=5) as r:
            self.assertTrue(r.geturl().endswith("/"))

    def test_factory_moves_make_no_half_speed_claim(self):
        live_on()
        r = self.step({"fsm": 601}, speed=1)
        self.assertFalse(any("half speed" in w for w in r["warnings"]), r)

    def test_factory_waits_are_not_stretched(self):
        self.assertEqual(self.cap({"fsm": 601}), 1.0)
        self.assertEqual(self.cap({"hand": {"side": "right", "pose": "fist"}}), 0.5)

    def cap(self, step):
        live_on()
        return server.gate(step)[1]

    def test_speed_above_one_is_refused_at_any_depth(self):
        live_on()
        move = {"arm_traj": {"file": "m_cheer", "speed": 4}}
        for step in (move, {"parallel": [move]}, {"repeat": {"times": 2, "steps": [move]}}):
            self.assertEqual(self.step(step, ok=False), 400, step)
        self.assertEqual(ran(), [])

    def test_ending_the_session_mid_move_stops_it(self):
        live_on()
        fake("r1_arm", "exec sleep 30")
        t = threading.Thread(target=lambda: call("/api/step", {"step": {"dance": "peekaboo"}, "live": True}))
        t.start()
        time.sleep(0.4)
        self.assertTrue(call("/api/end", {})["stopped"])
        t.join(4)
        self.assertFalse(t.is_alive(), "move still running after the pill went back to test mode")
        self.assertFalse(call("/api/status")["armed"])

    def test_a_second_stop_leaves_the_walk_home_alone(self):
        """r1_arm skips the walk home on a second signal, and people tap STOP twice."""
        live_on()
        sigs = os.path.join(TMP, "sigs")
        fake("r1_arm", "trap 'echo sig >> %s' INT; for i in 1 2 3 4 5 6 7 8 9 10 11 12; do sleep 0.1; done" % sigs)
        t = threading.Thread(target=lambda: call("/api/step", {"step": {"dance": "peekaboo"}, "live": True}))
        t.start()
        time.sleep(0.4)
        call("/api/stop", {})
        time.sleep(0.15)
        call("/api/stop", {})
        t.join(4)
        self.assertEqual(open(sigs).read().count("sig"), 1)

    def test_the_held_arm_program_gets_one_signal_too(self):
        sent = []

        class Arm:
            def poll(self):
                return None

            def send_signal(self, s):
                sent.append(s)

        hold = server.ArmHold()
        hold.p = Arm()
        hold.interrupt()
        hold.interrupt()
        self.assertEqual(len(sent), 1)
        hold.p = Arm()  # a new arm program can still be stopped
        hold.interrupt()
        self.assertEqual(len(sent), 2)

    def test_mode_816_is_explained(self):
        live_on()
        fake("r1_loco_client", 'echo "current fsm_id: 816"')
        for n in ("r1_hand", "r1_say", "r1_arm"):
            fake(n, 'echo 0 0 0 0 0 0 0 0 0 0 0 0 0')
        h = {i["id"]: i for i in call("/api/health")["items"]}
        self.assertEqual(h["robot"]["state"], "warn")
        self.assertIn("issue 182", h["robot"]["fix"])


class Pin(Base):
    def test_actions_need_the_pin_but_stop_never_does(self):
        server.STATE["pin"] = "4821"
        step = {"step": {"dance": "peekaboo"}, "live": False}
        self.assertEqual(call("/api/step", step, ok=False), 403)
        self.assertEqual(call("/api/step", step, headers={"X-R1-Pin": "0000"}, ok=False), 403)
        self.assertFalse(call("/api/step", step, headers={"X-R1-Pin": "4821"})["live"])
        self.assertTrue(call("/api/stop", {})["ok"])
        self.assertEqual(call("/api/sound_upload?name=x", raw=b"\0\0", ok=False), 403)
        self.assertEqual(call("/api/voice?live=1", raw=b"\0\0", ok=False), 403)


class Sounds(Base):
    def pcm(self, secs=0.5):
        return struct.pack("<%dh" % int(16000 * secs), *([1000] * int(16000 * secs)))

    def test_upload_list_play_stop_delete(self):
        self.assertEqual(call("/api/sound_upload?name=Mano%20daina", raw=self.pcm())["name"], "Mano daina")
        names = {s["name"]: s for s in call("/api/sounds")["sounds"]}
        self.assertEqual(names["Mano daina"]["secs"], 0.5)
        self.assertTrue(names["Mano daina"]["mine"])
        live_on()
        fake("r1_say", "exec sleep 30")
        call("/api/sound_play", {"name": "Mano daina", "live": True})
        time.sleep(0.2)
        self.assertEqual(call("/api/sounds")["playing"], "Mano daina")
        t0 = time.time()
        call("/api/sound_stop", {})
        self.assertLess(time.time() - t0, 2.5)
        self.assertIsNone(call("/api/sounds")["playing"])
        self.assertTrue(call("/api/sound_delete", {"name": "Mano daina"})["ok"])

    def test_big_stop_also_stops_sound(self):
        call("/api/sound_upload?name=a", raw=self.pcm())
        live_on()
        fake("r1_say", "exec sleep 30")
        call("/api/sound_play", {"name": "a", "live": True})
        call("/api/stop", {})
        self.assertIsNone(call("/api/sounds")["playing"])

    def test_test_mode_plays_nothing_on_the_robot(self):
        call("/api/sound_upload?name=b", raw=self.pcm())
        self.assertFalse(call("/api/sound_play", {"name": "b", "live": True})["live"])
        self.assertEqual(ran(), [])

    def test_names_cannot_escape_the_folder(self):
        call("/api/sound_upload?name=../../evil", raw=self.pcm())
        self.assertFalse(os.path.exists(os.path.join(TMP, "evil.wav")))
        self.assertEqual(call("/api/sound_play", {"name": "../../../etc/passwd", "live": False}, ok=False), 400)

    def test_builtin_sounds_cannot_be_deleted(self):
        for s in call("/api/sounds")["sounds"]:
            if not s["mine"]:
                self.assertEqual(call("/api/sound_delete", {"name": s["name"]}, ok=False), 400)
                break


class Talk(Base):
    def pcm(self):
        return struct.pack("<8000h", *([3000] * 8000))

    def test_talk_returns_audio_and_keeps_only_one_file(self):
        a = call("/api/voice?live=0", raw=self.pcm())
        self.assertEqual(a[:4], b"RIFF")
        call("/api/voice?live=0&fx=none", raw=self.pcm())
        import glob
        self.assertEqual(len(glob.glob(os.path.join(r1ctl.CACHE, "voice_*.wav"))), 1)

    def test_talk_reaches_the_speaker_and_stop_cuts_it(self):
        live_on()
        fake("r1_say", "exec sleep 30")
        call("/api/voice?live=1", raw=self.pcm())
        time.sleep(0.2)
        self.assertEqual(server.PLAYER.playing(), "talk")
        call("/api/stop", {})
        self.assertIsNone(server.PLAYER.playing())


class Lights(Base):
    def test_all_green_with_a_healthy_robot(self):
        live_on()
        fake("r1_loco_client", "echo 'current fsm_id: 811'")
        fake("r1_arm", "echo 0 0 0 0 0 0 0 0 0 0 0 0 0")
        fake("r1_hand", "echo 0 0 0 0 0 0")
        fake("r1_say", "echo volume 70")
        h = {i["id"]: i for i in call("/api/health")["items"]}
        for k in ("robot", "arms", "hand_left", "hand_right", "speaker"):
            self.assertEqual(h[k]["state"], "ok", k)
        self.assertIn("811", h["robot"]["note"])

    def test_dead_hands_say_what_to_do(self):
        live_on()
        fake("r1_hand", "exit 2")
        h = {i["id"]: i for i in call("/api/health")["items"]}
        self.assertEqual(h["hand_right"]["state"], "bad")
        self.assertIn("brainco_hand_server", h["hand_right"]["fix"])

    def test_hung_robot_program_cannot_hang_the_page(self):
        live_on()
        fake("r1_arm", "exec sleep 30")
        t0 = time.time()
        h = {i["id"]: i for i in call("/api/health")["items"]}
        self.assertEqual(h["arms"]["state"], "bad")
        self.assertLess(time.time() - t0, 6)

    def test_verified_marks_survive(self):
        call("/api/verified", {"name": "peekaboo", "ok": True})
        self.assertTrue(call("/api/status")["verified"]["peekaboo"]["ok"])

    def test_volume(self):
        live_on()
        self.assertEqual(call("/api/volume", {"level": 300})["level"], 100)
        self.assertTrue(any("volume 100" in l for l in ran()))


class Https(Base):
    def test_app_answers_over_https_and_a_bad_client_does_no_harm(self):
        import socket
        self.assertTrue(server.start_https("127.0.0.1", 18443))
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        s = socket.create_connection(("127.0.0.1", 18443))
        s.sendall(b"not tls at all\r\n\r\n")
        for _ in range(3):
            out = urllib.request.urlopen("https://127.0.0.1:18443/api/status", context=ctx, timeout=5).read()
            self.assertIn(b"live_allowed", out)
        s.close()
        page = urllib.request.urlopen("https://127.0.0.1:18443/phone.html", context=ctx, timeout=5).read()
        self.assertIn(b"R1 Remote", page)


def tearDownModule():
    shutil.rmtree(TMP, True)


class SayNow(Base):
    def test_line_plays_during_a_move(self):
        live_on()
        fake("r1_arm", "exec sleep 30")
        fake("r1_say", "exec sleep 5")
        t = threading.Thread(target=lambda: call("/api/step", {"step": {"dance": "peekaboo"}, "live": True}))
        t.start()
        time.sleep(0.5)
        self.assertTrue(server.STATE["busy"].locked())
        t0 = time.time()
        out = call("/api/say", {"text": "Hello there", "voice": "robot", "live": True})
        self.assertTrue(out["live"])
        self.assertLess(time.time() - t0, 1)
        self.assertEqual(server.PLAYER.playing(), "Hello there")
        call("/api/stop", {})
        t.join(4)
        self.assertFalse(t.is_alive())

    def test_lithuanian_line_with_no_voice_says_why(self):
        live_on()
        real, r1ctl.eleven_wav = r1ctl.eleven_wav, lambda *a, **k: None
        try:
            self.assertEqual(call("/api/say", {"text": "Ačiū", "live": True}, ok=False), 400)
        finally:
            r1ctl.eleven_wav = real

    def test_emulator_never_plays_on_the_robot(self):
        self.assertFalse(call("/api/say", {"text": "Hello", "voice": "robot", "live": True})["live"])


if __name__ == "__main__":
    unittest.main()
