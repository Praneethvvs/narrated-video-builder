"""Render an animated HTML scene to a silent 1920x1080 30 fps MP4, frame by frame.

The scene's state is a pure function of time (engine/kit.js), so we seek to each frame time and
screenshot. Frames where nothing is animating reuse the previous screenshot, which keeps renders fast.
"""
import math
import subprocess
from pathlib import Path

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
FPS = 30


def render(page, html: Path, cues: dict, duration: float, out: Path, extra_vars: dict | None = None):
    page.goto(html.resolve().as_uri())
    page.evaluate("(c) => { window.CUES = c; }", cues)
    if extra_vars:
        page.evaluate("(v) => Object.assign(window, v)", extra_vars)
    page.evaluate("document.fonts.ready.then(() => true)")
    intervals = page.evaluate("window.intervals()")
    missing = page.evaluate(
        "() => [...document.querySelectorAll('[data-at]')].map(e => e.dataset.at.split(/[+-]/)[0].trim())"
        ".filter(c => c && isNaN(+c) && !(c in window.CUES))")
    if missing:
        raise ValueError(f"{html.name}: unknown cues {sorted(set(missing))}")
    n = math.ceil(duration * FPS)
    proc = subprocess.Popen(
        [FF, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
         "-vf", "scale=in_range=full:out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
         "-pix_fmt", "yuv420p", "-color_range", "tv", "-r", str(FPS),
         "-frames:v", str(n), str(out)],
        stdin=subprocess.PIPE)
    last, shots = None, 0
    half = 0.5 / FPS
    for i in range(n):
        t = i / FPS
        active = last is None or any(a - half <= t <= b + 2 * half for a, b in intervals)
        if active:
            page.evaluate("(t) => window.seek(t)", t)
            last = page.screenshot(type="jpeg", quality=94)
            shots += 1
        proc.stdin.write(last)
    proc.stdin.close()
    proc.wait()
    if proc.returncode:
        raise RuntimeError(f"ffmpeg failed for {html.name}")
    return shots, n


def still(page, html: Path, cues: dict, t: float, out_png: Path):
    """Debug helper: one frame at time t."""
    page.goto(html.resolve().as_uri())
    page.evaluate("(c) => { window.CUES = c; }", cues)
    page.evaluate("document.fonts.ready.then(() => true)")
    page.evaluate("(t) => window.seek(t)", t)
    page.screenshot(path=str(out_png))
