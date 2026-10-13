"""QA helper: grab frames at given times and tile them (3 per row, 640x360 each) into one PNG.

  python scripts/frames.py <video> <out.png> t1 t2 ... (up to 9 times, seconds)
Pick times from the .srt, including mid-animation moments, and check subtitles match what is on screen.
"""
import os
import subprocess
import sys
import tempfile

import imageio_ffmpeg

ff = imageio_ffmpeg.get_ffmpeg_exe()
video, out, times = sys.argv[1], sys.argv[2], [float(t) for t in sys.argv[3:12]]
font = r"C\:/Windows/Fonts/arial.ttf" if os.name == "nt" else None
d = tempfile.mkdtemp()
files = []
for i, t in enumerate(times):
    f = os.path.join(d, f"{i}.png")
    vf = "scale=640:360"
    if font:
        vf += f",drawtext=fontfile='{font}':text='{t:.1f}s':x=10:y=10:fontsize=28:fontcolor=red:box=1"
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", str(t), "-i", video, "-frames:v", "1", "-vf", vf, f], check=True)
    files.append(f)
while len(files) % 3:
    files.append(files[-1])
inputs = sum([["-i", f] for f in files], [])
layout = "|".join(f"{(i % 3) * 640}_{(i // 3) * 360}" for i in range(len(files)))
subprocess.run([ff, "-y", "-loglevel", "error", *inputs, "-filter_complex", f"xstack=inputs={len(files)}:layout={layout}", out], check=True)
print(out)
