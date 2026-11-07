import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import r1ctl  # noqa: E402


def robot():
    cfg = r1ctl.config()
    return r1ctl.Robot(cfg, live=False, log=lambda *a: None)


def load_skill(name):
    import importlib.util
    p = os.path.join(r1ctl.LIB, "vision", name, "skill.py")
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Library(unittest.TestCase):
    def test_every_shipped_file_validates(self):
        for kind in ("dances", "hands", "events"):
            d = os.path.join(r1ctl.LIB, kind)
            for fn in os.listdir(d):
                r1ctl.validate_file(kind, r1ctl.load_yaml(os.path.join(d, fn)), fn)
        r1ctl.check_csv(os.path.join(r1ctl.LIB, "arm", "wave_demo.csv"))

    def test_every_dance_plays_in_dry_run(self):
        for fn in os.listdir(os.path.join(r1ctl.LIB, "dances")):
            r = robot()
            r1ctl.play_dance(r, os.path.splitext(fn)[0])
            self.assertTrue(r.history, fn)

    def test_bad_steps_rejected(self):
        bad = [
            [{"jump": 1}],
            [{"loco": "damp"}],
            [{"hand": {"side": "right", "q": [0, 0, 0, 0, 0, 2]}}],
            [{"arm_pose": {"q": [0, 1]}}],
            [{"wait": 999}],
        ]
        for steps in bad:
            with self.assertRaises(r1ctl.StepError):
                r1ctl.validate_steps(steps)

    def test_hand_clamps_and_both_sides(self):
        r = robot()
        r.hand("both", [2, -1, 0.5, 0.5, 0.5, 0.5])
        self.assertEqual(len(r.history), 2)
        for argv in r.history:
            self.assertEqual(argv[3:9], [1.0, 0.0, 0.5, 0.5, 0.5, 0.5])


class StopAndFaults(unittest.TestCase):
    """Real child processes with fake robot programs: the same path as live mode, no robot."""

    def setUp(self):
        import tempfile as tf
        self.d = tf.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.marks = os.path.join(self.d, "ran")

    def fake(self, name, body):
        p = os.path.join(self.d, name)
        with open(p, "w") as f:
            f.write("#!/bin/bash\necho %s >> %s\n%s\n" % (name, self.marks, body))
        os.chmod(p, 0o755)

    def robot(self):
        cfg = dict(r1ctl.config(), bin=self.d, sdk_bin=self.d)
        r = r1ctl.Robot(cfg, live=True, log=lambda *a: None)
        return r

    def ran(self):
        return open(self.marks).read().split() if os.path.exists(self.marks) else []

    def test_stop_interrupts_a_running_dance_and_nothing_follows(self):
        import threading
        import time
        self.fake("r1_arm", "exec sleep 30")
        self.fake("r1_hand", "exit 0")
        r = self.robot()
        steps = [{"arm_pose": {"q": [0] * 13}}, {"hand": {"side": "right", "pose": "open"}}, {"wait": 30}]
        t = threading.Thread(target=r1ctl.play_steps, args=(r, steps))
        t0 = time.time()
        t.start()
        time.sleep(0.4)
        r.abort()
        t.join(5)
        self.assertFalse(t.is_alive(), "dance kept running after STOP")
        self.assertLess(time.time() - t0, 3)
        self.assertEqual(self.ran(), ["r1_arm"], "a step ran after STOP")

    def test_stop_during_a_wait(self):
        import threading
        import time
        r = self.robot()
        t = threading.Thread(target=r1ctl.play_steps, args=(r, [{"wait": 30}]))
        t.start()
        time.sleep(0.2)
        r.abort()
        t.join(2)
        self.assertFalse(t.is_alive())

    def test_stop_reaches_both_sides_of_a_parallel_step(self):
        import threading
        import time
        self.fake("r1_arm", "exec sleep 30")
        self.fake("r1_hand", "exec sleep 30")
        r = self.robot()
        step = {"parallel": [{"arm_pose": {"q": [0] * 13}}, {"hand": {"side": "both", "pose": "open"}}]}
        t = threading.Thread(target=r1ctl.play_steps, args=(r, [step]))
        t.start()
        time.sleep(0.4)
        r.abort()
        t.join(4)
        self.assertFalse(t.is_alive())

    def test_missing_hands_warn_but_arms_finish(self):
        self.fake("r1_arm", "exit 0")
        self.fake("r1_hand", "exit 2")
        r = self.robot()
        r1ctl.play_steps(r, [{"parallel": [{"arm_pose": {"q": [0] * 13}}, {"hand": {"side": "both", "pose": "open"}}]}])
        self.assertIn("r1_arm", self.ran())
        self.assertEqual(len(r.warnings), 2)

    def test_arm_failure_still_stops_the_dance(self):
        self.fake("r1_arm", "exit 3")
        with self.assertRaises(r1ctl.StepError):
            r1ctl.play_steps(self.robot(), [{"arm_pose": {"q": [0] * 13}}])

    def test_slow_mode_scales_arm_and_hand_timing(self):
        args = os.path.join(self.d, "args")
        self.fake("r1_arm", "echo \"$@\" >> %s" % args)
        self.fake("r1_hand", "echo \"$@\" >> %s" % args)
        r = self.robot()
        r.speed = 0.5
        r1ctl.play_steps(r, [{"arm_traj": {"file": "wave_demo"}}, {"hand": {"side": "right", "pose": "open", "ms": 600}}])
        out = open(args).read()
        self.assertRegex(out, r"traj \S+ 0\.5\b")
        self.assertRegex(out, r" 1200$|1200\n")


class Voice(unittest.TestCase):
    def setUp(self):
        import tempfile as tf
        self.old = r1ctl.CACHE, r1ctl.read_secret
        r1ctl.CACHE = tf.mkdtemp()
        r1ctl.read_secret = lambda *a: ""
        self.addCleanup(self.restore)
        self.cfg = dict(r1ctl.config(), eleven_voice="v", eleven_model="m", voice_fx="robot")

    def restore(self):
        shutil.rmtree(r1ctl.CACHE, True)
        r1ctl.CACHE, r1ctl.read_secret = self.old

    def line(self, text, fx="robot"):
        import hashlib
        return os.path.join(r1ctl.CACHE, hashlib.sha1(("vm" + fx + text).encode()).hexdigest()[:16] + ".wav")

    def test_ready_made_line_needs_no_key_and_no_internet(self):
        open(self.line("Ačiū"), "w").close()
        self.assertEqual(r1ctl.eleven_wav(self.cfg, "Ačiū"), self.line("Ačiū"))

    def test_clean_voice_has_its_own_file(self):
        open(self.line("Labas", "none"), "w").close()
        self.assertIsNone(r1ctl.eleven_wav(self.cfg, "Labas"))
        self.assertEqual(r1ctl.eleven_wav(self.cfg, "Labas", fx="none"), self.line("Labas", "none"))

    def test_lithuanian_is_never_sent_to_the_english_voice(self):
        r = r1ctl.Robot(self.cfg, live=False, log=lambda *a: None)
        r.say("Ačiū, kad atėjote", "eleven")
        self.assertEqual(r.history, [])
        self.assertEqual(len(r.warnings), 1)

    def test_english_line_falls_back_to_the_built_in_voice(self):
        r = r1ctl.Robot(self.cfg, live=False, log=lambda *a: None)
        r.say("Hello", "eleven")
        self.assertIn("tts", r.history[0])


class InstallRemove(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = r1ctl.LIB
        shutil.copytree(self.saved, os.path.join(self.tmp, "library"))
        r1ctl.LIB = os.path.join(self.tmp, "library")

    def tearDown(self):
        r1ctl.LIB = self.saved
        shutil.rmtree(self.tmp)

    def test_install_dance_file_then_remove(self):
        src = os.path.join(self.tmp, "spin.yaml")
        with open(src, "w") as f:
            f.write("kind: dance\nsteps:\n  - hand: {side: left, pose: peace}\n  - wait: 1\n")
        self.assertEqual(r1ctl.install(src), ["dances/spin"])
        r1ctl.play_dance(robot(), "spin")
        r1ctl.remove("dances/spin")
        with self.assertRaises(r1ctl.StepError):
            r1ctl.find_item("dances", "spin")

    def test_install_rejects_bad_file(self):
        src = os.path.join(self.tmp, "bad.yaml")
        with open(src, "w") as f:
            f.write("kind: dance\nsteps:\n  - loco: zero_torque\n")
        with self.assertRaises(r1ctl.StepError):
            r1ctl.install(src)

    def test_install_folder_finds_skill_and_csv(self):
        pack = os.path.join(self.tmp, "pack")
        shutil.copytree(os.path.join(self.saved, "vision", "wave_back"), os.path.join(pack, "wave2"))
        shutil.copy(os.path.join(self.saved, "arm", "wave_demo.csv"), os.path.join(pack, "w2.csv"))
        got = sorted(r1ctl.install(pack))
        self.assertEqual(got, ["arm/w2", "vision/wave2"])


class EventMenu(unittest.TestCase):
    def test_keys_play_and_stop(self):
        r = robot()
        keys = iter(["1", "s", "7", "zz", "q"])
        r1ctl.event_menu(r, "demo", read=lambda _: next(keys))
        flat = [" ".join(map(str, a)) for a in r.history]
        self.assertTrue(any("--id 27" in a for a in flat))           # 1 = hello
        self.assertTrue(any("--stop_move" in a for a in flat))       # S = stop
        self.assertTrue(any("r1_hand" in a and "right" in a for a in flat))  # 7 = thumbs up


class Vision(unittest.TestCase):
    def lm(self, up):
        """fake 21 landmarks: finger i up when tip y < pip y."""
        pts = [(0.5, 0.9)] * 21
        pts = list(pts)
        for i, (tip, pip) in enumerate(zip((8, 12, 16, 20), (6, 10, 14, 18))):
            pts[pip] = (0.5, 0.5)
            pts[tip] = (0.5, 0.3 if up[i] else 0.6)
        return pts

    def test_rps_classify_and_winner(self):
        m = load_skill("rock_paper_scissors")
        self.assertEqual(m.classify(m.fingers_up(self.lm([0, 0, 0, 0]))), "rock")
        self.assertEqual(m.classify(m.fingers_up(self.lm([1, 1, 1, 1]))), "paper")
        self.assertEqual(m.classify(m.fingers_up(self.lm([1, 1, 0, 0]))), "scissors")
        self.assertEqual(m.winner("rock", "scissors"), "robot")
        self.assertEqual(m.winner("rock", "paper"), "human")

    def test_rps_full_round(self):
        m = load_skill("rock_paper_scissors")
        hand = self.lm([1, 1, 0, 0])
        s = m.Skill(detector=lambda f: hand)
        s.setup({"config": {"side": "right"}})
        out = []
        for t in (0, 1, 2.1, 2.2, 2.4, 2.6, 2.8, 3.0):
            out += s.on_frame(None, {}, now=t)
        says = [st["say"] for st in out if "say" in st]
        self.assertTrue(any("scissors" in x for x in says[1:]), says)
        r1ctl.validate_steps(out)
        r1ctl.play_steps(robot(), out)

    def test_mirror_rate_limited_and_valid(self):
        m = load_skill("mirror_hand")
        s = m.Skill(detector=lambda f: [(0.5 + 0.01 * i, 0.5 + 0.01 * i) for i in range(21)])
        s.setup({"config": {}})
        out = [s.on_frame(None, {}, now=t / 30.0) for t in range(30)]
        sent = [o for o in out if o]
        self.assertTrue(3 <= len(sent) <= 6)
        r1ctl.validate_steps(sent[0])

    def test_wave_back_triggers_once(self):
        m = load_skill("wave_back")
        xs = iter([0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3] + [0.4] * 20)
        s = m.Skill(detector=lambda f: [(next(xs), 0.5)] * 21)
        s.setup({"config": {"dance": "hello"}})
        out = [s.on_frame(None, {}, now=t * 0.1) for t in range(20)]
        self.assertEqual(sum(1 for o in out if o), 1)


class Agent(unittest.TestCase):
    def test_mock_agent_runs_whitelisted_command_only(self):
        r = robot()
        saved = r1ctl.read_secret
        r1ctl.read_secret = lambda *a: ""
        try:
            r1ctl.run_agent(r, "host", iter(["hello there", "please wave", "rock paper scissors", "quit"]))
        finally:
            r1ctl.read_secret = saved
        flat = [" ".join(map(str, a)) for a in r.history]
        self.assertTrue(any("--id 27" in a for a in flat))  # wave → hello dance
        self.assertTrue(any("tts" in a for a in flat))

    def test_persona_commands_exist(self):
        p = r1ctl.load_yaml(os.path.join(r1ctl.LIB, "agents", "host", "persona.yaml"))
        for name, target in p["commands"].items():
            if isinstance(target, str):
                r1ctl.find_item("dances", target)
            else:
                r1ctl.validate_steps(target, name)


class Emotions(unittest.TestCase):
    def test_every_emotion_has_a_move(self):
        for emo in r1ctl.EMOTIONS:
            r1ctl.find_item("dances", emo)
            r1ctl.play_dance(robot(), emo)

    def test_mock_llm_returns_emotion(self):
        p = r1ctl.load_yaml(os.path.join(r1ctl.LIB, "agents", "host", "persona.yaml"))
        out = r1ctl.llm_reply(r1ctl.config(), p, [], "tell me a joke", "")
        self.assertEqual(out["emotion"], "laughing")
        self.assertIn(out["emotion"], r1ctl.EMOTIONS)


class VoiceWaitsForTheArm(unittest.TestCase):
    """The arm walks to its first frame before the move. A reveal must not land before the arm does."""

    def play(self, arm_script):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        log = os.path.join(d, "log")
        for name, body in (("r1_arm", arm_script), ("r1_hand", "echo hand >> %s" % log)):
            p = os.path.join(d, name)
            with open(p, "w") as f:
                f.write("#!/bin/bash\n" + body.replace("LOG", log) + "\n")
            os.chmod(p, 0o755)
        r = r1ctl.Robot(dict(r1ctl.config(), bin=d, iface="eth0"), live=True, log=lambda *a: None)
        csv = os.path.join(d, "x.csv")
        open(csv, "w").write("0,0,0,0,0,0,0,0,0,0,0,0,0,0\n1,0,0,0,0,0,0,0,0,0,0,0,0,0\n")
        keep = r1ctl.find_item
        r1ctl.find_item = lambda k, n: csv
        self.addCleanup(lambda: setattr(r1ctl, "find_item", keep))
        r1ctl.play_steps(r, [{"parallel": [{"arm_traj": {"file": "x"}}, {"hand": {"side": "right", "q": [0] * 6}}]}])
        return open(log).read().split()

    def test_fingers_start_on_go(self):
        self.assertEqual(self.play("echo walking >> LOG; sleep 0.4; echo arrived >> LOG; echo go; sleep 0.2; echo end >> LOG"),
                         ["walking", "arrived", "hand", "end"])

    def test_an_arm_that_fails_does_not_hang_the_fingers(self):
        self.assertEqual(self.play("echo walking >> LOG"), ["walking", "hand"])


class Limits(unittest.TestCase):
    def test_a_file_cannot_ask_for_limp(self):
        for mode in (0, 1, 4, 811):
            with self.assertRaises(r1ctl.StepError):
                r1ctl.validate_steps([{"fsm": mode}])
        r1ctl.validate_steps([{"fsm": 601}])


class SecondStop(unittest.TestCase):
    def test_a_second_stop_sends_no_second_signal(self):
        sent = []

        class Kid:
            def poll(self):
                return 0

            def send_signal(self, s):
                sent.append(s)

        r = r1ctl.Robot(dict(r1ctl.config(), iface="eth0"), live=True, log=lambda *a: None)
        r.children.add(Kid())
        r.abort()
        r.abort()
        self.assertEqual(len(sent), 1)


class StubbornProgram(unittest.TestCase):
    def test_a_program_that_ignores_ctrl_c_is_killed(self):
        p = subprocess.Popen(["python3", "-c", "import signal,time; signal.signal(signal.SIGINT, signal.SIG_IGN); print(1, flush=True); time.sleep(30)"], stdout=subprocess.PIPE)
        p.stdout.readline()
        r1ctl.Robot._finish_off([p], grace=0.05)
        self.assertEqual(p.wait(5), -9)


if __name__ == "__main__":
    unittest.main(verbosity=1)
