"""Ships the soundboard: own/CC0 kit → 16 kHz mono WAV the robot speaker can play, peak-normalised.
Run on the Mac: python3 studio/tools/make_sounds.py
Sources: ~/promo-video/assets/kris-music-kit (ElevenLabs on Kris's plan, or CC0/PD, licences in its README)."""
import array
import os
import subprocess
import sys
import wave

KIT = os.path.expanduser("~/promo-video/assets/kris-music-kit")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sounds")
FILES = {
    "Whoosh": "sfx/01-whoosh-soft.wav", "Swish": "sfx/02-swish-in.wav", "Pop": "sfx/03-pop.wav",
    "Click": "sfx/04-tick-click.wav", "Ding": "sfx/05-ding-reveal.wav", "Page flip": "sfx/06-paper-flip.wav",
    "Riser": "sfx/07-riser-subtle.wav", "Impact": "sfx/08-impact-soft.wav", "Typing": "sfx/09-typing-burst.wav",
    "Sparkle": "sfx/10-sparkle-chime.wav",
    "Calm piano": "beds/a-piano-intimate-t1.mp3", "Hopeful piano": "beds/b-piano-strings-hopeful-t1.mp3",
    "Music box": "beds/c-musicbox-celesta-fairytale-t1.mp3", "Tavern": "beds/d-tavern-lute-recorder-t1.mp3",
    "Baroque": "beds/e-baroque-harpsichord-strings-t1.mp3", "Curious piano": "beds/f-solo-piano-counterpoint-t1.mp3",
    "Vivaldi Spring": "pd/vivaldi-spring-1-allegro-modena-pd.ogg", "Bach Prelude": "pd/bach-wtc1-prelude-C-bwv846-ishizaka-cc0.ogg",
}
os.makedirs(OUT, exist_ok=True)
for name, rel in FILES.items():
    src = os.path.join(KIT, rel)
    if not os.path.exists(src):
        sys.exit("missing " + src)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         stdout=subprocess.PIPE, check=True).stdout
    a = array.array("h")
    a.frombytes(raw[:len(raw) // 2 * 2])
    peak = max(1, max(abs(v) for v in a))
    gain = min(8.0, 29000.0 / peak)
    a = array.array("h", [int(v * gain) for v in a])
    with wave.open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(a.tobytes())
    print("%-16s %6.1f s  gain %.1f" % (name, len(a) / 16000, gain))
