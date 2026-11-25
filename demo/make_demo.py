"""Makes the 60-second narrated demo video of the WhosOn flow.

Run:  python demo/make_demo.py   (needs: pip install pillow imageio-ffmpeg; the narration uses macOS `say`)
Output: demo/whoson-demo.mp4
Everything shown is made up (the same synthetic players as the phone prototype). Nothing real is drawn or sent.
"""
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "whoson-demo.mp4"
W, H, FPS = 1280, 720, 15
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

BG, INK, MUTED = (245, 242, 234), (27, 36, 32), (96, 110, 102)
GREEN, GREEN_SOFT, LINE = (31, 93, 70), (222, 237, 229), (217, 223, 218)
AMBER, AMBER_SOFT, RED, RED_SOFT, WHITE = (179, 92, 0), (253, 238, 214), (176, 52, 52), (250, 225, 225), (255, 255, 255)


def font(size, bold=False):
    return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size, index=1 if bold else 0)


# ------------------------------------------------------------------ the story: (caption headline, small label, narration)
SCENES = [
    ("Meet the co-captain", "WHOSON",
     "Every week, league captains scramble to find out who can play, and to build a lineup that follows ALTA's rules. Meet Whos On."),
    ("Set up in minutes", "1  SET UP",
     "Setup takes minutes. Captains upload the team roster, and the ALTA schedule P D F, exactly as it came."),
    ("It reads messy replies", "2  ASK THE PLAYERS",
     "The agent emails each player and reads their messy replies. If it is unsure, it asks one follow-up question."),
    ("One digest, not fifty texts", "3  PLAN THE LINEUP",
     "Captains get one digest, not fifty messages. The planner proposes a legal lineup and explains every line."),
    ("Rules checked. Captain approves.", "4  APPROVE AND ENTER",
     "A rules checker can veto any lineup. The captain approves with one tap, and receives an entry sheet to copy into ALTA."),
    ("Captains stay in charge", "WHOSON",
     "The captain stays in charge. The agent never publishes to ALTA for the captain."),
]
MAX_TOTAL = 60.0
SCENE_LEN = [11.5, 9.0, 9.5, 9.5, 12.0, 8.5]   # seconds on screen, adds up to 60
ANIM_LEN = [3.0, 7.5, 9.0, 8.0, 8.0, 3.0]        # how long each scene's animation was designed to take


# ------------------------------------------------------------------ drawing helpers
def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def prog(t, start, dur=0.5):
    return ease((t - start) / dur)


def layer(base, fn, p, dy=18):
    """Draw fn(draw) on a transparent layer and composite it with opacity p, sliding up by dy*(1-p)."""
    if p <= 0:
        return
    lay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    fn(ImageDraw.Draw(lay))
    if p < 1:
        a = lay.getchannel("A").point(lambda v: int(v * p))
        lay.putalpha(a)
    base.alpha_composite(lay, (0, int(round(dy * (1 - p)))))


def rrect(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def text(d, xy, s, size, fill=INK, bold=False, anchor="la"):
    d.text(xy, s, font=font(size, bold), fill=fill, anchor=anchor)


def wrap(s, size, width, bold=False):
    f, words, lines, cur = font(size, bold), s.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if f.getlength(trial) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def check(d, cx, cy, r=13, color=GREEN):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    d.line([(cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)], fill=WHITE, width=3, joint="curve")


def chip(d, x, y, label, fg, bg, size=17):
    w = font(size, True).getlength(label) + 26
    rrect(d, (x, y, x + w, y + size + 14), (size + 14) // 2, fill=bg)
    text(d, (x + 13, y + 6), label, size, fg, True)
    return w


def caption(img, t, i, t_scene):
    head, label, _ = SCENES[i]

    def f(d):
        text(d, (70, 150), label, 20, GREEN, True)
        y = 188
        for line in wrap(head, 54, 440, True):
            text(d, (70, y), line, 54, INK, True)
            y += 64
    layer(img, f, prog(t_scene, 0.1, 0.6))


def phone(d, x, y, w=330, h=610):
    rrect(d, (x, y, x + w, y + h), 44, fill=(30, 34, 32))
    rrect(d, (x + 10, y + 10, x + w - 10, y + h - 10), 36, fill=WHITE)
    rrect(d, (x + w // 2 - 50, y + 16, x + w // 2 + 50, y + 30), 7, fill=(30, 34, 32))
    return (x + 10, y + 10, x + w - 10, y + h - 10)


# ------------------------------------------------------------------ scenes (each draws the right-hand visual)
def scene_title(img, t):
    def f(d):
        text(d, (780, 300), "WhosOn", 120, GREEN, True, "mm")
        text(d, (780, 420), "for ALTA adult league captains", 26, MUTED, False, "mm")
        text(d, (780, 470), "Email first.  Captains approve everything.", 22, INK, True, "mm")
    layer(img, f, prog(t, 0.3, 0.8))


def scene_setup(img, t):
    rows = [("League", "Sunday Women · Fall 2026 · AA-3", "Confirmed"),
            ("Roster", "roster.xlsx", "14 players found"),
            ("Schedule", "ALTA schedule.pdf (as downloaded)", "7 matches found")]

    def card(d):
        rrect(d, (560, 130, 1220, 600), 22, fill=WHITE, outline=LINE, width=2)
        text(d, (596, 160), "Team setup", 28, INK, True)
        text(d, (596, 200), "One private link, about 10 minutes, once per season.", 18, MUTED)
    layer(img, card, prog(t, 0.2))
    for k, (name, what, result) in enumerate(rows):
        start = 1.0 + k * 1.9

        def row(d, k=k, name=name, what=what, result=result, start=start):
            y = 250 + k * 108
            rrect(d, (596, y, 1184, y + 92), 14, fill=BG)
            text(d, (620, y + 14), name.upper(), 15, MUTED, True)
            text(d, (620, y + 38), what, 21, INK, False)
            text(d, (620, y + 64), result, 17, GREEN, True) if t > start + 0.9 else None
            if t > start + 0.9:
                check(d, 1150, y + 46)
        layer(img, row, prog(t, start))


def scene_replies(img, t):
    items = [("Carla", "can't, my kid has a recital", "OUT", RED, RED_SOFT),
             ("Lena", "I can play but I have to leave by 4", "PLAYS · until 4:00 PM", GREEN, GREEN_SOFT),
             ("Isla", "maybe? depends on work", "NOT SURE · asking", AMBER, AMBER_SOFT)]
    text_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    del text_layer
    for k, (who, msg, tag, fg, bg) in enumerate(items):
        start = 0.6 + k * 2.4

        def row(d, k=k, who=who, msg=msg, tag=tag, fg=fg, bg=bg, start=start):
            y = 150 + k * 128
            bw = font(21).getlength(msg) + 44
            rrect(d, (560, y, 560 + bw, y + 58), 22, fill=(233, 236, 234))
            text(d, (582, y + 17), msg, 21, INK)
            text(d, (562, y - 20), who, 15, MUTED, True)
            if t > start + 0.9:
                d.line([(560 + bw + 14, y + 29), (560 + bw + 44, y + 29)], fill=MUTED, width=3)
                d.polygon([(560 + bw + 44, y + 22), (560 + bw + 54, y + 29), (560 + bw + 44, y + 36)], fill=MUTED)
                chip(d, 560 + bw + 66, y + 12, tag, fg, bg)
        layer(img, row, prog(t, start))

    def follow(d):
        y = 150 + 2 * 128 + 70
        rrect(d, (560, y, 1130, y + 76), 20, fill=GREEN_SOFT)
        text(d, (582, y + 12), "Agent to Isla", 14, GREEN, True)
        text(d, (582, y + 36), "Quick check: can you confirm by Friday noon?", 20, INK)
    layer(img, follow, prog(t, 0.6 + 2 * 2.4 + 1.8))
    layer(img, lambda d: text(d, (560, 600), "Every guess is shown to the captain. When unsure, it asks.", 19, MUTED), prog(t, 7.0))


def scene_digest(img, t):
    def f(d):
        x0, y0, x1, y1 = phone(d, 640, 70)
        text(d, (x0 + 20, y0 + 44), "Week 1 · at Team 6 · Sun Sep 13", 15, MUTED, True)
        text(d, (x0 + 20, y0 + 68), "Captain's digest", 28, INK, True)
        rrect(d, (x0 + 14, y0 + 112, x1 - 14, y0 + 164), 14, fill=BG)
        text(d, (x0 + 28, y0 + 128), "11 can play · 2 out · 1 asking", 19, INK, True)
    layer(img, f, prog(t, 0.3))

    def alert(d):
        x0, y0, x1, y1 = 650, 70, 960, 680
        rrect(d, (x0 + 14, y0 + 190, x1 - 14, y0 + 262), 14, fill=AMBER_SOFT)
        text(d, (x0 + 28, y0 + 200), "Needs the captain", 14, AMBER, True)
        text(d, (x0 + 28, y0 + 222), "Lena leaves by 4:00.", 16, INK)
        text(d, (x0 + 28, y0 + 242), "Line 5 may run late.", 16, INK)
    layer(img, alert, prog(t, 1.6))

    lines = [("1D", "Ava Chen + Brooke Patel", "same pair · R5"), ("2D", "Dana Kim + Lena Fischer", "new pair · R6"),
             ("3D", "Ellie Brooks + Fran Okafor", "same pair · R5"), ("4D", "Maya Singh + Priya Shah", "same pair · R5"),
             ("5D", "Hana Sato + Sam Torres", "same pair · R5")]
    for k, (ln, who, why) in enumerate(lines):
        def row(d, k=k, ln=ln, who=who, why=why):
            x0, y0 = 660, 70 + 10 + 290 + k * 62
            rrect(d, (x0, y0, x0 + 290, y0 + 54), 10, fill=(247, 249, 247), outline=LINE)
            text(d, (x0 + 12, y0 + 7), ln, 16, GREEN, True)
            text(d, (x0 + 50, y0 + 6), who, 14, INK, True)
            text(d, (x0 + 50, y0 + 28), why, 13, AMBER if "R6" in why else MUTED)
        layer(img, row, prog(t, 3.0 + k * 0.55, 0.4), 10)

    def note(d):
        text(d, (1010, 330), "Every line has a", 20, MUTED)
        text(d, (1010, 358), "reason and a rule", 20, MUTED)
        text(d, (1010, 386), "number. The code,", 20, MUTED)
        text(d, (1010, 414), "not the AI, decides", 20, INK, True)
        text(d, (1010, 442), "who is legal.", 20, INK, True)
    layer(img, note, prog(t, 6.0))


def scene_approve(img, t):
    rules = ["R1 format", "R2 roster", "R3 one line", "R4 availability", "R5 pair moves", "R6 player moves", "R7 sandbagging"]

    def box(d):
        rrect(d, (560, 110, 900, 640), 22, fill=WHITE, outline=LINE, width=2)
        text(d, (586, 134), "Rules checker", 24, INK, True)
    layer(img, box, prog(t, 0.2))
    for k, r in enumerate(rules):
        def row(d, k=k, r=r):
            y = 184 + k * 44
            check(d, 600, y + 12, 12)
            text(d, (626, y), r, 20, INK)
        layer(img, row, prog(t, 0.8 + k * 0.35, 0.3), 8)

    def btn(d):
        approved = t > 4.6
        rrect(d, (586, 520, 874, 590), 16, fill=GREEN if approved else INK)
        text(d, (730, 555), "Approved" if approved else "Approve lineup", 24, WHITE, True, "mm")
    layer(img, btn, prog(t, 3.4))

    def sheet(d):
        x0, y0 = 930, 110
        rrect(d, (x0, y0, 1240, 640), 18, fill=WHITE, outline=LINE, width=2)
        text(d, (x0 + 18, y0 + 18), "EMAIL TO THE CAPTAIN", 13, MUTED, True)
        text(d, (x0 + 18, y0 + 40), "Copy this into ALTA", 21, INK, True)
        text(d, (x0 + 18, y0 + 76), "2026 Fall Sunday Women AA-3", 14, GREEN, True)
        text(d, (x0 + 18, y0 + 96), "Week 1 (Sep 13) AT TEAM 6", 13, MUTED)
        rows = [("1D", "AVA CHEN / BROOKE PATEL", "1:00 PM"), ("2D", "DANA KIM / LENA FISCHER", "1:00 PM"),
                ("3D", "ELLIE BROOKS / FRAN OKAFOR", "2:00 PM"), ("4D", "MAYA SINGH / PRIYA SHAH", "2:00 PM"),
                ("5D", "HANA SATO / SAM TORRES", "3:00 PM")]
        for k, (a, b, c) in enumerate(rows):
            y = y0 + 130 + k * 56
            d.line([(x0 + 18, y - 6), (x0 + 292, y - 6)], fill=LINE)
            text(d, (x0 + 18, y + 4), a, 15, INK, True)
            text(d, (x0 + 52, y), b, 12, INK, True)
            text(d, (x0 + 52, y + 18), c, 12, MUTED)
        rrect(d, (x0 + 18, y0 + 424, x0 + 292, y0 + 500), 10, fill=AMBER_SOFT)
        for n, ln in enumerate(wrap("The captain presses Publish on ALTA. The agent never logs in.", 13, 250, True)):
            text(d, (x0 + 30, y0 + 436 + n * 20), ln, 13, AMBER, True)
    layer(img, sheet, prog(t, 5.6, 0.7), 30)


def scene_end(img, t):
    def f(d):
        text(d, (640, 230), "Captains stay in charge.", 66, GREEN, True, "mm")
        y = 330
        for ln in ["Captain approves every lineup.", "Captain approves every team message.", "Presses Publish on ALTA personally."]:
            check(d, 380, y + 14, 13)
            text(d, (412, y), ln, 30, INK)
            y += 54
        text(d, (640, 560), "Prototype demo · all names and data are made up", 18, MUTED, False, "mm")
    layer(img, f, prog(t, 0.3, 0.8))


VISUALS = [scene_title, scene_setup, scene_replies, scene_digest, scene_approve, scene_end]


# ------------------------------------------------------------------ narration and timing
PREFERRED_VOICES = ["Ava (Premium)", "Nora", "Zoe (Premium)", "Evan (Premium)", "Allison (Premium)", "Nicky (Premium)", "Ava (Enhanced)",
                    "Zoe (Enhanced)", "Allison (Enhanced)", "Samantha (Enhanced)", "Flo (English (US))", "Samantha"]


def pick_voice():
    import os
    if os.environ.get("VOICE"):
        return os.environ["VOICE"]
    have = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    for v in PREFERRED_VOICES:
        if any(line.startswith(v + " ") for line in have.splitlines()):
            return v
    # Siri voices do not show up in `say -v ?` but still work by name
    probe = subprocess.run(["say", "-v", "Nora", "-o", "/dev/null", "."], capture_output=True)
    if probe.returncode == 0:
        return "Nora"
    return "Samantha"


def narrate(tmp):
    voice = pick_voice()
    print("voice:", voice)
    clips, durs = [], []
    for i, (_, _, line) in enumerate(SCENES):
        aiff = tmp / f"s{i}.aiff"
        subprocess.run(["say", "-v", voice, "-r", "152", "-o", str(aiff), line], check=True)
        wav = tmp / f"s{i}.wav"
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(aiff), "-ar", "44100", "-ac", "1", str(wav)], check=True)
        info = subprocess.run([FFMPEG, "-i", str(wav)], capture_output=True, text=True).stderr
        h, m, s = info.split("Duration:")[1].split(",")[0].strip().split(":")
        clips.append(wav)
        durs.append(int(h) * 3600 + int(m) * 60 + float(s))
    return clips, durs


def main():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        clips, durs = narrate(tmp)
        scene_len = SCENE_LEN
        print("narration", [round(x, 1) for x in durs], "scene", scene_len, "total", sum(scene_len))
        for i, (d, L) in enumerate(zip(durs, scene_len)):
            if d + 0.6 > L:
                sys.exit(f"Narration for scene {i + 1} is {d:.1f}s but the scene is only {L}s")
        starts = [sum(scene_len[:i]) for i in range(len(scene_len))]

        frames_dir = tmp / "frames"
        frames_dir.mkdir()
        n = int(round(MAX_TOTAL * FPS))
        for f in range(n):
            t = f / FPS
            i = max(k for k in range(len(starts)) if starts[k] <= t)
            ts = (t - starts[i]) * min(1.0, ANIM_LEN[i] / scene_len[i])
            img = Image.new("RGBA", (W, H), BG + (255,))
            d = ImageDraw.Draw(img)
            d.rectangle((0, 0, W, 8), fill=GREEN)
            text(d, (70, 52), "WhosOn", 22, GREEN, True)
            if i != 5:
                caption(img, t, i, ts)
            VISUALS[i](img, ts)
            # progress bar
            d = ImageDraw.Draw(img)
            d.rectangle((0, H - 6, int(W * t / MAX_TOTAL), H), fill=GREEN)
            img.convert("RGB").save(frames_dir / f"f{f:05d}.png")

        # audio: place each clip at its scene start
        inputs, delays = [], []
        for i, c in enumerate(clips):
            inputs += ["-i", str(c)]
            delays.append(f"[{i}:a]adelay={int((starts[i] + 0.3) * 1000)}:all=1[a{i}]")
        mix = ";".join(delays) + ";" + "".join(f"[a{i}]" for i in range(len(clips))) + f"amix=inputs={len(clips)}:normalize=0[am];[am]apad[aout]"
        audio = tmp / "audio.wav"
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", *inputs, "-filter_complex", mix, "-map", "[aout]", "-t", str(MAX_TOTAL), str(audio)], check=True)
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames_dir / "f%05d.png"), "-i", str(audio),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-shortest", str(OUT)], check=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
