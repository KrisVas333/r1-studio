"""Mirror: each of the person's fingers → the same Revo2 finger. EMA smoothing + 5 Hz command rate."""
import time

# (tip, base) landmark pairs per Revo2 channel: thumb, thumb_aux, index, middle, ring, pinky
PAIRS = [(4, 2), (4, 2), (8, 5), (12, 9), (16, 13), (20, 17)]


def curl(lm):
    """0 = straight, 1 = curled, from tip-to-wrist vs base-to-wrist distance."""
    wx, wy = lm[0]
    out = []
    for tip, base in PAIRS:
        dt = ((lm[tip][0] - wx) ** 2 + (lm[tip][1] - wy) ** 2) ** 0.5
        db = ((lm[base][0] - wx) ** 2 + (lm[base][1] - wy) ** 2) ** 0.5 or 1e-6
        out.append(min(1.0, max(0.0, (1.9 - dt / db) / 1.0)))
    return out


class Skill:
    def __init__(self, detector=None, alpha=0.4, period=0.2):
        self.detector, self.alpha, self.period = detector, alpha, period
        self.q, self.last = None, 0.0

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
        self.side = ctx.get("config", {}).get("side", "right")

    def on_frame(self, frame, ctx, now=None):
        now = time.time() if now is None else now
        lm = self.detector(frame)
        if lm is None:
            return []
        c = curl(lm)
        self.q = c if self.q is None else [self.alpha * a + (1 - self.alpha) * b for a, b in zip(c, self.q)]
        if now - self.last < self.period:
            return []
        self.last = now
        return [{"hand": {"side": self.side, "q": [round(v, 2) for v in self.q], "ms": 150}}]
