# How To Run Content Agents — Start To Finish

## What This Does

Content Agents is an **AI video pre-production pipeline**. You give it a project brief (song lyrics + BPM, or an ad description) and it:

1. Splits the content into scenes
2. Writes a **text prompt per scene** (image prompt + video motion prompt)
3. Builds an **edit timeline** (Premiere Pro XMEML or Final Cut Pro FCPXML) with placeholder clips timed to your BPM
4. Optionally **pushes all scenes to ComfyUI** to render the actual video clips automatically using a **last-frame/first-frame** pipeline for seamless visual continuity

The single entry point for everything is `run.py`.

---

## How The ComfyUI Pipeline Works (Last-Frame / First-Frame)

When you run with `--comfy`, scenes are **not all queued at once**. The pipeline runs sequentially:

1. **Scene 1** — generates a starting image from the Nano Banana prompt via Lumina2, then animates it with LTX-Video
2. After scene 1 finishes, the pipeline **downloads the output video**, extracts the **2nd-to-last frame** using ffmpeg, and uploads it to ComfyUI as a PNG
3. **Scene 2** — uses that extracted frame as its visual starting point instead of generating a new image. The LTX model picks up exactly where scene 1 left off — same character, same lighting, same environment
4. This repeats for each subsequent scene

This means you only need **one starting image** for the whole sequence. Every scene after the first flows naturally from the end of the previous one.

Temporary frame files are saved to `output/_tmp_frames/` and cleaned up between runs.

---

## Prerequisites

### Python 3.10+

```
python --version
```

### Install dependencies

```
pip install requests
```

### ffmpeg + ffprobe

Required for frame extraction. Verify with:

```
ffprobe -version
ffmpeg -version
```

### input_scenes/ folder

The FCP workflow needs placeholder source clips. Put any `.mp4` files in `input_scenes/` named `scene_01.mp4` and `scene_02.mp4` (matching your scene count). For quick testing, copy `placeholder_master.mp4`:

```
copy placeholder_master.mp4 input_scenes\scene_01.mp4
copy placeholder_master.mp4 input_scenes\scene_02.mp4
```

### ComfyUI (only needed for --comfy)

- ComfyUI must be running at `http://127.0.0.1:8188`
- Your workflow JSON must be in `workflows/mv_workflow.json`
- The companion node config `workflows/mv_workflow_nodes.json` tells the pipeline which node IDs to inject prompts into

Export from ComfyUI: **Settings > Dev Mode > Save (API Format)**

---

## Project Briefs

All project details live in a brief file inside `briefs/`.

### Music Video Brief — `briefs/music_vid_input.md`

```markdown
BPM: 83

## Lyrics

Your full lyrics here...

## Creative Notes

Describe the visual tone, camera style, color palette, mood, etc.
```

### Ad Brief — `briefs/ad_project_input.md`

```markdown
## Product Name
## Audience
## Core Problem
## Value Proposition
## Offer Or CTA
## Creative Notes
## Visual References (optional)
```

---

## Running The Pipeline

### Standard run (prompts + timeline + ComfyUI render)

```
python run.py --type music_video --brief briefs/music_vid_input.md --project_name my_video --input_dir ./input_scenes --timeline fcp --comfy
```

### Prompts and timeline only (no ComfyUI)

```
python run.py --type music_video --brief briefs/music_vid_input.md --project_name my_video --input_dir ./input_scenes --timeline fcp
```

### Ad workflow

```
python run.py --type ad --brief briefs/ad_project_input.md --project_name my_ad --ad_style brand_spot --input_dir ./input_scenes --timeline fcp --comfy
```

Ad style options: `brand_spot`, `lifestyle`, `ugc`

---

## What Gets Created

```
output/my_video/
├── my_video.fcpxml         ← Final Cut Pro timeline
├── prompts.txt             ← All scene prompts (image + video per scene)
└── director_settings.json  ← Visual style per scene

output/_tmp_frames/         ← Extracted last frames (used during ComfyUI run)
├── scene_01.mp4            ← Downloaded video from scene 1
└── scene_01_last_frame.png ← Frame injected into scene 2
```

---

## Full Argument Reference

| Argument | Required | Description | Default |
|---|---|---|---|
| `--type` | Yes | `music_video` or `ad` | — |
| `--brief` | Yes | Path to your brief markdown file | — |
| `--project_name` | Yes | Output folder name and sequence label | — |
| `--timeline` | No | `prem`, `fcp`, or `both` | `prem` |
| `--input_dir` | FCP only | Folder containing source scene clips | `.` |
| `--ad_style` | Ad only | `brand_spot`, `lifestyle`, or `ugc` | `brand_spot` |
| `--beats_per_bar` | No | Time signature numerator | `4` |
| `--bars_per_scene` | No | Bars per scene for BPM timing | `2` |
| `--comfy` | No | Push scenes to ComfyUI after generation | off |
| `--comfy_url` | No | ComfyUI server URL | `http://127.0.0.1:8188` |
| `--workflow` | No | Override ComfyUI workflow JSON path | auto-selects from `workflows/` |

---

## Terminal Output When Running With --comfy

```
[health] ComfyUI is up.

[comfy] Pushing 2 scenes -> http://127.0.0.1:8188
[comfy] Last-frame/first-frame: first_frame_input_node=267:238

  [1/2] scene_01  [Premium Night Pulse]
  Frame length set to 49 frames (~2.0s)
  scene_01  queued -> 4289470e-...
  Waiting for scene_01 to finish before extracting last frame...
  Job complete.
  Found video in node 273['images']: LTX_2.3_i2v_00019_.mp4
  Downloaded -> output/_tmp_frames/scene_01.mp4
  Extracted 2nd-to-last frame (frame 47) -> scene_01_last_frame.png
  Uploaded scene_01_last_frame.png -> ComfyUI input/scene_01_last_frame.png
  [last-frame] Ready for next scene: scene_01_last_frame.png

  [2/2] scene_02  [Premium Night Pulse]
  [last-frame] Using extracted frame: scene_01_last_frame.png
  First-frame injected: scene_01_last_frame.png -> node 267:238
  scene_02  queued -> d04f2906-...

[comfy] All scenes queued.
```

Rendered clips are saved to ComfyUI's output folder: `ComfyUI/output/video/`

---

## Scene Count and Testing

The current scene count is set to **2** for fast iteration. Change it in `orchestrate_premxml.py`:

```python
SCENE_COUNT = 2   # change to 6 for full production run
```

Video length per scene is controlled in `workflows/mv_workflow_nodes.json`:

```json
"node_frame_length": "267:225",
"frame_length_override": 49
```

49 frames = ~2 seconds. Set to `121` for ~5 seconds (production length). Remove `frame_length_override` entirely to use whatever is set in the ComfyUI workflow.

---

## Scene Timing Math

Scene length is calculated from BPM:

```
seconds per beat  = 60 / BPM
seconds per scene = beats_per_bar × bars_per_scene × seconds_per_beat
```

Songs below 100 BPM automatically use double-time pacing to keep scenes under 5 seconds.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `ComfyUI not reachable` | Start ComfyUI before running with `--comfy` |
| `Workflow file not found` | Export workflow from ComfyUI in API format → save to `workflows/mv_workflow.json` |
| `Node 'X' not found in workflow` | Update node IDs in `workflows/mv_workflow_nodes.json` |
| `missing required input clip` | Add placeholder clips to `input_scenes/` (see Prerequisites) |
| `No video found in job output` | Frame extraction failed — next scene uses fallback image prompt. Check ComfyUI output folder structure matches `node_frame_length` config |
| Brief missing `BPM:` line | Add `BPM: 120` near the top of your music video brief |

---

## Workflow Node Config (`mv_workflow_nodes.json`)

```json
{
  "node_clip_image": "57:27",         // CLIP text node for image prompt (Lumina2)
  "node_ltx_motion": "267:266",       // Motion prompt node (LTX-Video)
  "node_ksampler": "57:3",            // KSampler seed randomization
  "extra_noise_seeds": ["267:216", "267:237"],  // LTX RandomNoise nodes
  "node_first_frame_input": "267:238", // Node whose image input gets rewired for last-frame injection
  "node_frame_length": "267:225",     // Frame count override node
  "frame_length_override": 49         // 49 = ~2s test, 121 = ~5s production
}
```

If you swap in a different ComfyUI workflow, update these IDs. To find them:

```python
import json
with open("workflows/mv_workflow.json") as f:
    wf = json.load(f)
for node_id, node in wf.items():
    inp = node.get("inputs", {})
    if "text" in inp or "value" in inp or "seed" in inp:
        print(node_id, node.get("class_type"), list(inp.keys()))
```
