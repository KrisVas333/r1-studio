"""Move factory: writes the preset deck (arm keyframes → library/arm/m_<name>.csv + library/dances/<name>.yaml).

Upper body only (arms, waist turn, small head moves); legs stay with Unitree's balance controller.
Every move is checked on Unitree's R1 model by r1sim (joint limits, arm-body hits, speed).
Conventions measured on the model (2026-10-23):
  shoulder pitch -1.57 = arm forward, -2.9 = overhead · elbow: see elbow() (joint +1.4 straight, -0.95 folded)
  'out' = shoulder roll away from body · 'inw' = shoulder yaw turning the forearm across the body
Run:  ~/r1/sim/.venv/bin/python tools/make_moves.py
"""
import os
import sys

import yaml

R1 = os.path.expanduser("~/r1")
LIB = os.path.join(R1, "r1ctl", "library")
MAXV = 1.5  # rad/s planning speed (r1_arm hard cap is 2.0)


def elbow(e):
    """Moves below are written in 'intent' units (-0.95 straight · 0 = 90° · 2.0 folded).
    Measured on Unitree's model the real joint is the other way round: +1.4 straight, 0 bent, -0.95 folded."""
    return -e / 0.95 * 1.4 if e < 0 else -min(e, 2.05) / 2.05 * 0.95


def arm(sp=0.0, out=0.0, inw=0.0, e=0.0, wr=0.0):
    return (sp, out, inw, elbow(e), wr)


REST = arm()
UP = arm(-2.8, 0.4, 0, -0.95)
V_UP = arm(-2.7, 0.6, 0, -0.95)
FWD = arm(-1.57, 0, 0, -0.95)
SIDE = arm(0, 1.57, 0, -0.95)
DOWN = arm(0, 0.1, 0, -0.95)
FOLD = arm(-0.3, 0.1, 0, 2.0)
GUARD = arm(-0.6, 0.15, 0.35, 1.6)
PUNCH = arm(-1.5, 0.05, 0.15, -0.9)
HIP = arm(-0.1, 0.65, 0.9, 1.4)
CHIN = arm(-0.9, 0.2, 0.6, 2.0)
BELLY = arm(-0.2, 0.15, 1.0, 1.4)
FACE = arm(-1.3, 0.2, 0.8, 1.95)
HEAD_TOP = arm(-2.5, 0.9, 0.3, 1.7)
SHRUG = arm(-0.2, 0.45, -0.9, 0.9, 1.2)
SALUTE = arm(-1.8, 0.5, 0.7, 1.9)


def pose(R=REST, L=REST, waist=0.0, nod=0.0, turn=0.0):
    """→ 13 joints in r1_arm order. Left arm mirrors roll/yaw/wrist signs."""
    return [L[0], L[1], -L[2], L[3], -L[4], R[0], -R[1], R[2], R[3], R[4], waist, nod, turn]


MOVES = []


def move(name, title, category, emoji, frames, hands=(), say=None, pre=None):
    """frames: [(seconds_from_previous, pose)] — first frame starts at t=0. hands: [(t, side, pose)]."""
    MOVES.append(dict(name=name, title=title, category=category, emoji=emoji, frames=frames, hands=hands, say=say, pre=pre))


def osc(a, b, n, dt):
    """a, b, a, b … n times (for bounces/shakes)."""
    return [(dt, a if i % 2 == 0 else b) for i in range(n)]


# ---------------------------------------------------------------- EMOTIONS
move("happy", "Happy", "Emotions", "😄", [(0, pose()), (0.8, pose(V_UP, V_UP)), *osc(pose(arm(-2.5, 0.7, 0, -0.5), arm(-2.5, 0.7, 0, -0.5)), pose(V_UP, V_UP), 4, 0.35), (0.8, pose())],
     hands=[(0, "both", "open")], say="Yay! This is the best day ever!")
move("excited", "Excited", "Emotions", "🤩", [(0, pose()), *osc(pose(FOLD, UP), pose(UP, FOLD), 6, 0.45), (0.8, pose())],
     hands=[(0, "both", "fist")], say="Let's goooo!")
move("sad", "Sad", "Emotions", "😢", [(0, pose()), (1.5, pose(DOWN, DOWN, nod=0.35)), (2.0, pose(DOWN, DOWN, waist=0.1, nod=0.4)), (1.2, pose())],
     hands=[(0, "both", "open")], say="Oh no. That makes me sad.")
move("angry", "Angry", "Emotions", "😠", [(0, pose()), (0.7, pose(arm(0, 0.35, 0, 0.5), arm(0, 0.35, 0, 0.5))),
     *osc(pose(arm(-0.2, 0.35, 0, 0.6), arm(0, 0.35, 0, 0.4)), pose(arm(0, 0.35, 0, 0.4), arm(-0.2, 0.35, 0, 0.6)), 6, 0.2), (0.8, pose())],
     hands=[(0, "both", "fist")], say="Grrr! Not cool!")
move("surprised", "Surprised", "Emotions", "😲", [(0, pose()), (0.6, pose(arm(-1.4, 0.6, -0.3, 1.0), arm(-1.4, 0.6, -0.3, 1.0), nod=-0.15)), (1.5, pose(arm(-1.4, 0.6, -0.3, 1.0), arm(-1.4, 0.6, -0.3, 1.0))), (1.0, pose())],
     hands=[(0, "both", "open")], say="Whoa! I did not see that coming!")
move("scared", "Scared", "Emotions", "😱", [(0, pose()), (0.7, pose(FACE, FACE, nod=0.2)), *osc(pose(FACE, FACE, waist=0.15), pose(FACE, FACE, waist=-0.15), 4, 0.25), (1.0, pose())],
     hands=[(0, "both", "open")], say="Eek! Is it gone?")
move("shy", "Shy", "Emotions", "😊", [(0, pose()), (1.0, pose(arm(-0.3, 0.2, 0.6, 0.5), arm(-0.3, 0.2, 0.6, 0.5), nod=0.3, turn=0.3)), (1.5, pose(arm(-0.3, 0.2, 0.6, 0.5), arm(-0.3, 0.2, 0.6, 0.5), waist=0.2, nod=0.3, turn=0.3)), (1.0, pose())],
     hands=[(0, "both", "soft_grip")], say="Oh, stop it. You're making my circuits blush.")
move("love", "Love", "Emotions", "🥰", [(0, pose()), (1.0, pose(arm(-1.2, 0.2, 0.7, 1.4), arm(-1.2, 0.2, 0.7, 1.4))), *osc(pose(arm(-1.2, 0.2, 0.7, 1.4), arm(-1.2, 0.2, 0.7, 1.4), waist=0.15), pose(arm(-1.2, 0.2, 0.7, 1.4), arm(-1.2, 0.2, 0.7, 1.4), waist=-0.15), 4, 0.5), (1.0, pose())],
     hands=[(0, "both", "ok")], say="I love you guys!")
move("proud", "Proud", "Emotions", "😎", [(0, pose()), (1.0, pose(HIP, HIP, nod=-0.15)), (1.8, pose(HIP, HIP, waist=0.25, nod=-0.15)), (1.0, pose())],
     hands=[(0, "both", "fist")], say="Nailed it. As usual.")
move("thinking", "Thinking", "Emotions", "🤔", [(0, pose()), (1.0, pose(CHIN, BELLY, turn=0.25, nod=0.1)), (2.0, pose(CHIN, BELLY, turn=-0.2, nod=0.1)), (1.0, pose())],
     hands=[(0, "right", "point")], say="Hmm. Let me think about that.")
move("sleepy", "Sleepy", "Emotions", "😴", [(0, pose()), (1.4, pose(V_UP, V_UP)), (1.0, pose(V_UP, V_UP, waist=0.2)), (1.6, pose(DOWN, DOWN, nod=0.4)), (1.0, pose())],
     hands=[(0, "both", "open")], say="Yaaawn. Low battery.")
move("laughing", "Laughing", "Emotions", "😂", [(0, pose()), (0.8, pose(BELLY, BELLY)), *osc(pose(BELLY, BELLY, waist=0.15, nod=0.1), pose(BELLY, BELLY, waist=-0.15, nod=-0.05), 6, 0.3), (0.8, pose())],
     hands=[(0, "both", "soft_grip")], say="Ha ha ha! Good one!")
move("confused", "Confused", "Emotions", "😕", [(0, pose()), (0.9, pose(SHRUG, SHRUG, turn=0.3)), (1.5, pose(SHRUG, SHRUG, turn=-0.25)), (0.9, pose())],
     hands=[(0, "both", "open")], say="Huh? Does not compute.")

# ---------------------------------------------------------------- REACTIONS
move("cheer", "Cheer", "Reactions", "🙌", [(0, pose()), (0.8, pose(V_UP, V_UP)), *osc(pose(V_UP, V_UP, waist=0.15), pose(V_UP, V_UP, waist=-0.15), 4, 0.35), (0.8, pose())],
     hands=[(0, "both", "fist")], say="Woo hoo!")
move("facepalm", "Facepalm", "Reactions", "🤦", [(0, pose()), (1.0, pose(arm(-1.35, 0.15, 0.85, 2.05), nod=0.25)), (1.5, pose(arm(-1.35, 0.15, 0.85, 2.05), nod=0.3, turn=-0.15)), (1.0, pose())],
     hands=[(0, "right", "open")], say="Oh, humans.")
move("shrug", "Shrug", "Reactions", "🤷", [(0, pose()), (0.8, pose(SHRUG, SHRUG)), (1.2, pose(SHRUG, SHRUG, nod=-0.1)), (0.8, pose())],
     hands=[(0, "both", "open")], say="I don't know.")
move("mind_blown", "Mind blown", "Reactions", "🤯", [(0, pose()), (1.0, pose(HEAD_TOP, HEAD_TOP)), (0.4, pose(HEAD_TOP, HEAD_TOP)), (0.6, pose(arm(-2.4, 1.3, 0, -0.9), arm(-2.4, 1.3, 0, -0.9))), (0.8, pose(arm(-2.4, 1.3, 0, -0.9), arm(-2.4, 1.3, 0, -0.9))), (1.0, pose())],
     hands=[(0, "both", "fist"), (1.4, "both", "open")], say="Mind. Blown.")
move("salute", "Salute", "Reactions", "🫡", [(0, pose()), (1.0, pose(SALUTE)), (1.5, pose(SALUTE)), (1.0, pose())],
     hands=[(0, "right", "open")], say="Reporting for duty!")
move("bow", "Thank-you bow", "Reactions", "🙇", [(0, pose()), (1.0, pose(arm(-0.6, 0.1, 1.0, 1.6), arm(-0.1, 0.6, 0, -0.9), nod=0.4)), (1.4, pose(arm(-0.6, 0.1, 1.0, 1.6), arm(-0.1, 0.6, 0, -0.9), nod=0.45)), (1.0, pose())],
     hands=[(0, "right", "open")], say="Thank you, thank you. You are too kind.")
move("high_five", "High five?", "Reactions", "🖐️", [(0, pose()), (1.0, pose(arm(-2.3, 0.4, 0, -0.4))), (2.5, pose(arm(-2.3, 0.4, 0, -0.4))), (1.0, pose())],
     hands=[(0, "right", "open")], say="Up high! Gently, please.")
move("point_at_you", "Point at you", "Reactions", "👉", [(0, pose()), (0.8, pose(arm(-1.45, 0.1, 0.1, -0.9))), (1.5, pose(arm(-1.45, 0.1, 0.1, -0.9), waist=0.15)), (0.8, pose())],
     hands=[(0, "right", "point")], say="Yes, you! You look like a future engineer.")
move("thumbs_up_both", "Double thumbs up", "Reactions", "👍", [(0, pose()), (0.9, pose(arm(-1.2, 0.3, 0, 0.4), arm(-1.2, 0.3, 0, 0.4))), (1.5, pose(arm(-1.2, 0.3, 0, 0.4), arm(-1.2, 0.3, 0, 0.4), waist=0.1)), (0.9, pose())],
     hands=[(0, "both", "thumbs_up")], say="Awesome!")

# ---------------------------------------------------------------- VIRAL / TIKTOK (moves only, no music)
AURA_A = arm(-1.3, 0.8, -0.2, -0.5, 0.8)
AURA_B = arm(-1.1, 0.5, 0.3, 0.2, -0.6)
move("aura_farming", "Aura farming", "Viral", "🛶", [(0, pose()), (1.0, pose(AURA_A, REST, turn=-0.3)), (0.7, pose(AURA_B, REST, turn=-0.3)), (0.7, pose(AURA_A, REST, waist=0.1, turn=-0.3)),
     (0.9, pose(REST, AURA_A, turn=0.3)), (0.7, pose(REST, AURA_B, turn=0.3)), (0.7, pose(REST, AURA_A, waist=-0.1, turn=0.3)),
     (0.9, pose(AURA_A, AURA_A)), (0.7, pose(AURA_B, AURA_B, nod=-0.1)), (0.7, pose(AURA_A, AURA_A, nod=-0.1)), (1.2, pose(arm(-0.3, 0.2, 0, 0.2), REST, turn=0.35, nod=-0.1)), (1.0, pose())],
     hands=[(0, "both", "open")], say="Aura level: maximum.")
move("dab", "Dab", "Viral", "🫳", [(0, pose()), (0.8, pose(arm(-2.2, 1.2, 0, -0.95), arm(-1.8, 0.2, 1.1, 2.0), waist=0.2, nod=0.3, turn=0.3)), (1.4, pose(arm(-2.2, 1.2, 0, -0.95), arm(-1.8, 0.2, 1.1, 2.0), waist=0.2, nod=0.3, turn=0.3)), (0.9, pose())],
     hands=[(0, "both", "open")], say="Dab!")
move("hit_the_woah", "Hit the woah", "Viral", "💥", [(0, pose()), *[(dt, p) for _ in range(2) for dt, p in [(0.6, pose(arm(-1.8, 0.1, 0.8, 1.2), GUARD)), (0.35, pose(arm(-0.6, 0.6, 0, -0.6), GUARD, waist=-0.15))]], (0.9, pose())],
     hands=[(0, "both", "fist")], say="Woah!")
move("the_robot", "The robot", "Viral", "🤖", [(0, pose()), (0.5, pose(FOLD, REST)), (0.3, pose(FOLD, REST)), (0.5, pose(arm(-1.57, 0, 0, 0), FOLD)), (0.3, pose(arm(-1.57, 0, 0, 0), FOLD, turn=0.3)),
     (0.5, pose(arm(-1.57, 0, 0, 0), arm(-1.57, 0, 0, 0), turn=0.3)), (0.3, pose(arm(-1.57, 0, 0, 0), arm(-1.57, 0, 0, 0), turn=-0.3)), (0.5, pose(arm(-1.57, 0.4, -0.6, 0), arm(-1.57, 0.4, -0.6, 0), waist=0.3)),
     (0.5, pose(arm(-1.57, 0.4, -0.6, 0), arm(-1.57, 0.4, -0.6, 0), waist=-0.3)), (0.8, pose())],
     hands=[(0, "both", "open")], say="Beep. Boop. I invented this dance.")
move("macarena", "Macarena", "Viral", "💃", [(0, pose()), (0.7, pose(FWD, REST)), (0.6, pose(FWD, FWD)), (0.6, pose(arm(-1.57, 0, 0, -0.95, 1.5), FWD)), (0.6, pose(arm(-1.57, 0, 0, -0.95, 1.5), arm(-1.57, 0, 0, -0.95, 1.5))),
     (0.7, pose(arm(-1.2, 0.1, 1.0, 1.9), arm(-1.57, 0, 0, -0.95, 1.5))), (0.7, pose(arm(-1.2, 0.1, 1.0, 1.9), arm(-1.2, 0.1, 1.0, 1.9))),
     (0.8, pose(HEAD_TOP, arm(-1.2, 0.1, 1.0, 1.9))), (0.8, pose(HEAD_TOP, HEAD_TOP)), (0.8, pose(HIP, HEAD_TOP)), (0.8, pose(HIP, HIP)),
     *osc(pose(HIP, HIP, waist=0.25), pose(HIP, HIP, waist=-0.25), 4, 0.4), (0.9, pose())],
     hands=[(0, "both", "open")], say="Hey! Macarena!")
move("ymca", "Y-M-C-A", "Viral", "🔤", [(0, pose()), (0.9, pose(V_UP, V_UP)), (0.6, pose(V_UP, V_UP)), (0.9, pose(HEAD_TOP, HEAD_TOP)), (0.6, pose(HEAD_TOP, HEAD_TOP)),
     (0.9, pose(arm(-2.3, 0.2, -0.3, 0.6), arm(-0.8, 0.9, 0, 0.6))), (0.6, pose(arm(-2.3, 0.2, -0.3, 0.6), arm(-0.8, 0.9, 0, 0.6))),
     (0.9, pose(arm(-2.9, 0.1, 0.4, -0.4), arm(-2.9, 0.1, 0.4, -0.4))), (0.8, pose(arm(-2.9, 0.1, 0.4, -0.4), arm(-2.9, 0.1, 0.4, -0.4))), (1.0, pose())],
     hands=[(0, "both", "open")], say="Y! M! C! A!")
move("disco_point", "Disco point", "Movies", "🕺", [(0, pose()), *[(dt, p) for _ in range(3) for dt, p in [(0.6, pose(arm(-2.6, 0.6, 0, -0.95), HIP)), (0.6, pose(arm(-0.3, 0.1, 1.0, -0.6), HIP, waist=0.2))]], (0.9, pose())],
     hands=[(0, "right", "point"), (0, "left", "fist")], say="Stayin' alive! Well, staying charged.")
move("thriller_zombie", "Zombie walk arms", "Movies", "🧟", [(0, pose()), (1.2, pose(arm(-1.5, 0, 0, -0.9, 0.6), arm(-1.5, 0, 0, -0.9, 0.6), nod=0.15)),
     *osc(pose(arm(-1.4, 0, 0, -0.9, 0.6), arm(-1.6, 0, 0, -0.9, 0.6), waist=0.2, turn=0.2), pose(arm(-1.6, 0, 0, -0.9, 0.6), arm(-1.4, 0, 0, -0.9, 0.6), waist=-0.2, turn=-0.2), 4, 0.8), (1.0, pose())],
     hands=[(0, "both", "soft_grip")], say="Braaains. Just kidding. I have a processor.")
move("pulp_fiction_v", "V across the eyes", "Movies", "✌️", [(0, pose()), (0.9, pose(arm(-1.3, 0.2, 0.95, 1.9))), (0.8, pose(arm(-1.3, 0.6, 0.4, 1.7), waist=-0.15)), (0.8, pose(REST, arm(-1.3, 0.2, 0.95, 1.9))), (0.8, pose(REST, arm(-1.3, 0.6, 0.4, 1.7), waist=0.15)),
     *osc(pose(arm(-0.3, 0.3, 0, 0.8), arm(-0.3, 0.3, 0, 0.8), waist=0.3), pose(arm(-0.3, 0.3, 0, 0.8), arm(-0.3, 0.3, 0, 0.8), waist=-0.3), 4, 0.45), (0.9, pose())],
     hands=[(0, "both", "peace")], say="Let's twist!")
move("lasso", "Lasso", "Viral", "🤠", [(0, pose()), (0.9, pose(arm(-2.7, 0.5, 0, 0.3), HIP)), *[(0.35, pose(arm(-2.7 + 0.2 * (i % 2), 0.5 + 0.3 * ((i // 2) % 2), 0, 0.3, 0.8 * (1 if i % 2 else -1)), HIP)) for i in range(8)], (0.9, pose())],
     hands=[(0, "right", "fist"), (0, "left", "fist")], say="Yee-haw!")
move("noodle_arms", "Noodle arms", "Viral", "🍜", [(0, pose()), (0.8, pose(SIDE, SIDE)), *osc(pose(arm(-0.2, 1.5, 0, -0.2, 0.8), arm(0.2, 1.5, 0, -0.95, -0.8)), pose(arm(0.2, 1.5, 0, -0.95, -0.8), arm(-0.2, 1.5, 0, -0.2, 0.8)), 6, 0.45), (0.9, pose())],
     hands=[(0, "both", "open")], say="Wiggle wiggle!")

# ---------------------------------------------------------------- FIGHT (air only, never toward people)
move("guard", "Guard stance", "Fight", "🛡️", [(0, pose()), (0.8, pose(GUARD, GUARD, turn=0.0)), (1.5, pose(GUARD, GUARD, waist=0.15)), (0.8, pose())],
     hands=[(0, "both", "fist")], say="Ready.")
move("jab", "Jab", "Fight", "👊", [(0, pose(GUARD, GUARD)), (0.6, pose(GUARD, GUARD)), (0.3, pose(GUARD, PUNCH, waist=0.15)), (0.4, pose(GUARD, GUARD)), (0.6, pose())],
     hands=[(0, "both", "fist")], pre=None)
move("one_two", "One-two combo", "Fight", "🥊", [(0, pose()), (0.6, pose(GUARD, GUARD)), (0.3, pose(GUARD, PUNCH, waist=0.15)), (0.35, pose(GUARD, GUARD)), (0.3, pose(PUNCH, GUARD, waist=-0.2)), (0.4, pose(GUARD, GUARD)),
     (0.3, pose(GUARD, PUNCH, waist=0.15)), (0.35, pose(GUARD, GUARD)), (0.3, pose(PUNCH, GUARD, waist=-0.2)), (0.4, pose(GUARD, GUARD)), (0.7, pose())],
     hands=[(0, "both", "fist")], say="One, two! One, two!")
move("uppercut", "Uppercut", "Fight", "⬆️", [(0, pose()), (0.6, pose(arm(-0.3, 0.15, 0.2, 1.8), GUARD, waist=-0.15)), (0.4, pose(arm(-2.0, 0.15, 0.3, 1.0), GUARD, waist=0.2)), (0.6, pose(GUARD, GUARD)), (0.7, pose())],
     hands=[(0, "both", "fist")], say="Hi-yah!")
move("karate_chop", "Karate chop", "Fight", "🥋", [(0, pose()), (0.8, pose(arm(-2.6, 0.5, 0, 1.0), GUARD)), (0.35, pose(arm(-1.1, 0.2, 0.3, -0.5), GUARD, waist=0.15)), (0.7, pose(arm(-1.1, 0.2, 0.3, -0.5), GUARD, waist=0.15)), (0.8, pose())],
     hands=[(0, "right", "open"), (0, "left", "fist")], say="Hi-YAH!")
move("block", "Block", "Fight", "🧱", [(0, pose()), (0.5, pose(arm(-1.5, 0.3, 0.6, 1.3), arm(-1.5, 0.3, 0.6, 1.3))), (1.0, pose(arm(-1.5, 0.3, 0.6, 1.3), arm(-1.5, 0.3, 0.6, 1.3), nod=0.15)), (0.8, pose())],
     hands=[(0, "both", "fist")], say="Blocked!")
move("energy_blast", "Energy blast", "Fight", "🌀", [(0, pose()), (1.2, pose(arm(-0.5, 0.35, 0.6, 1.4), arm(-0.5, 0.35, 0.6, 1.4), waist=0.4)), (1.0, pose(arm(-0.5, 0.35, 0.6, 1.4), arm(-0.5, 0.35, 0.6, 1.4), waist=0.45)),
     (0.6, pose(arm(-1.57, 0.15, 0.2, -0.6), arm(-1.57, 0.15, 0.2, -0.6))), (1.2, pose(arm(-1.57, 0.15, 0.2, -0.6), arm(-1.57, 0.15, 0.2, -0.6))), (1.0, pose())],
     hands=[(0, "both", "soft_grip"), (2.2, "both", "open")], say="Charging... charging... BLAST!")
move("crane", "Crane pose", "Fight", "🦢", [(0, pose()), (1.2, pose(arm(-2.4, 1.2, 0, -0.6, 1.0), arm(-2.4, 1.2, 0, -0.6, -1.0))), (2.0, pose(arm(-2.4, 1.2, 0, -0.6, 1.0), arm(-2.4, 1.2, 0, -0.6, -1.0))), (1.0, pose())],
     hands=[(0, "both", "ok")], say="If done right, no can defend.")
move("victory", "Victory", "Fight", "🏆", [(0, pose()), (0.8, pose(UP, UP)), *osc(pose(UP, UP, waist=0.2), pose(UP, UP, waist=-0.2), 4, 0.4), (0.9, pose())],
     hands=[(0, "both", "fist")], say="Champion!")


SIM = None
LIMITS = None


def hits(q):
    """True if this pose makes an arm touch the body or the other arm (contacts already in rest pose ignored)."""
    import mujoco
    import numpy as np
    SIM.pose(np.array(q, float))
    m, d = SIM.m, SIM.d
    for c in d.contact[:d.ncon]:
        if c.geom1 in SIM.floor or c.geom2 in SIM.floor or c.dist > -0.005:
            continue
        pair = tuple(sorted((m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2])))
        if pair in BASE:
            continue
        names = "".join(mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, b) or "" for b in pair)
        if any(k in names for k in ("shoulder", "elbow", "wrist")):
            return True
    return False


BASE = set()


def clamp(q):
    return [min(hi, max(lo, v)) if lo is not None else v for v, (lo, hi) in zip(q, LIMITS)]


def repair(qa, qb, depth=0):
    """Straight path collides? insert a waypoint with arms swung outward (+ elbows a bit bent)."""
    bad = any(hits([a + (b - a) * (u * u * (3 - 2 * u)) for a, b in zip(qa, qb)]) for u in [i / 20 for i in range(1, 20)])
    if not bad or depth > 3:
        return [qb]
    mid = [(a + b) / 2 for a, b in zip(qa, qb)]
    mid[1] += 0.45   # left roll out
    mid[6] -= 0.45   # right roll out
    mid[3] = max(mid[3], 0.2)
    mid[8] = max(mid[8], 0.2)
    mid = clamp(mid)
    return repair(qa, mid, depth + 1) + repair(mid, qb, depth + 1)


def fix_pose(q, name):
    """Keyframe touches itself? turn forearms outward + open shoulders a little until clear (keeps the intent)."""
    q = list(q)
    for i in range(12):
        if not hits(q):
            if i:
                print("   🔧 %s: adjusted a keyframe (%d steps)" % (name, i))
            return q
        q[2] *= 0.8; q[7] *= 0.8          # shoulder yaw toward neutral
        q[1] += 0.08; q[6] -= 0.08        # shoulders out
        q[0] += 0.05 if q[0] < -0.3 else 0  # less raised in front
        q[5] += 0.05 if q[5] < -0.3 else 0
        q = clamp(q)
    print("   ⚠️ %s: keyframe still collides after fixing" % name)
    return q


# ---------------------------------------------------------------- OBJECTS (soft, light things only; adult hands them over)
move("take_object", "Take an object", "Objects", "🤲", [(0, pose()), (1.0, pose(arm(-1.0, 0.25, 0.2, 0.3))), (4.0, pose(arm(-1.0, 0.25, 0.2, 0.3))), (1.2, pose(arm(-0.6, 0.2, 0.3, 1.0)))],
     hands=[(0, "right", "open"), (4.2, "right", "soft_grip")], say="Please put it in my hand. Gently!")
move("give_back", "Give it back", "Objects", "🎁", [(0, pose(arm(-0.6, 0.2, 0.3, 1.0))), (1.2, pose(arm(-1.1, 0.25, 0.2, 0.2))), (3.0, pose(arm(-1.1, 0.25, 0.2, 0.2))), (1.2, pose())],
     hands=[(0, "right", "soft_grip"), (2.0, "right", "open")], say="Here you go!")
move("soft_toss", "Soft toss (plush/foam only)", "Objects", "🧸", [(0, pose(arm(-0.6, 0.2, 0.3, 1.0))), (1.0, pose(arm(0.5, 0.2, 0, -0.6))), (0.6, pose(arm(-1.7, 0.2, 0, -0.5))), (1.0, pose())],
     hands=[(0, "right", "soft_grip"), (1.45, "right", "open")], say="Catch! Soft throw!")


def build(mv):
    """keyframes → (rows @50 Hz, auto-stretched so no joint exceeds MAXV, collision-repaired)."""
    fixed = [(dt, fix_pose(q, mv["name"])) for dt, q in mv["frames"]]
    frames = [fixed[0]]
    for dt, q in fixed[1:]:
        path = repair(frames[-1][1], q)
        for k, w in enumerate(path):
            frames.append((dt / len(path), w))
    keys, t = [], 0.0
    prev = None
    for dt, q in frames:
        if prev is not None:
            dt = max(dt, max(abs(a - b) for a, b in zip(q, prev)) / MAXV)
        t += dt
        keys.append((t if prev is not None else 0.0, q))
        prev = q
    rows = []
    for (ta, qa), (tb, qb) in zip(keys, keys[1:]):
        n = max(1, int(round((tb - ta) * 50)))
        for s in range(n):
            u = s / n
            u = u * u * (3 - 2 * u)
            rows.append([ta + (tb - ta) * s / n] + [a + (b - a) * u for a, b in zip(qa, qb)])
    rows.append([keys[-1][0]] + list(keys[-1][1]))
    return rows


def main():
    sys.path.insert(0, os.path.join(R1, "sim"))
    sys.argv = sys.argv[:1]
    import r1sim
    global SIM, LIMITS
    sim = SIM = r1sim.Sim()
    LIMITS = []
    for a in sim.adr:
        if a is None or not sim.m.jnt_limited[a[0]]:
            LIMITS.append((None, None))
        else:
            LIMITS.append(tuple(float(v) * 0.97 for v in sim.m.jnt_range[a[0]]))
    import numpy as np
    sim.pose(np.zeros(13))
    for c in sim.d.contact[:sim.d.ncon]:
        if c.dist <= -0.005:
            BASE.add(tuple(sorted((sim.m.geom_bodyid[c.geom1], sim.m.geom_bodyid[c.geom2]))))
    ok = bad = 0
    for mv in MOVES:
        rows = build(mv)
        csv_name = "m_" + mv["name"]
        with open(os.path.join(LIB, "arm", csv_name + ".csv"), "w") as f:
            f.write("t,lsp,lsr,lsy,le,lwr,rsp,rsr,rsy,re,rwr,waist_yaw,head_pitch,head_yaw\n")
            for r in rows:
                f.write(",".join("%.4f" % v for v in r) + "\n")
        seq = [{"hand": {"side": side, "pose": p}} if i == 0 or t == 0 else None for i, (t, side, p) in enumerate(mv["hands"])]
        hand_steps, last_t = [], 0.0
        for t, side, p in mv["hands"]:
            if t > last_t:
                hand_steps.append({"wait": round(t - last_t, 2)})
                last_t = t
            hand_steps.append({"hand": {"side": side, "pose": p}})
        par = [{"arm_traj": {"file": csv_name}}]
        if hand_steps:
            par.append(hand_steps[0] if len(hand_steps) == 1 else {"repeat": {"times": 1, "steps": hand_steps}})
        if mv["say"]:
            par.append({"say": {"text": mv["say"], "voice": "eleven"}})
        steps = [{"parallel": par}, {"hand": {"side": "both", "pose": "open", "ms": 500}}]
        doc = {"kind": "dance", "title": mv["title"], "category": mv["category"], "emoji": mv["emoji"],
               "seconds": round(rows[-1][0], 1), "steps": steps}
        with open(os.path.join(LIB, "dances", mv["name"] + ".yaml"), "w") as f:
            f.write("# generated by studio/tools/make_moves.py (upper body only; checked on Unitree's R1 model)\n")
            yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False)
        tl = r1sim.Timeline()
        tl.play_csv(os.path.join(LIB, "arm", csv_name + ".csv"))
        problems = [p for p in sim.check(tl) if "❌" in p]
        status = "✅" if not problems else "❌ " + "; ".join(problems[:2])
        ok += not problems
        bad += bool(problems)
        print("%-16s %-10s %4.1fs %s" % (mv["name"], mv["category"], rows[-1][0], status))
    print("\n%d ok · %d need fixing · %d moves" % (ok, bad, len(MOVES)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
