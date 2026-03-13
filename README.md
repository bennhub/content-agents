# Content Agents

AI video pre-production pipeline. Give it a project brief and it generates scene prompts, a BPM-timed edit timeline, and renders the videos via ComfyUI using a **last-frame/first-frame** pipeline for seamless visual continuity between clips.

## How It Works

1. Fill out a brief (lyrics + BPM, or ad description)
2. Run `run.py` — it generates scene prompts and an FCP/Premiere timeline
3. With `--comfy`: renders each scene sequentially in ComfyUI. After scene 1 finishes, extracts the last frame and uses it as the starting point for scene 2. Every clip flows from where the previous one ended.

The real engine is:

- AI coding agent (Claude Code) operating in the CLI
- `run.py` orchestrating generation and ComfyUI rendering
- `comfy_client.py` handling the last-frame extraction and injection pipeline
- ComfyUI for local GPU rendering (Lumina2 image gen + LTX-Video)

## Quick Start

```
python run.py --type music_video --brief briefs/music_vid_input.md --project_name my_video --input_dir ./input_scenes --timeline fcp --comfy
```

See `docs/HOW_TO.md` for full setup and usage.

## Repo Structure

```
content-agents/
├── run.py                        ← entry point
├── orchestrate_fcpxml.py         ← FCP timeline + prompt generation
├── orchestrate_premxml.py        ← Premiere timeline + SCENE_COUNT
├── comfy_client.py               ← ComfyUI API: queue, poll, extract, inject
├── briefs/
│   ├── music_vid_input.md
│   └── ad_project_input.md
├── config/
│   └── director_settings.json
├── workflows/
│   ├── mv_workflow.json          ← ComfyUI workflow (API format)
│   └── mv_workflow_nodes.json    ← node IDs + render settings
├── input_scenes/                 ← source clips for FCP timeline
└── output/                       ← generated projects + tmp frames
```

## Current Settings

- `SCENE_COUNT = 2` in `orchestrate_premxml.py` (set to 6 for production)
- `frame_length_override: 49` in `mv_workflow_nodes.json` (~2s for fast testing, use 121 for ~5s production)

## Requirements

- Python 3.10+
- `pip install requests`
- ffmpeg + ffprobe (for last-frame extraction)
- ComfyUI running at `http://127.0.0.1:8188` (for `--comfy`)

## Docs

- `docs/HOW_TO.md` — full setup, commands, and argument reference
- `docs/GENERATION_GUIDE.md` — how the pipeline and last-frame logic works
