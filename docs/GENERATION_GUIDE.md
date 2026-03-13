# Generation Guide

## What Drives The Workflow

The workflow is designed to be operated by a coding agent in the CLI, such as Claude Code.

That matters because the scripts are only one part of the system:

- the agent reads the brief and repo state
- the Python scripts run the generation logic
- the outputs feed into ComfyUI (local GPU rendering) and Final Cut Pro

The project engine is:

- AI coding agent
- CLI workflow (`run.py`)
- Python generation scripts
- ComfyUI for GPU rendering

## Repo Layout

```
content-agents/
├── run.py                     ← single entry point for everything
├── orchestrate_fcpxml.py      ← FCP timeline + prompt generation
├── orchestrate_premxml.py     ← Premiere timeline + SCENE_COUNT constant
├── comfy_client.py            ← ComfyUI API client (queue, poll, download, upload)
├── briefs/
│   ├── music_vid_input.md
│   └── ad_project_input.md
├── config/
│   └── director_settings.json
├── workflows/
│   ├── mv_workflow.json           ← ComfyUI workflow (API format)
│   └── mv_workflow_nodes.json     ← node ID config + render settings
├── input_scenes/              ← placeholder source clips for FCP timeline
└── output/                    ← generated project folders
    └── _tmp_frames/           ← temporary extracted frames (last-frame pipeline)
```

## Scene Count

`SCENE_COUNT` is defined in `orchestrate_premxml.py` and imported by `orchestrate_fcpxml.py`.

- **Current value: 2** — for fast development and testing
- **Production value: 6** — for full 30-second packages

Change it in one place:

```python
# orchestrate_premxml.py
SCENE_COUNT = 2   # 2 for testing, 6 for production
```

The input_scenes folder and all timeline outputs automatically scale with this number.

## The Last-Frame / First-Frame Pipeline

This is the core of the ComfyUI generation flow on this branch.

### Why it exists

Previously the pipeline generated N independent images and animated each one separately. The videos looked unrelated even with matching prompts because each image was generated from scratch.

### How it works

1. **Scene 1** runs the full pipeline: Lumina2 generates an image from the Nano Banana prompt → LTX-Video animates it
2. `comfy_client.py` polls ComfyUI until scene 1 is complete (`/history/{prompt_id}`)
3. The output video is downloaded from `/view?filename=...&subfolder=video`
4. ffmpeg extracts the **2nd-to-last frame** from the video
5. That frame is uploaded to ComfyUI via `/upload/image`
6. **Scene 2** injects a `LoadImage` node dynamically into the workflow JSON and rewires node `267:238` (ResizeImageMaskNode) to pull from that frame instead of Lumina2's output
7. LTX-Video picks up from that exact visual state — same character, same lighting, same room

### What still runs on scene 2+

Lumina2 still runs on scene 2 because it's baked into the workflow and can't be disabled via the API. Its output is ignored since `267:238` is rewired to use the LoadImage node instead. This wastes ~12 seconds of compute per scene.

**Future optimization**: use a separate `mv_workflow_i2v.json` (image-to-video only, no Lumina2) for scene 2+ to cut render time roughly in half.

### Frame injection in the workflow

The injection happens inside `send_to_comfy_headless()` in `comfy_client.py`:

```python
# Adds a LoadImage node dynamically
workflow["_first_frame_loader"] = {
    "inputs": {"image": first_frame_filename, "upload": "image"},
    "class_type": "LoadImage"
}
# Rewires the resize node to use it instead of the SD3/Lumina2 output
workflow["267:238"]["inputs"]["input"] = ["_first_frame_loader", 0]
```

The node ID `267:238` is configured in `workflows/mv_workflow_nodes.json` under `node_first_frame_input`.

## Prompt Structure

Each scene gets two prompts:

**Nano Banana prompt** → injected into `57:27` (CLIPTextEncode) → drives Lumina2 image generation

- Used for scene 1 only in production
- Scene 2+ sends empty string (image is the extracted last frame)
- Kept short: subject + setting + action + lighting + palette + mood

**LTX motion prompt** → injected into `267:266` (PrimitiveStringMultiline) → drives LTX-Video animation

- Used for every scene
- Kept short: duration + camera + subject motion + mood + negatives

## Render Speed Controls

Video frame length is overridden via `workflows/mv_workflow_nodes.json`:

```json
"node_frame_length": "267:225",
"frame_length_override": 49
```

| `frame_length_override` | Duration | Use |
|---|---|---|
| `49` | ~2 seconds | Fast testing |
| `97` | ~4 seconds | Mid-length review |
| `121` | ~5 seconds | Production |
| _(remove key)_ | workflow default | Use whatever ComfyUI has |

## Music Video Workflow — Step By Step

### 1. Fill out the brief

Edit `briefs/music_vid_input.md`. Required: `BPM:`, `## Lyrics`, `## Creative Notes`.

### 2. Add input clips

Put placeholder clips in `input_scenes/` named `scene_01.mp4`, `scene_02.mp4` (matching `SCENE_COUNT`).

### 3. Start ComfyUI

ComfyUI must be running at `http://127.0.0.1:8188` before running with `--comfy`.

### 4. Run the pipeline

```
python run.py --type music_video --brief briefs/music_vid_input.md --project_name my_video --input_dir ./input_scenes --timeline fcp --comfy
```

### 5. Review output

Check `output/my_video/prompts.txt` — verify scene prompts look right before a full production run.

### 6. Import into Final Cut Pro

File > Import XML > `output/my_video/my_video.fcpxml`

## Advertisement Workflow

Same flow as music video. Use `briefs/ad_project_input.md` and `--type ad --ad_style brand_spot`.

Ad styles: `brand_spot`, `lifestyle`, `ugc`

## Common Problems

| Problem | Fix |
|---|---|
| Scene 2 looks nothing like scene 1 | Frame extraction failed — check terminal for `[last-frame] WARNING` and verify ComfyUI output folder has videos |
| `No video found in job output` | Check node output keys printed in terminal, update `get_output_video_filename` search keys in `comfy_client.py` |
| Missing scene clips | Copy `placeholder_master.mp4` to `input_scenes/scene_01.mp4` etc. |
| ComfyUI not reachable | Start ComfyUI first |
| Brief missing BPM | Add `BPM: 120` near top of music video brief |
