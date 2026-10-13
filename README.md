# narrated-video-builder

A Claude Code skill (and plain Python tool) that builds narrated 1080p tutorial and explainer videos from a YAML script.

You write the narration and pick a scene for each part. It voices the narration offline with Kokoro, renders GSAP-animated HTML scenes whose animations fire as each sentence is spoken, cuts screen recordings with eased zoom, spotlight and masks, then crossfades everything and adds burned and soft subtitles plus chapters. Because every cue comes from the audio, changing the speaking pace re-times the whole video.

## Install

```
git clone https://github.com/Praneethvvs/narrated-video-builder ~/.claude/skills/narrated-video-builder
python ~/.claude/skills/narrated-video-builder/scripts/setup.py
```

Setup needs Python 3.10+ and Node.js. It installs the Python deps, Playwright Chromium and GSAP, and downloads the Kokoro model (about 340 MB).

## Try it

```
python ~/.claude/skills/narrated-video-builder/scripts/build.py init my-video
python ~/.claude/skills/narrated-video-builder/scripts/build.py all my-video
```

That builds a one-minute demo into `my-video/build/`. Edit `my-video/script.yaml` to make your own. The format is in `references/script-format.md`, and `SKILL.md` covers the workflow Claude follows.

Third-party pieces keep their own licences: Kokoro (Apache 2.0), GSAP (GreenSock standard licence), Playwright (Apache 2.0), FFmpeg via imageio-ffmpeg (LGPL/GPL).
