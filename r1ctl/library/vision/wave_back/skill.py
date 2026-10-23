"""Wave detector: an open hand moving left-right 3+ times within 2 s → play the greeting dance."""
import time


class Skill:
    def __init__(self, detector=None):
        self.detector, self.xs, self.cool = detector, [], 0.0

    def setup(self, ctx):
        if self.detector is None:
            import mediapipe as mp
            import cv2
            hands = mp.solutions.hands.Hands(max_num_hands=1, min_detection_confidence=0.6)

            def detect(frame):
                res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if not res.multi_hand_landmarks:
                    return None
                return [(p.x, p.y) for p in res.multi_hand_landmarks[0].landmark]
            self.detector = detect
        self.dance = ctx.get("config", {}).get("dance", "hello")

    def on_frame(self, frame, ctx, now=None):
        now = time.time() if now is None else now
        if now < self.cool:
            return []
        lm = self.detector(frame)
        self.xs = [(t, x) for t, x in self.xs if now - t < 2.0]
        if lm is not None:
            self.xs.append((now, lm[9][0]))
        flips, last = 0, 0
        for (_, a), (_, b) in zip(self.xs, self.xs[1:]):
            d = (b > a) - (b < a)
            if d and abs(b - a) > 0.01 and d != last:
                flips, last = flips + 1, d
        if flips >= 4:
            self.xs, self.cool = [], now + 8.0
            return [{"dance": self.dance}]
        return []
