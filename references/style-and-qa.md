# Style, narration and QA

## Narration
- Conversational, one idea per sentence, second person ("you'll see").
- Define before use; keep one running example through the whole video and reuse its numbers.
- At the start of each step, say where we are; end each segment with a bridge to the next; the recap mirrors the outline.
- Hold key numbers (`hold: true`) and pause before calculation steps (`pause: true`) so viewers can follow.
- Every factual claim maps to the user's source of truth (a facts file, the code, the docs). If unsure, phrase it as a general concept or cut it.
- Don't condescend ("beginner", "newcomer") and don't editorialise about the product's flaws unless asked.

## Visual style
- Light, conventional: one accent colour plus greys, green/red only for kept/lost or good/bad. No emoji, bouncing or spinning.
- Nothing important in the bottom ~150 px of a scene: subtitles sit there.
- Formulas must read correctly on their own: brackets and units on every term.

## QA routine
1. `ffmpeg -i build/<name>_burned.mp4` shows 1920x1080, 30 fps, `yuv420p(tv)`, AAC 48 kHz stereo; the soft file also has a `mov_text` subtitle stream.
2. Frame tile: `python <skill>/scripts/frames.py build/<name>_burned.mp4 out.png t1 ... t9`. Pick times from the `.srt`, include mid-animation moments, and check that each subtitle matches what is appearing, nothing sits under the subtitles, and no real names or secrets appear.
3. After narration changes, re-check claims; after structural changes, re-check continuity against the outline.

## Known quirks
- **Windows ffmpeg filters:** the `subtitles` filter breaks on drive colons, so the builder burns with `cwd=build` and relative paths. `drawtext` needs `fontfile='C\:/Windows/Fonts/arial.ttf'`.
- **Colour range:** browser screenshots are full range; the pipeline forces `out_range=tv`, `-color_range tv` and yuv420p. Keep that or players show different contrast between scenes and screens.
- **zoompan** jitters unless the input is upscaled 2x first (done in `screen_fx.py`).
- **Kokoro** trims leading/trailing silence per clip so `gap`/`hold` values are exact.
- **TLS-intercepting proxies:** `pip install truststore` before `setup.py` so downloads trust the OS store.
- **Stale clips:** `final` asserts each clip's recorded text matches the script; re-run `scenes`/`screens` for changed segments.
