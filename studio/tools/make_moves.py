"""Move factory: writes the preset deck (arm keyframes → library/arm/m_<name>.csv + library/dances/<name>.yaml).

Upper body only (arms, waist turn, small head moves); legs stay with Unitree's balance controller.
Every move is checked on Unitree's R1 model by r1sim (joint limits, arm-body hits, speed).
Conventions measured on the model (2026-10-23):
  shoulder pitch -1.57 = arm forward, -2.9 = overhead · elbow: see elbow() (joint +1.4 straight, -0.95 folded)
  'out' = shoulder roll away from body · 'inw' = shoulder yaw turning the forearm across the body
Run:  ~/r1/sim/.venv/bin/python tools/make_moves.py
"""
import glob
import hashlib
import json
import os
import random
import sys

import yaml

R1 = os.path.expanduser("~/r1")
LIB = os.path.join(R1, "r1ctl", "library")
PEAK = 1.9  # rad/s, top joint speed of a planned move (r1_arm hard cap is 2.0)


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
FACE = arm(-0.5, -0.15, 0.13, 1.9, 1.5)   # palms turned to the face, about 6 cm clear, hands apart (searched on the model)
HEAD_TOP = arm(-2.5, 0.9, 0.3, 1.7)
SHRUG = arm(-0.2, 0.45, -0.9, 0.9, 1.2)
SALUTE = arm(-1.8, 0.5, 0.7, 1.9)


def pose(R=REST, L=REST, waist=0.0, nod=0.0, turn=0.0):
    """→ 13 joints in r1_arm order. Left arm mirrors roll/yaw/wrist signs."""
    return [L[0], L[1], -L[2], L[3], -L[4], R[0], -R[1], R[2], R[3], R[4], waist, nod, turn]


MOVES = []


def move(name, title, category, emoji, frames, hands=(), say=None, pre=None, keep_grip=False):
    """frames: [(seconds_from_previous, pose)] — first frame starts at t=0. hands: [(t, side, pose)].
    keep_grip: do not open the hands at the end (the move ends holding something)."""
    MOVES.append(dict(name=name, title=title, category=category, emoji=emoji, frames=frames, hands=hands, say=say, pre=pre, keep_grip=keep_grip))


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
     (0.9, pose(arm(-2.7, 0.35, 0.25, -0.4), arm(-2.7, 0.35, 0.25, -0.4))), (0.8, pose(arm(-2.7, 0.35, 0.25, -0.4), arm(-2.7, 0.35, 0.25, -0.4))), (0.7, pose(V_UP, V_UP)), (1.0, pose())],
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
move("victory", "Victory", "Fight", "🏆", [(0, pose()), (0.8, pose(V_UP, V_UP)), *osc(pose(V_UP, V_UP, waist=0.2), pose(V_UP, V_UP, waist=-0.2), 4, 0.4), (0.9, pose())],
     hands=[(0, "both", "fist")], say="Champion!")

# ---------------------------------------------------------------- GAMES (2026-11-06, hide behind hands, LT voice)
PEEK_OPEN = arm(-1.4, 0.8, 0, 0.3, 0.6)
THROW_LOW = arm(-1.0, 0.15, 0.25, 1.0)
THROW_HIGH = arm(-1.5, 0.15, 0.25, 1.0)
move("peekaboo", "Peekaboo", "Games", "🙈", [(0, pose()), (0.9, pose(FACE, FACE)), (1.6, pose(FACE, FACE)), (0.4, pose(PEEK_OPEN, PEEK_OPEN)), (0.9, pose(PEEK_OPEN, PEEK_OPEN)),
     (0.6, pose(FACE, FACE)), (1.0, pose(FACE, FACE)), (0.4, pose(PEEK_OPEN, PEEK_OPEN, waist=0.3)), (0.9, pose(PEEK_OPEN, PEEK_OPEN, waist=0.3)), (1.0, pose())],
     hands=[(0, "both", "open")], say="Kur aš dingau? Ku-kū!")
move("count_eyes", "Hide and seek: count", "Games", "🫣", [(0, pose()), (0.9, pose(FACE, FACE)), (5.0, pose(FACE, FACE)), (1.0, pose()), (1.0, pose(waist=0.5)), (1.0, pose(waist=-0.5)), (0.8, pose())],
     hands=[(0, "both", "open")], say="Vienas. Du. Trys. Keturi. Penki. Einu ieškoti!")
move("found_you", "Hide and seek: found you", "Games", "👉", [(0, pose()), (0.8, pose(FWD, REST)), (1.6, pose(FWD, REST)), (0.9, pose())],
     hands=[(0, "right", "point")], say="Radau tave!")
for _p, _em, _lt in (("rock", "✊", "Akmuo"), ("paper", "🖐️", "Popierius"), ("scissors", "✌️", "Žirklės")):
    move("rps_" + _p, "RPS: " + _lt, "Games", _em,
         [(0, pose()), (0.9, pose(THROW_HIGH)), *osc(pose(THROW_LOW), pose(THROW_HIGH), 6, 0.35), (2.2, pose(THROW_HIGH)), (1.0, pose())],
         hands=[(0, "right", "fist"), (3.1, "right", _p)], say="Akmuo, popierius, žirklės!")


SIM = None
LIMITS = None

# Unitree's model has no Revo2 hands, so the mujoco contact check below never saw them.
# Stand-in matching studio/web/js/robot3d.js: a capsule along the wrist link's x axis, metres.
HAND_X = [0.135 + i * 0.168 / 7 for i in range(8)]   # palm start → fingertips
HAND_R = 0.04
HEAD_C = (0.01, 0.0, 0.37)                           # torso frame, from the mesh
HEAD_R = 0.085
TORSO_LO, TORSO_HI = (-0.098, -0.10, -0.20), (0.071, 0.10, 0.26)
CLEAR_HEAD, CLEAR_BODY, CLEAR_HANDS = 0.065, 0.06, 0.055   # thumbs and fingers stick out past the capsule


def hand_gaps():
    """Clearances for the pose already set in SIM: {'L': (head, body), 'R': (head, body), 'hands': gap}, metres."""
    import numpy as np
    m, d = SIM.m, SIM.d
    t = m.body("torso_link").id
    to, tm = d.xpos[t], d.xmat[t].reshape(3, 3)
    head = to + tm @ np.array(HEAD_C)
    pts, lat, out = {}, {}, {}
    for s, name in (("L", "left_wrist_roll_link"), ("R", "right_wrist_roll_link")):
        b = m.body(name).id
        pts[s] = np.array([d.xpos[b] + d.xmat[b].reshape(3, 3) @ np.array([x, 0, 0]) for x in HAND_X])
        local = (pts[s] - to) @ tm
        lat[s] = local[:, 1]
        off = np.maximum(np.maximum(np.array(TORSO_LO) - local, local - np.array(TORSO_HI)), 0)
        out[s] = (float(np.linalg.norm(pts[s] - head, axis=1).min() - HEAD_R - HAND_R),
                  float(np.linalg.norm(off, axis=1).min() - HAND_R))
    out["hands"] = float(np.linalg.norm(pts["L"][:, None] - pts["R"][None, :], axis=2).min() - 2 * HAND_R)
    out["order"] = float((lat["L"] - lat["R"]).min())   # below 0: the hands have swapped sides
    return out


def hand_trouble(q):
    """Which hands are too close to the head, the body or each other in this pose: a set of 'L' / 'R'."""
    import numpy as np
    SIM.pose(np.array(q, float))
    g = hand_gaps()
    sides = {s for s in "LR" if g[s][0] < CLEAR_HEAD or g[s][1] < CLEAR_BODY}
    # Crossed hands are ruled out too: a pose past the crossing looks clear, but the path there goes through the hands.
    return sides | ({"L", "R"} if g["hands"] < CLEAR_HANDS or g["order"] < 0 else set())


def hits(q):
    """True if this pose makes an arm touch the body or the other arm (contacts already in rest pose ignored),
    or a hand comes too close to the head, the body or the other hand."""
    import mujoco
    import numpy as np
    if hand_trouble(q):
        return True
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
    """Straight path collides? bend it through the closest clear pose to its worst point."""
    pts = [[a + (b - a) * (u * u * (3 - 2 * u)) for a, b in zip(qa, qb)] for u in [i / 20 for i in range(1, 20)]]
    bad = [p for p in pts if hits(p)]
    if not bad or depth > 5:
        return [qb]
    mid = nearest_clear(bad[len(bad) // 2])
    if mid is None:
        return [qb]
    return repair(qa, mid, depth + 1) + repair(mid, qb, depth + 1)


FIXED = {}


def nearest_clear(q):
    """The closest pose to q that touches nothing. Moves only the arm in trouble; if both are, keeps them mirrored."""
    key = tuple(round(v, 4) for v in q)
    if key in FIXED:
        return FIXED[key]
    if not hits(q):
        FIXED[key] = list(q)
        return FIXED[key]
    rng = random.Random(str(key))
    sides = hand_trouble(q) or {"L", "R"}
    best = None
    for radius in (0.1, 0.2, 0.3, 0.45, 0.6, 0.8, 1.0, 1.3, 1.6):
        for _ in range(500):
            d = [rng.uniform(-radius, radius) for _ in range(4)]
            c = list(q)
            for i in range(4):
                if "L" in sides:
                    c[i] += d[i]
                if "R" in sides:
                    c[5 + i] += d[i] * (-1 if i in (1, 2) else 1)    # right arm: roll and yaw mirror
            c = clamp(c)
            cost = sum((a - b) ** 2 for a, b in zip(c, q))
            if (best is None or cost < best[0]) and not hits(c):
                best = (cost, c)
        if best:
            break
    FIXED[key] = best[1] if best else None
    return FIXED[key]


def fix_pose(q, name):
    """Keyframe touches itself? take the closest pose that doesn't, so the move keeps its shape."""
    c = nearest_clear(list(q))
    if c is None:
        print("   ⚠️ %s: no clear pose near this keyframe" % name)
        return list(q)
    if c != list(q):
        print("   🔧 %s: moved a keyframe by %.2f rad" % (name, max(abs(a - b) for a, b in zip(c, q))))
    return c


# ---------------------------------------------------------------- OBJECTS (soft, light things only; adult hands them over)
move("take_object", "Take an object", "Objects", "🤲", [(0, pose()), (1.0, pose(arm(-1.0, 0.25, 0.2, 0.3))), (4.0, pose(arm(-1.0, 0.25, 0.2, 0.3))), (1.2, pose(arm(-0.6, 0.2, 0.3, 1.0)))],
     hands=[(0, "right", "open"), (4.2, "right", "soft_grip")], say="Please put it in my hand. Gently!", keep_grip=True)
move("give_back", "Give it back", "Objects", "🎁", [(0, pose(arm(-0.6, 0.2, 0.3, 1.0))), (1.2, pose(arm(-1.1, 0.25, 0.2, 0.2))), (3.0, pose(arm(-1.1, 0.25, 0.2, 0.2))), (1.2, pose())],
     hands=[(0, "right", "soft_grip"), (2.0, "right", "open")], say="Here you go!")
move("soft_toss", "Soft toss (plush/foam only)", "Objects", "🧸", [(0, pose(arm(-0.6, 0.2, 0.3, 1.0))), (1.0, pose(arm(0.5, 0.2, 0, -0.6))), (0.6, pose(arm(-1.7, 0.2, 0, -0.5))), (1.0, pose())],
     hands=[(0, "right", "soft_grip"), (1.45, "right", "open")], say="Catch! Soft throw!")


# The stop-motion builder on the phone picks from these. Each one is checked below, like a move's keyframe.
PALETTE = [("Rest", "🧍", pose()), ("Both up", "🙌", pose(V_UP, V_UP)), ("Right up", "🙋", pose(UP, REST)), ("Left up", "🙋", pose(REST, UP)),
           ("Arms out", "🤸", pose(SIDE, SIDE)), ("Forward", "🧟", pose(FWD, FWD)), ("Point", "👉", pose(arm(-1.45, 0.1, 0.1, -0.9))),
           ("Guard", "🛡️", pose(GUARD, GUARD)), ("Punch", "👊", pose(GUARD, PUNCH, waist=0.15)), ("Hips", "😎", pose(HIP, HIP)),
           ("Shrug", "🤷", pose(SHRUG, SHRUG)), ("Hide face", "🙈", pose(FACE, FACE)), ("Head top", "🤯", pose(HEAD_TOP, HEAD_TOP)),
           ("Salute", "🫡", pose(SALUTE)), ("Turn left", "↩️", pose(waist=0.4)), ("Turn right", "↪️", pose(waist=-0.4))]


def smooth(rows, width=7, passes=2):
    """A bent path has corners, and a corner is a jolt in the joint. Two passes of a 0.14 s average round them off."""
    q, h = [r[1:] for r in rows], width // 2
    for _ in range(passes):
        pad = [q[0]] * h + q + [q[-1]] * h
        q = [[sum(pad[i + j][c] for j in range(width)) / width for c in range(13)] for i in range(len(q))]
    return [rows[0]] + [[r[0]] + x for r, x in zip(rows[1:-1], q[1:-1])] + [rows[-1]]


def build(mv):
    """keyframes → rows @50 Hz. Each keyframe-to-keyframe stretch is one smooth stroke, even when the path
    bends around something, and is stretched in time so its peak speed stays under PEAK."""
    fixed = [(dt, fix_pose(q, mv["name"])) for dt, q in mv["frames"]]
    prev, t, rows = fixed[0][1], 0.0, []
    for dt, q in fixed[1:]:
        path = [prev] + repair(prev, q)
        dist = [0.0]
        for a, b in zip(path, path[1:]):
            dist.append(dist[-1] + max(abs(x - y) for x, y in zip(a, b)))
        dt = max(dt, 1.5 * dist[-1] / PEAK)    # smoothstep peaks at 1.5 × the average speed
        n = max(1, int(round(dt * 50)))
        k = 0
        for i in range(n):
            u = i / n
            at = (u * u * (3 - 2 * u)) * dist[-1]
            while k + 2 < len(path) and at > dist[k + 1]:
                k += 1
            f = (at - dist[k]) / (dist[k + 1] - dist[k]) if dist[k + 1] > dist[k] else 0.0
            rows.append([t + dt * i / n] + [a + (b - a) * f for a, b in zip(path[k], path[k + 1])])
        t += dt
        prev = q
    rows.append([t] + list(prev))
    return smooth(rows)


def gaps_at(row):
    import numpy as np
    SIM.pose(np.array(row[1:], float))
    return hand_gaps()


def read_csv(path):
    rows = []
    for line in open(path):
        try:
            v = [float(c) for c in line.strip().split(",")]
        except ValueError:
            continue
        if len(v) == 14:
            rows.append(v)
    return rows


def audit(r1sim):
    """Every arm file the robot could ever play, on Unitree's body shapes plus the stand-in hands, row by row.
    Only what passes goes into arm_safe.json. The server refuses the rest on the real robot."""
    import numpy as np
    good, bad = {}, []
    files = sorted(glob.glob(os.path.join(LIB, "arm", "*.csv"))) + sorted(glob.glob(os.path.join(R1, "r1-joga", "export", "*.csv"))) \
        + sorted(glob.glob(os.path.join(R1, "r1-joga", "export", "poses", "*.csv")))
    for path in {os.path.basename(f): f for f in files}.values():
        tl = r1sim.Timeline()
        tl.play_csv(path)
        problems = [p for p in SIM.check(tl) if "❌" in p]
        gaps = [gaps_at(r) for r in read_csv(path)]
        for label, worst in (("head", min(min(g["L"][0], g["R"][0]) for g in gaps)),
                             ("body", min(min(g["L"][1], g["R"][1]) for g in gaps)),
                             ("other hand", min(g["hands"] for g in gaps))):
            if worst < 0:
                problems.append("hand into %s by %.0f cm" % (label, -worst * 100))
        name = os.path.splitext(os.path.basename(path))[0]
        if problems:
            bad.append((name, problems[0]))
        else:
            good[name] = hashlib.sha1(open(path, "rb").read()).hexdigest()[:16]
    with open(os.path.join(R1, "studio", "arm_safe.json"), "w") as f:
        json.dump(good, f, indent=0, sort_keys=True)
    print("\nBody check: %d files cleared · %d refused" % (len(good), len(bad)))
    for name, why in bad:
        print("   ❌ %-34s %s" % (name, why))
    # STOP walks the arms straight home from wherever they are. Rest on the real robot is not known yet: both guesses.
    homes = {"zeros": np.zeros(13), "elbows 1.35": np.array([0, 0, 0, 1.35, 0, 0, 0, 0, 1.35, 0, 0, 0, 0], float)}
    worst = []
    for path in sorted(glob.glob(os.path.join(LIB, "arm", "m_*.csv"))):
        low = (9.0, "", 0.0)
        for r in read_csv(path)[::10]:
            q = np.array(r[1:])
            for label, h in homes.items():
                for u in (0.1, 0.25, 0.4, 0.55, 0.7, 0.85):
                    g = gaps_at([0] + list(q + (h - q) * u))
                    low = min(low, (min(g["L"][0], g["R"][0], g["L"][1], g["R"][1], g["hands"]), label, r[0]))
        worst.append((low[0], os.path.basename(path)[2:-4], low[1], low[2]))
    print("Walk home after STOP, closest moments:")
    for g, name, label, t in sorted(worst)[:6]:
        print("   %-18s %5.1f cm  (home %s, stopped at %.1f s)" % (name, g * 100, label, t))
    return len(bad)


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
        steps = [{"parallel": par}] + ([] if mv["keep_grip"] else [{"hand": {"side": "both", "pose": "open", "ms": 500}}])
        doc = {"kind": "dance", "title": mv["title"], "category": mv["category"], "emoji": mv["emoji"],
               "seconds": round(rows[-1][0], 1), "steps": steps}
        with open(os.path.join(LIB, "dances", mv["name"] + ".yaml"), "w") as f:
            f.write("# generated by studio/tools/make_moves.py (upper body only; checked on Unitree's R1 model)\n")
            yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False)
        tl = r1sim.Timeline()
        tl.play_csv(os.path.join(LIB, "arm", csv_name + ".csv"))
        problems = [p for p in sim.check(tl) if "❌" in p]
        gaps = [gaps_at(r) for r in rows]
        for label, worst in (("head", min(min(g["L"][0], g["R"][0]) for g in gaps)),
                             ("body", min(min(g["L"][1], g["R"][1]) for g in gaps)),
                             ("other hand", min(g["hands"] for g in gaps))):
            if worst < 0:
                problems.append("hand near %s (%.0f cm)" % (label, worst * 100))
        status = "✅" if not problems else "❌ " + "; ".join(problems[:2])
        ok += not problems
        bad += bool(problems)
        print("%-16s %-10s %4.1fs %s" % (mv["name"], mv["category"], rows[-1][0], status))
    print("\n%d ok · %d need fixing · %d moves" % (ok, bad, len(MOVES)))
    palette = [{"label": n, "emoji": e, "q": [round(v, 4) for v in fix_pose(list(q), n)]} for n, e, q in PALETTE]
    with open(os.path.join(R1, "studio", "web", "poses.json"), "w") as f:
        json.dump(palette, f, ensure_ascii=False)
    audit(r1sim)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
