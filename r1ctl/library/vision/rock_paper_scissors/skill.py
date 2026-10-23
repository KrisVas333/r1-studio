"""Rock-paper-scissors: robot counts 3-2-1, reads the person's hand, shows its own throw, says who won."""
import random
import time

TIPS, PIPS = (8, 12, 16, 20), (6, 10, 14, 18)  # MediaPipe index/middle/ring/pinky tip + pip ids
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


def fingers_up(lm):
    """lm: 21 (x, y) points, image coords (y grows down). Returns [index, middle, ring, pinky] up?"""
    return [lm[t][1] < lm[p][1] for t, p in zip(TIPS, PIPS)]


def classify(up):
    n = sum(up)
    if n == 0:
        return "rock"
    if n >= 3:
        return "paper"
    if up[0] and up[1] and not up[2] and not up[3]:
        return "scissors"
    return None


def winner(robot_throw, human_throw):
    if robot_throw == human_throw:
        return "draw"
    return "robot" if BEATS[robot_throw] == human_throw else "human"


class Skill:
    def __init__(self, detector=None):
        self.detector = detector  # tests inject a fake; real runs build MediaPipe in setup()
        self.state, self.t0, self.votes = "idle", 0.0, []

    def setup(self, ctx):
        if self.detector is None:
            import mediapipe as mp
            hands = mp.solutions.hands.Hands(max_num_hands=1, min_detection_confidence=0.6)

            def detect(frame):
                import cv2
                res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if not res.multi_hand_landmarks:
                    return None
                return [(p.x, p.y) for p in res.multi_hand_landmarks[0].landmark]
            self.detector = detect
        self.side = ctx.get("config", {}).get("side", "right")

    def on_frame(self, frame, ctx, now=None):
        now = time.time() if now is None else now
        lm = self.detector(frame)
        if self.state == "idle":
            if lm is not None:  # a hand appeared: start a round
                self.state, self.t0, self.votes = "count", now, []
                return [{"say": "Rock, paper, scissors!"}, {"hand": {"side": self.side, "pose": "fist", "ms": 300}}]
            return []
        if self.state == "count":
            if now - self.t0 < 2.0:
                return []
            self.state, self.t0 = "read", now
            return []
        if self.state == "read":
            if lm is not None:
                c = classify(fingers_up(lm))
                if c:
                    self.votes.append(c)
            if now - self.t0 < 0.6 and len(self.votes) < 5:
                return []
            self.state, self.t0 = "cooldown", now
            human = max(set(self.votes), key=self.votes.count) if self.votes else None
            mine = random.choice(list(BEATS))
            steps = [{"hand": {"side": self.side, "pose": mine, "ms": 250}}]
            if human is None:
                return steps + [{"say": "I could not see your hand. Again?"}]
            w = winner(mine, human)
            line = {"draw": "Draw! We both picked %s." % mine,
                    "robot": "I win! %s beats %s." % (mine, human),
                    "human": "You win! %s beats %s." % (human, mine)}[w]
            return steps + [{"say": line}]
        if self.state == "cooldown" and now - self.t0 > 4.0:
            self.state = "idle"
            return [{"hand": {"side": self.side, "pose": "open"}}]
        return []
