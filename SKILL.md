---
name: narrated-video-builder
description: Build a narrated 1080p tutorial or explainer video from a YAML script - offline TTS voice-over (Kokoro), GSAP-animated HTML scenes whose animations fire on each spoken sentence, screen recordings with eased zoom, spotlight and masks, crossfades, burned and soft subtitles, and chapters. Use whenever someone wants a training video, product walkthrough, explainer, narrated demo, or "turn these screen recordings into a narrated video", and when revising such a video (faster/slower narration, re-timing, fixing a slide, re-cutting a screen clip).
---

# Narrated video builder

Turns a `script.yaml` (narration + segments) into `<name>_burned.mp4`, `<name>_soft.mp4`, `<name>.srt` and `<name>_chapters.txt`.
Everything is driven by the audio: each spoken line's start time is a **cue**, and scene animations and screen effects are placed on cues, so re-timing the voice re-times the picture.

## Setup (once per machine)
```
python <skill>/scripts/setup.py        # pip deps, Playwright Chromium, GSAP via npm, Kokoro model (~340 MB)
```
Needs Python 3.10+, Node.js (npm) and internet for the first run. ffmpeg comes from `imageio-ffmpeg` (there is no ffprobe: read `ffmpeg -i <file>` stderr).
Set `NVB_BROWSER_CHANNEL=msedge` (or `chrome`) to render with an installed browser instead of the bundled Chromium.

## Workflow
1. **Scaffold:** `python <skill>/scripts/build.py init <project>` copies a working one-minute demo. Build it once to confirm the machine works.
2. **Outline first.** Agree the chapters and the running example with the user before writing narration. One idea per sentence; define a term before using it; end each segment with a bridge to the next.
3. **Write `script.yaml`** - see `references/script-format.md`. Prefer the built-in templates (`title`, `card`, `bullets`, `calc`, `cards`); hand-write HTML in `scenes/` only for bespoke diagrams.
4. **Screen recordings** (optional) go in `rec/<name>.mp4|webm` with a `<name>.json` of beat marks - see `references/recordings.md`.
5. **Build:**
   ```
   python <skill>/scripts/build.py tts     <project>
   python <skill>/scripts/build.py scenes  <project> [segment_id ...]
   python <skill>/scripts/build.py screens <project> [segment_id ...]
   python <skill>/scripts/build.py final   <project> [--no-burn]
   python <skill>/scripts/build.py all     <project>
   python <skill>/scripts/build.py still   <project> <scene_id> <t>    # one debug PNG
   ```
   Long builds (a 40-minute video takes a while): run in the background and wait on a log file.
6. **QA** - see `references/style-and-qa.md`. At minimum: `ffmpeg -i` (1920x1080, 30 fps, yuv420p(tv), AAC 48 kHz stereo) and a frame tile with `scripts/frames.py` at times picked from the `.srt`, including mid-animation moments.

## Pace (defaults, all overridable in script.yaml)
| key | default | meaning |
|---|---|---|
| `speed` | 1.12 | Kokoro speed for every line (per-segment `speed:` overrides) |
| `gap` | 0.25 s | silence after each line or beat |
| `number_hold` | 0.8 s | extra hold after lines with `hold: true` (a key number lands) |
| `step_pause` | 0.35 s | extra pause before lines with `pause: true` (a calculation step) |
| `lead` / `tail` / `xfade` | 0.6 / 0.9 / 0.35 s | segment start silence, end hold, crossfade |

These came from real feedback: speed 1.0, 1.6 s holds and 0.8 s step pauses felt too slow for a 40-minute tutorial.

## Revisions
- **Keep the previous version.** Change `name:` (e.g. `v2`) so outputs don't overwrite, or copy the project folder.
- **"Make it faster/slower"** = change `speed`, `gap`, `number_hold`, `step_pause` only, then `all`. Words, numbers, slides and order stay frozen. Scenes and screen clips re-time automatically because cues come from the audio offsets.
- TTS is cached by hash of voice|speed|text, so a changed line re-voices only that line; a speed change re-voices everything.
- Screen clips only trim idle time; they never cut on-screen action (a beat keeps max(narration, action), and freezes the last frame if narration is longer). So a faster voice shortens screen segments less than scenes.
- After any wording change, re-check every claim against the user's source of truth.

## Files
- `scripts/build.py` builder, `scripts/setup.py`, `scripts/frames.py` (QA tile)
- `engine/kit.js` (GSAP cue kit, `data-anim` vocabulary), `engine/scene.css` (palette), `engine/templates.py` (built-in scenes), `engine/render_scene.py`, `engine/screen_fx.py`
- `examples/demo/` the scaffold project
- `references/script-format.md`, `references/recordings.md`, `references/style-and-qa.md`
