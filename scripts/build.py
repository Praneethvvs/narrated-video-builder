"""Build a narrated 1080p video from a project folder: TTS narration, animated HTML scenes, zoomed screen recordings,
crossfades, subtitles and chapters.

Usage (any working directory):
  python scripts/build.py init    <project>            # scaffold a project from examples/demo
  python scripts/build.py tts     <project>            # narration clips (cached by voice|speed|text)
  python scripts/build.py scenes  <project> [ids...]   # render animated scenes
  python scripts/build.py screens <project> [ids...]   # cut + zoom screen-recording segments
  python scripts/build.py final   <project> [--no-burn]
  python scripts/build.py all     <project> [--no-burn]
  python scripts/build.py still   <project> <scene_id> [t]   # one debug PNG of a scene

Project layout:
  <project>/script.yaml          narration + segments (see references/script-format.md)
  <project>/scenes/*.html        hand-written scenes (optional; built-in templates need none)
  <project>/rec/<rec>.webm|mp4   screen recordings + <rec>.json beat marks (only for screen segments)
  <project>/build/               everything generated; outputs <name>_soft.mp4, <name>_burned.mp4, <name>.srt, <name>_chapters.txt
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf
import yaml

SKILL = Path(__file__).resolve().parent.parent
ENGINE = SKILL / "engine"
sys.path.insert(0, str(ENGINE))
from render_scene import render, still  # noqa: E402
from screen_fx import filter_chain  # noqa: E402
from templates import TEMPLATES  # noqa: E402

FF = imageio_ffmpeg.get_ffmpeg_exe()
MODELS = Path(os.environ.get("NVB_MODELS", SKILL / "models"))
GSAP = Path(os.environ.get("NVB_GSAP", SKILL / "node_modules" / "gsap" / "dist"))
RATE = 24000
FPS = 30
VENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-color_range", "tv", "-r", str(FPS)]
REC_EXT = (".webm", ".mp4", ".mov", ".mkv")
NL = chr(10)

# Defaults tuned for a brisk tutorial pace. Every one can be overridden at the top of script.yaml.
DEFAULTS = {
    "name": "video", "title": "Walkthrough", "voice": "am_michael", "lang": "en-us",
    "speed": 1.12,          # Kokoro speed for every line (segment `speed:` overrides)
    "gap": 0.25,            # silence after each line / beat
    "number_hold": 0.8,     # extra hold after a line marked `hold: true` (lands a key number)
    "step_pause": 0.35,     # extra pause before a line marked `pause: true` (a calculation step)
    "lead": 0.6,            # silence at the start of every segment (must exceed xfade)
    "tail": 0.9,            # hold after the last line of a segment
    "xfade": 0.35,          # crossfade between segments
    "footer_left": "", "footer_right": "",
    "subtitle_font": "Segoe UI" if os.name == "nt" else "Arial",
    "browser_channel": None,  # e.g. "msedge" or "chrome"; default = Playwright's bundled Chromium
}

P = SCRIPT = B = AUD = CLIPS = None


def load_project(path):
    global P, SCRIPT, B, AUD, CLIPS
    P = Path(path).resolve()
    raw = yaml.safe_load(open(P / "script.yaml", encoding="utf-8"))
    SCRIPT = {**DEFAULTS, **raw}
    B = P / "build"
    AUD, CLIPS = B / "audio", B / "clips"
    for seg in SCRIPT["segments"]:
        for u in seg.get("lines", []) + seg.get("beats", []):
            u["_speed"] = seg.get("speed", SCRIPT["speed"])
            for key, default in (("hold", "number_hold"), ("pause", "step_pause")):
                if u.get(key) is True:
                    u[key] = SCRIPT[default]
                u[key] = float(u.get(key) or 0)


def ff(*args, cwd=None):
    subprocess.run([FF, "-y", "-loglevel", "error", *args], check=True, cwd=cwd)


def clean(text):
    return " ".join(str(text).split())


def browser(p):
    ch = os.environ.get("NVB_BROWSER_CHANNEL") or SCRIPT.get("browser_channel")
    return p.chromium.launch(channel=ch) if ch else p.chromium.launch()


# ---------------------------------------------------------------- narration ---------------
def units():
    for seg in SCRIPT["segments"]:
        for u in seg.get("lines", []) + seg.get("beats", []):
            if u.get("say"):
                yield seg, u


def audio_key(u):
    h = hashlib.sha1(f"{SCRIPT['voice']}|{u['_speed']}|{clean(u['say'])}".encode()).hexdigest()[:16]
    return AUD / f"{h}.wav"


def cmd_tts():
    AUD.mkdir(parents=True, exist_ok=True)
    kokoro, n = None, 0
    for seg, u in units():
        wav = audio_key(u)
        if wav.exists():
            continue
        if kokoro is None:
            from kokoro_onnx import Kokoro
            onnx, voices = MODELS / "kokoro-v1.0.onnx", MODELS / "voices-v1.0.bin"
            if not onnx.exists():
                sys.exit(f"Kokoro model missing in {MODELS}. Run: python scripts/setup.py")
            kokoro = Kokoro(str(onnx), str(voices))
        samples, rate = kokoro.create(clean(u["say"]), voice=SCRIPT["voice"], speed=u["_speed"], lang=SCRIPT["lang"])
        idx = np.where(np.abs(samples) > 0.01)[0]
        if len(idx):  # trim leading/trailing silence so the timing values mean what they say
            samples = samples[max(0, idx[0] - int(0.04 * rate)): idx[-1] + int(0.12 * rate)]
        sf.write(wav, samples, rate)
        n += 1
        print(f"tts {seg['id']}: {len(samples) / rate:.1f}s  {clean(u['say'])[:60]}")
    total = sum(dur(u) for _, u in units())
    print(f"rendered {n} new clips; narration total {total / 60:.1f} min")


def dur(u):
    info = sf.info(str(audio_key(u)))
    return info.frames / info.samplerate


def load(u):
    data, rate = sf.read(str(audio_key(u)), dtype="float32")
    assert rate == RATE
    return data


# ---------------------------------------------------------------- scenes ------------------
def scene_timeline(seg):
    """Cue times for a scene: each line starts after the previous line + gap + hold (+ its own pause)."""
    if not seg.get("lines"):
        return {}, [], float(seg.get("duration", 2.2))
    t, cues, placed = SCRIPT["lead"], {}, []
    for ln in seg["lines"]:
        t += ln["pause"]
        if ln.get("cue"):
            cues[ln["cue"]] = round(t, 3)
        placed.append((t, ln))
        t += dur(ln) + SCRIPT["gap"] + ln["hold"]
    total = t - SCRIPT["gap"] + seg.get("tail", SCRIPT["tail"])
    return cues, placed, total


def head_html():
    css = (ENGINE / "scene.css").as_uri()
    js = "".join(f'<script src="{(GSAP / f).as_uri()}"></script>' for f in ("gsap.min.js", "DrawSVGPlugin.min.js", "SplitText.min.js"))
    pal = SCRIPT.get("palette") or {}
    over = f"<style>:root {{ {' '.join(f'--{k}: {v};' for k, v in pal.items())} }}</style>" if pal else ""
    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{css}">{over}{js}'
            f'<script src="{(ENGINE / "kit.js").as_uri()}"></script>')


def foot_html(seg):
    left = seg.get("footer_left", SCRIPT["footer_left"])
    right = seg.get("footer_right", SCRIPT["footer_right"])
    return f'<div class="foot"><span>{left}</span><span>{right}</span></div>' if (left or right) else ""


def scene_file(seg):
    """HTML for a scene: a built-in template (`template:` + `data:`) or a project file (`html:`), with {{VARS}} filled."""
    if not GSAP.exists():
        sys.exit(f"GSAP not found at {GSAP}. Run: python scripts/setup.py")
    head, foot = head_html(), foot_html(seg)
    if seg.get("template"):
        src = TEMPLATES[seg["template"]](seg.get("data", {}), head, foot)
    else:
        src = (P / seg.get("dir", "scenes") / seg["html"]).read_text(encoding="utf-8")
    for k, v in {"HEAD": head, "FOOT": foot, **(seg.get("vars") or {})}.items():
        src = src.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{[A-Z0-9_]+\}\}", src)
    if left:
        raise ValueError(f"{seg['id']}: unfilled template vars {sorted(set(left))}")
    out = B / "scenes" / f"{seg['id']}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(src, encoding="utf-8")
    return out


def cmd_scenes(ids):
    from playwright.sync_api import sync_playwright
    CLIPS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        br = browser(p)
        page = br.new_page(viewport={"width": 1920, "height": 1080})
        for seg in SCRIPT["segments"]:
            if seg["kind"] != "scene" or (ids and seg["id"] not in ids):
                continue
            cues, placed, total = scene_timeline(seg)
            out = CLIPS / f"{seg['id']}.mp4"
            shots, n = render(page, scene_file(seg), cues, total, out)
            meta = {"total": total, "cues": cues, "units": [[t, clean(ln["say"])] for t, ln in placed if ln.get("say")]}
            (CLIPS / f"{seg['id']}.json").write_text(json.dumps(meta, indent=1))
            print(f"scene {seg['id']}: {total:.1f}s ({shots}/{n} frames rendered)")
        br.close()


# ---------------------------------------------------------------- screens -----------------
ACT_FPS, ACT_PIXELS = 15, 14


def rec_video(rec):
    for ext in REC_EXT:
        f = P / "rec" / f"{rec}{ext}"
        if f.exists():
            return f
    sys.exit(f"recording rec/{rec}.(webm|mp4|mov|mkv) not found")


def activity(rec):
    """Per-frame changed-pixel counts, used to find where on-screen action ends (cached)."""
    cache = B / "cache" / f"{rec}_activity.npy"
    if cache.exists():
        return np.load(cache)
    cache.parent.mkdir(parents=True, exist_ok=True)
    w, h = 480, 270
    raw = subprocess.run([FF, "-loglevel", "error", "-i", str(rec_video(rec)),
                          "-vf", f"fps={ACT_FPS},scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                         check=True, capture_output=True).stdout
    fr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, h, w).astype(np.int16)
    diff = np.zeros(len(fr), dtype=np.int32)
    diff[1:] = (np.abs(fr[1:] - fr[:-1]) > 25).reshape(len(fr) - 1, -1).sum(axis=1)
    np.save(cache, diff)
    return diff


def last_active(act, a, b):
    i0, i1 = int(a * ACT_FPS), min(int(b * ACT_FPS), len(act))
    idx = np.where(act[i0:i1] >= ACT_PIXELS)[0]
    return a if not len(idx) else (i0 + idx[-1] + 1) / ACT_FPS


def screen_plan(seg):
    """Pieces of the recording to keep. Each beat keeps max(narration, on-screen action); idle time beyond that is
    trimmed, and if the narration outlasts the recorded beat the last frame is frozen. Actions are never cut."""
    meta = json.loads((P / "rec" / f"{seg['rec']}.json").read_text())
    marks = [(m["beat"], m["t"]) for m in meta["marks"]]
    order = [b for b, _ in marks]
    times = dict(marks)
    act = activity(seg["rec"])
    lead, gap, tail = SCRIPT["lead"], SCRIPT["gap"], SCRIPT["tail"]
    pieces, beats, clip_t = [], [], 0.0
    first = seg["beats"][0]["id"]
    pieces.append((max(0.0, times[first] - lead), times[first], 0.0))
    clip_t += times[first] - pieces[0][0]
    cuts = sorted(tuple(c) for c in seg.get("cuts", []))
    for k, beat in enumerate(seg["beats"]):
        if beat["id"] not in times:
            sys.exit(f"{seg['id']}: beat '{beat['id']}' has no mark in rec/{seg['rec']}.json")
        i = order.index(beat["id"])
        if i + 1 >= len(order):
            sys.exit(f"{seg['id']}: beat '{beat['id']}' needs a following mark (add an 'end' mark)")
        s, e = times[beat["id"]], times[order[i + 1]]
        need = dur(beat) + gap + beat["hold"] + (tail if k == len(seg["beats"]) - 1 else 0)
        acted = last_active(act, s, e - 0.5) - s + 0.35
        cut_len = sum(max(0, min(cb, e) - max(ca, s)) for ca, cb in cuts)
        avail = (e - s) - cut_len
        keep = min(avail, max(need, acted - cut_len))
        freeze = max(0.0, need - avail)
        beats.append((clip_t, beat))
        cur, remaining = s, keep
        for ca, cb in cuts + [(1e9, 1e9)]:
            if cb <= cur:
                continue
            if ca > cur:
                take = min(remaining, ca - cur)
                if take > 0.02:
                    pieces.append((cur, cur + take, 0.0))
                    remaining -= take
                if remaining <= 0.02:
                    break
            cur = max(cur, cb)
        if freeze > 0:
            a, b, _ = pieces[-1]
            pieces[-1] = (a, b, freeze)
        clip_t += keep + freeze
    return pieces, beats, clip_t


def lower_third(label):
    """Small caption card naming the screen, rendered once to a transparent PNG."""
    from playwright.sync_api import sync_playwright
    d = B / "lt"
    d.mkdir(parents=True, exist_ok=True)
    out = d / (re.sub(r"[^A-Za-z0-9]+", "_", label) + ".png")
    if out.exists():
        return out
    accent = (SCRIPT.get("palette") or {}).get("accent", "#2a78d6")
    html = f"""<html><body style="margin:0;background:transparent;">
<div style="display:inline-flex;align-items:center;gap:16px;background:#ffffff;border-radius:14px;padding:14px 26px 14px 18px;
box-shadow:0 6px 24px rgba(15,23,42,.18);font-family:'Segoe UI',Arial,sans-serif;">
<div style="width:8px;height:40px;border-radius:4px;background:{accent};"></div>
<div style="font-size:30px;font-weight:700;color:#1b2540;">{label}</div></div></body></html>"""
    with sync_playwright() as pw:
        br = browser(pw)
        pg = br.new_page(viewport={"width": 900, "height": 120})
        pg.set_content(html)
        pg.locator("div").first.screenshot(path=str(out), omit_background=True)
        br.close()
    return out


def cmd_screens(ids):
    CLIPS.mkdir(parents=True, exist_ok=True)
    gap = SCRIPT["gap"]
    for seg in SCRIPT["segments"]:
        if seg["kind"] != "screen" or (ids and seg["id"] not in ids):
            continue
        pieces, beats, total = screen_plan(seg)
        zooms, boxes, spots = [], [], []
        for off, beat in beats:
            d = dur(beat)
            for zm in beat.get("zooms", []):
                zooms.append({"a": off + zm.get("at", 0.2), "b": off + zm.get("until", d + gap),
                              "cx": zm["cx"], "cy": zm["cy"], "z": zm["z"]})
            for sp in beat.get("spots", []):
                spots.append({"a": off + sp.get("at", 0.3), "b": off + sp.get("until", d + gap),
                              "x": sp["x"], "y": sp["y"], "w": sp["w"], "h": sp["h"]})
            for bx in beat.get("boxes", []):
                boxes.append({"a": off + bx.get("at", 0.3), "b": off + bx.get("until", d),
                              "x": bx["x"], "y": bx["y"], "w": bx["w"], "h": bx["h"]})
        for m in seg.get("masks", []):  # solid boxes that hide sensitive areas, in clip seconds
            boxes.append({"a": m.get("from", 0), "b": m.get("until", 1e6), "x": m["x"], "y": m["y"], "w": m["w"], "h": m["h"],
                          "fill": True, "color": m.get("color", "0xF7F8FA")})
        parts = []
        for i, (a, b, fz) in enumerate(pieces):
            pad = f",tpad=stop_mode=clone:stop_duration={fz:.3f}" if fz > 0 else ""
            parts.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS,fps={FPS}{pad}[p{i}]")
        graph = ";".join(parts) + ";" + "".join(f"[p{i}]" for i in range(len(pieces))) + \
            f"concat=n={len(pieces)}:v=1:a=0,scale=1920:1080,setsar=1,{filter_chain(zooms, spots, boxes)}[v0]"
        extra = []
        if seg.get("lower_third"):
            png = lower_third(seg["lower_third"])
            extra = ["-loop", "1", "-t", f"{total:.3f}", "-i", str(png)]
            graph += (";[1:v]format=rgba,fade=t=in:st=0.3:d=0.45:alpha=1,fade=t=out:st=3.4:d=0.45:alpha=1[lt]"
                      ";[v0][lt]overlay=x=48:y=860:format=auto,format=yuv420p[v]")
        else:
            graph += ";[v0]null[v]"
        out = CLIPS / f"{seg['id']}.mp4"
        ff("-i", str(rec_video(seg["rec"])), *extra, "-filter_complex", graph, "-map", "[v]", *VENC, "-t", f"{total:.3f}", str(out))
        meta = {"total": total, "units": [[off, clean(b["say"])] for off, b in beats]}
        (CLIPS / f"{seg['id']}.json").write_text(json.dumps(meta, indent=1))
        print(f"screen {seg['id']}: {total:.1f}s, {len(pieces)} pieces, {len(zooms)} zooms, {len(boxes)} boxes")


# ---------------------------------------------------------------- final -------------------
def wrap(text, width=42):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def balance(text, width=44):
    """Split a subtitle cue into two lines of similar length."""
    if len(text) <= width:
        return text
    words, best = text.split(), None
    for i in range(1, len(words)):
        l1, l2 = " ".join(words[:i]), " ".join(words[i:])
        if len(l1) <= width + 4 and len(l2) <= width + 4:
            score = abs(len(l1) - len(l2))
            if best is None or score < best[0]:
                best = (score, l1 + NL + l2)
    return best[1] if best else NL.join(wrap(text)[:2])


def cues_for(text, limit=86):
    """Break a line into subtitle cues at sentence ends, then evenly by length."""
    sentences = re.split(r"(?<=[.?!])\s+", clean(text))
    chunks = []
    for s in sentences:
        k = max(1, math.ceil(len(s) / limit))
        target, cur = len(s) / k, ""
        for w in s.split():
            if cur and len(cur) + 1 + len(w) > target + 6:
                chunks.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        chunks.append(cur)
    merged = []
    for c in chunks:
        if merged and (len(merged[-1]) < 22 or len(c) < 22) and len(merged[-1]) + 1 + len(c) <= limit:
            merged[-1] = f"{merged[-1]} {c}"
        else:
            merged.append(c)
    return [balance(c) for c in merged]


def fmt_srt(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def cmd_final(burn=True):
    segs, name, xf = SCRIPT["segments"], SCRIPT["name"], SCRIPT["xfade"]
    metas = [json.loads((CLIPS / f"{s['id']}.json").read_text()) for s in segs]
    starts, t = [], 0.0
    for m in metas:
        starts.append(t)
        t += m["total"] - xf
    total = t + xf
    track = np.zeros(int((total + 1) * RATE), dtype="float32")
    srt, chapters = [], []
    for seg, m, st in zip(segs, metas, starts):
        if seg.get("chapter"):
            chapters.append((st, seg["chapter"]))
        spoken = [u for u in seg.get("lines", []) + seg.get("beats", []) if u.get("say")]
        for (off, text), u in zip(m["units"], spoken):
            assert clean(u["say"]) == text, f"{seg['id']}: clip metadata is stale, re-render scenes/screens"
            data = load(u)
            i = int((st + off) * RATE)
            track[i:i + len(data)] += data
            d = len(data) / RATE
            # `sub:` lets subtitles show digits ("$875,000") while the voice reads words
            text = re.sub(r"(\$[\d,.]+) (billion|million|thousand)", "\\1\u2060\\2", clean(u.get("sub") or u["say"]))
            cs = [c.replace("\u2060", " ") for c in cues_for(text)]
            chars = sum(len(c) for c in cs)
            tt = st + off
            for c in cs:
                dd = d * len(c) / chars
                srt.append((tt, tt + dd - 0.05, c))
                tt += dd
    wav = B / f"{name}_narration.wav"
    sf.write(wav, track[: int(total * RATE)], RATE)
    srt_name = f"{name}.srt"
    (B / srt_name).write_text(NL.join(f"{i}{NL}{fmt_srt(a)} --> {fmt_srt(b)}{NL}{c}{NL}"
                                      for i, (a, b, c) in enumerate(srt, 1)), encoding="utf-8")
    ffmeta = [";FFMETADATA1", f"title={SCRIPT['title']}", ""]
    yt = []
    for k, (a, title) in enumerate(chapters):
        b = chapters[k + 1][0] if k + 1 < len(chapters) else total
        ffmeta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(a * 1000)}", f"END={int(b * 1000)}", f"title={title}", ""]
        yt.append(f"{int(a // 60):02d}:{int(a % 60):02d} {title}")
    (B / f"{name}_chapters.ffmeta").write_text(NL.join(ffmeta), encoding="utf-8")
    (B / f"{name}_chapters.txt").write_text(NL.join(yt) + NL, encoding="utf-8")

    inputs, graph = [], []
    for i, s in enumerate(segs):
        inputs += ["-i", str(CLIPS / f"{s['id']}.mp4")]
        graph.append(f"[{i}:v]fps={FPS},scale=out_range=tv,format=yuv420p,setsar=1,settb=AVTB[s{i}]")
    prev = "s0"
    for i in range(1, len(segs)):
        graph.append(f"[{prev}][s{i}]xfade=transition=fade:duration={xf}:offset={starts[i]:.3f}[x{i}]")
        prev = f"x{i}"
    if len(segs) == 1:
        graph[0] = graph[0].replace("[s0]", "[x0]")
        prev = "x0"
    video = B / f"{name}_video.mp4"
    ff(*inputs, "-filter_complex", ";".join(graph), "-map", f"[{prev}]", *VENC, "-t", f"{total:.3f}", str(video))
    soft = f"{name}_soft.mp4"
    ff("-i", str(video), "-i", str(wav), "-i", str(B / srt_name), "-i", str(B / f"{name}_chapters.ffmeta"),
       "-map", "0:v", "-map", "1:a", "-map", "2:s", "-map_metadata", "3", "-map_chapters", "3",
       "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
       "-c:s", "mov_text", "-metadata:s:s:0", "language=eng", "-movflags", "+faststart",
       "-t", f"{total:.3f}", str(B / soft))
    print(f"wrote {B / soft} ({total / 60:.2f} min)")
    if burn:
        fonts = B / "fonts"
        fonts.mkdir(exist_ok=True)
        for f in ("segoeui.ttf", "segoeuib.ttf", "arial.ttf"):
            src = Path("C:/Windows/Fonts") / f
            if src.exists() and not (fonts / f).exists():
                shutil.copy(src, fonts / f)
        style = (f"FontName={SCRIPT['subtitle_font']},FontSize=10.5,PrimaryColour=&H00FFFFFF,BorderStyle=4,Outline=5,"
                 "OutlineColour=&H30141414,BackColour=&H30141414,Shadow=0,MarginV=14,MarginL=60,MarginR=60")
        # relative paths + cwd: Windows drive colons break the subtitles filter
        ff("-i", soft, "-map", "0:v", "-map", "0:a", "-map_metadata", "0", "-map_chapters", "0",
           "-vf", f"subtitles={srt_name}:fontsdir=fonts:force_style='{style}'",
           "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-color_range", "tv",
           "-c:a", "copy", "-movflags", "+faststart", f"{name}_burned.mp4", cwd=str(B))
        print(f"wrote {B / f'{name}_burned.mp4'}")


def cmd_init(path):
    dst = Path(path)
    if dst.exists() and any(dst.iterdir()):
        sys.exit(f"{dst} is not empty")
    shutil.copytree(SKILL / "examples" / "demo", dst, dirs_exist_ok=True)
    print(f"created {dst.resolve()} - edit script.yaml, then: python {Path(__file__).resolve()} all {dst}")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, proj = sys.argv[1], sys.argv[2]
    rest = [a for a in sys.argv[3:] if not a.startswith("--")]
    if cmd == "init":
        return cmd_init(proj)
    load_project(proj)
    burn = "--no-burn" not in sys.argv
    if cmd == "tts":
        cmd_tts()
    elif cmd == "scenes":
        cmd_scenes(rest)
    elif cmd == "screens":
        cmd_screens(rest)
    elif cmd == "final":
        cmd_final(burn)
    elif cmd == "all":
        cmd_tts(); cmd_scenes([]); cmd_screens([]); cmd_final(burn)
    elif cmd == "still":
        from playwright.sync_api import sync_playwright
        seg = next(s for s in SCRIPT["segments"] if s["id"] == rest[0])
        cues, _, total = scene_timeline(seg)
        with sync_playwright() as p:
            br = browser(p)
            pg = br.new_page(viewport={"width": 1920, "height": 1080})
            t = float(rest[1]) if len(rest) > 1 else total
            out = B / f"still_{seg['id']}_{t:.1f}.png"
            still(pg, scene_file(seg), cues, t, out)
            print(out, "total", round(total, 1), cues)
            br.close()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
