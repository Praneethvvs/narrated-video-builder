# script.yaml format

```yaml
name: v1                     # output prefix: build/v1_soft.mp4, v1_burned.mp4, v1.srt, v1_chapters.txt
title: My walkthrough        # MP4 metadata title
voice: am_michael            # any Kokoro voice (af_heart, bf_emma, am_michael, ...)
lang: en-us
speed: 1.12
gap: 0.25
number_hold: 0.8
step_pause: 0.35
lead: 0.6
tail: 0.9
xfade: 0.35
footer_left: My product · Walkthrough   # scene footer (per-segment override: footer_left/footer_right)
footer_right: Demo data only
palette: {accent: "#2a78d6"}  # optional CSS variable overrides (accent, accent-soft, loss, kept, ink, ink2, muted, surface, rule, panel)
subtitle_font: Segoe UI
browser_channel: msedge       # optional; or env NVB_BROWSER_CHANNEL
segments: [...]
```

## Spoken units (scene `lines`, screen `beats`)
| key | meaning |
|---|---|
| `say` | text the voice reads. Write numbers as words when the voice mangles digits ("eight hundred seventy-five thousand"). |
| `sub` | optional subtitle text shown instead of `say` (use digits: "$875,000"). Same words otherwise. |
| `cue` | name other elements use to appear when this line starts (scene lines). |
| `hold` | `true` = `number_hold` seconds of silence after the line, or a number of seconds. |
| `pause` | `true` = `step_pause` seconds before the line, or a number. |

## Scene segment
```yaml
- id: calc_1                  # unique; clip file name
  kind: scene
  chapter: 2.1 The calculation  # optional; starts a chapter here
  speed: 1.12                   # optional override
  tail: 1.0                     # optional override
  template: calc                # built-in (title | card | bullets | calc | cards) ...
  data: {...}                   # ... with its data, see engine/templates.py docstrings and examples/demo
  # or: html: my_scene.html     # hand-written file in <project>/scenes/
  vars: {NAME: value}           # optional {{NAME}} substitutions in the HTML
  lines: [...]
- id: card2
  kind: scene
  template: card
  duration: 2.2                 # scenes with no lines need a duration
  data: {label: Step 2, name: The app}
```

Built-in template data (all text fields accept inline HTML):
- `title`: `title, subtitle, items: [..], items_cue`
- `card`: `label, name`
- `bullets`: `step, title, sub, points: [{cue, text}], recap: {cue, text}`
- `calc`: `step, title, question, formula: [{cue, text}], rows: [{cue, label, value}], meaning: {cue, text}, recap`
- `cards`: `step, title, sub, cols, cards: [{cue, tag, color: blue|green|amber|grey, title, text}], table: {cue, title, head, rows: [{cue, cells, total}]}, recap`

`value` is a string or a counter: `{count: [from, to], fmt: int|usd|usdk|pct|pct1|dec1|dec2|dec3, prefix, suffix, dur}`.

Write formulas so they read correctly without narration: brackets and units on every term, e.g. `1 − ($875k ÷ $1,080k) ≈ 19%`, not `1 − 875 ÷ 1,080`.

## Hand-written scene HTML
Start with `{{HEAD}}` (stylesheet, GSAP, kit) and end the body with `{{FOOT}}`. Then mark elements up:
- `data-at="cue"`, `"cue+0.4"`, or seconds (`"0.3"`).
- `data-anim`: `fade, up, left, right, pop, grow-x, grow-y, draw` (SVG strokes), `count` (`data-from/-to/-fmt/-prefix/-suffix`), `pulse`, `stagger` (children; `data-gap`), `keys` (`data-prop`, `data-keys="cue:0, cue+1:50"`), `hl` (with class `hlbox`).
- `data-dur` overrides duration; `data-out="cue"` fades the element out.
- `<h1 data-at="0">` reveals word by word.
- For anything custom define `window.build = (tl, at, K) => { tl.to(el, {...}, at('cue+0.2')); }`.
The renderer refuses to build a scene that references an unknown cue.

## Screen segment
```yaml
- id: t_dashboard
  kind: screen
  rec: dashboard              # rec/dashboard.mp4 (or .webm/.mov/.mkv) + rec/dashboard.json
  chapter: 3.1 The dashboard
  lower_third: The dashboard  # caption card for the first ~4 s
  cuts: [[41.0, 47.5]]        # source seconds to drop (dead waits, spinners)
  masks: [{x: 0, y: 0, w: 400, h: 80, from: 0, until: 999}]   # solid boxes hiding sensitive areas (clip seconds)
  beats:
    - id: open                # must match a mark in the json
      say: This is the dashboard.
      zooms: [{cx: 640, cy: 380, z: 1.4, at: 0.2, until: 3.5}]
      spots: [{x: 46, y: 392, w: 1170, h: 208, at: 0.3}]     # dim everything else
      boxes: [{x: 548, y: 392, w: 148, h: 210, at: 0.5}]     # outline
```
Effect coordinates are source pixels (1920x1080); `at`/`until` are seconds from the beat start (`until` defaults to the end of the beat's narration).
