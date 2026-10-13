# Screen recordings

A screen segment needs two files in `<project>/rec/`:
- `<rec>.mp4` (or `.webm`, `.mov`, `.mkv`), 1920x1080.
- `<rec>.json` with one mark per beat, in recording seconds, plus a final `end` mark:
  ```json
  {"marks": [{"beat": "open", "t": 1.2}, {"beat": "click_row", "t": 6.8}, {"beat": "end", "t": 14.0}]}
  ```
A beat runs from its mark to the next mark. The builder keeps the part where the screen is still changing (pixel activity) or the narration length, whichever is longer, trims the idle rest, and freezes the last frame if the narration is longer than the whole beat. On-screen actions are never cut.

## Recording with Playwright (repeatable, marks for free)
Scripted recordings beat manual ones: re-recordable after UI changes and the marks are exact.
```python
import json, time
from playwright.sync_api import sync_playwright

marks, t0 = [], None
def mark(beat):
    marks.append({"beat": beat, "t": round(time.monotonic() - t0, 2)})

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context("pw-profile", headless=False,
        viewport={"width": 1920, "height": 1080}, record_video_dir="rec_raw", record_video_size={"width": 1920, "height": 1080})
    page = ctx.pages[0]
    t0 = time.monotonic()
    page.goto("https://app.example.com/dashboard"); page.wait_for_load_state("networkidle")
    mark("open"); page.wait_for_timeout(1500)
    mark("click_row"); page.get_by_role("row").nth(1).click(); page.wait_for_timeout(2500)
    mark("end")
    video = page.video.path()
    ctx.close()
json.dump({"marks": marks}, open("rec/dashboard.json", "w"))
# move/rename `video` to rec/dashboard.webm
```
Notes:
- Playwright starts the video slightly before `t0`; check the first mark against the video once and add a constant offset if needed.
- Use a persistent profile so sign-in survives between runs. Never type passwords from a script; sign in once by hand.
- Seeking in Playwright webm is slow; the builder decodes from the start, so keep recordings per section rather than one huge file.
- Some actions are irreversible in real apps (closing a case, sending an email). Use disposable demo data and record those beats last.

## Privacy
- Record on demo or fictional data. Never show real customer names; open filtered URLs directly instead of navigating through unfiltered lists.
- Use `masks:` for anything that still slips into frame (user name in the header, tenant name, tabs you must not show).
