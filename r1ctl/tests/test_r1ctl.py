import os
import shutil
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


if __name__ == "__main__":
    unittest.main(verbosity=1)
