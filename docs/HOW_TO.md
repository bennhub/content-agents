# How To Run Content Agents — Start To Finish

## What This Does

Content Agents is an **AI video pre-production pipeline**. You give it a project brief (song lyrics + BPM, or an ad description) and it:

1. Splits the content into **6 scenes**
2. Writes a **text prompt per scene** (image prompt + video motion prompt)
3. Builds an **edit timeline** (Premiere Pro XMEML or Final Cut Pro FCPXML) with placeholder clips timed to your BPM
4. Optionally **pushes all 6 prompts to ComfyUI** to render the actual video clips automatically

The single entry point for everything is `run.py`.

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

### placeholder_master.mp4

The Premiere workflow copies a placeholder clip into your project folder so Premiere resolves media on import. Add any short `.mp4` to the repo root and name it `placeholder_master.mp4`.

```
content-agents/
└── placeholder_master.mp4   ← any .mp4 file, any content
```

### ComfyUI (only needed for --comfy)

- ComfyUI must be running at `http://127.0.0.1:8188`
- Your workflow JSON files must be in the `workflows/` folder:
  - `workflows/mv_workflow.json` — for music videos (LTX 2.3 video generation)
  - `workflows/ad_workflow.json` — for ads (image generation)
- Each workflow has a companion node config: `workflows/mv_workflow_nodes.json` and `workflows/ad_workflow_nodes.json` — these tell `run.py` which ComfyUI node IDs to inject prompts into

To set up the workflow JSONs: open ComfyUI, load your workflow, go to **Settings > Dev Mode > Save (API Format)**, and save the file to `workflows/`.

---

## Project Briefs

All project details live in a brief file inside `briefs/`. Two templates are included:

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
Your product here

## Audience
Who this is for

## Core Problem
What problem it solves

## Value Proposition
Why it is the solution

## Offer Or CTA
Call to action

## Creative Notes
Visual tone, style notes

## Visual References
Reference scenes or aesthetics
```

Edit the brief files before running. The script reads directly from them.

---

## Running The Pipeline

### Music Video — Premiere Pro + ComfyUI (full run)

```
python run.py --type music_video --brief briefs/music_vid_input.md --project_name my_video --comfy
```

This is the main command. It:
- Reads your brief
- Generates 6 scene prompts
- Writes a Premiere Pro XMEML timeline to `my_video/my_video.xml`
- Copies placeholder clips to `my_video/scene_01.mp4` through `scene_06.mp4`
- Pushes all 6 scene prompts to ComfyUI and queues the renders

### Music Video — Premiere only, no ComfyUI

```
python run.py --type music_video --brief briefs/music_vid_input.md --project_name my_video
```

Generates the timeline and prompts. No GPU rendering. Use `prompts.txt` manually with any video generator.

### Ad — Premiere Pro + ComfyUI

```
python run.py --type ad --brief briefs/ad_project_input.md --project_name my_ad --ad_style brand_spot --comfy
```

Ad style options: `brand_spot`, `lifestyle`, `ugc`

### Final Cut Pro instead of Premiere

```
python run.py --type music_video --brief briefs/music_vid_input.md --project_name my_video --input_dir . --timeline fcp --comfy
```

> Note: FCP requires `--input_dir` pointing to a folder with `scene_01.mp4` through `scene_06.mp4`.

### Both timelines

```
python run.py --type music_video --brief briefs/music_vid_input.md --project_name my_video --input_dir . --timeline both --comfy
```

---

## Full Argument Reference

| Argument | Required | Description | Default |
|---|---|---|---|
| `--type` | Yes | `music_video` or `ad` | — |
| `--brief` | Yes | Path to your brief markdown file | — |
| `--project_name` | Yes | Output folder name and sequence label | — |
| `--timeline` | No | `prem`, `fcp`, or `both` | `prem` |
| `--input_dir` | FCP only | Folder containing `scene_01.mp4` through `scene_06.mp4` | `.` |
| `--ad_style` | Ad only | `brand_spot`, `lifestyle`, or `ugc` | `brand_spot` |
| `--beats_per_bar` | No | Time signature numerator | `4` |
| `--bars_per_scene` | No | Bars per scene for BPM timing | `2` |
| `--comfy` | No | Push scenes to ComfyUI after generation | off |
| `--workflow` | No | Override ComfyUI workflow JSON path | auto-selects from `workflows/` |
| `--comfy_url` | No | ComfyUI server URL | `http://127.0.0.1:8188` |

---

## What Gets Created

After running, your project folder looks like:

```
my_video/
├── my_video.xml          ← Premiere Pro XMEML timeline (import this)
├── prompts.txt           ← All 6 scene prompts (image + video per scene)
├── director_settings.json  ← Visual style per scene
├── scene_01.mp4          ← Placeholder clip
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
└── scene_06.mp4
```

The terminal output shows each step and, if `--comfy` is active, a `prompt_id` per scene:

```
[health] Checking ComfyUI at http://127.0.0.1:8188 ...
[health] ComfyUI is up.

[workflow] ...\workflows\mv_workflow.json
[nodes]    {'node_clip_image': '57:27', 'node_ltx_motion': '267:266', ...}

[prem]  Prompts : ...\my_video\prompts.txt
[prem]  XMEML   : ...\my_video\my_video.xml

[comfy] Pushing 6 scenes -> http://127.0.0.1:8188
  scene_01  [anticipation]
  scene_01  queued -> bc015226-f7f9-4177-894a-c61ef00de963
  scene_02  [ignition]
  scene_02  queued -> 16b350ae-779e-4a33-83c0-de8fb917f87e
  ...

[comfy] All scenes queued.
```

Monitor render progress in the **ComfyUI browser UI** at `http://127.0.0.1:8188`.

Rendered clips are saved to ComfyUI's own output folder — typically:
```
ComfyUI/output/video/LTX_2.3_i2v/
```

---

## After ComfyUI Finishes

1. Locate the 6 rendered `.mp4` files in ComfyUI's output folder
2. Rename them `scene_01.mp4` through `scene_06.mp4`
3. Drop them into your project folder (`my_video/`), replacing the placeholders
4. Open Premiere Pro → **File > Import** → select `my_video/my_video.xml`
5. The sequence loads with all 6 clips placed back-to-back, timed to your BPM

---

## Scene Timing Math

Scene length is calculated from BPM:

```
seconds per beat  = 60 / BPM
seconds per scene = beats_per_bar × bars_per_scene × seconds_per_beat
```

**Example at 83 BPM (default brief):**

The script detects this is below 100 BPM and uses double-time pacing automatically, capping scene length at 5 seconds max.

**Example at 120 BPM:**
- `60 / 120 = 0.5s` per beat
- `4 beats × 2 bars = 8 beats`
- `0.5 × 8 = 4.0s` per scene
- 6 scenes = **24 seconds total**

---

## Troubleshooting

| Error | Fix |
|---|---|
| `placeholder_master.mp4 not found` | Add any `.mp4` to the repo root and name it `placeholder_master.mp4` |
| `ComfyUI not reachable` | Start ComfyUI before running with `--comfy` |
| `Workflow file not found: workflows/mv_workflow.json` | Export your workflow from ComfyUI in API format and save it to `workflows/mv_workflow.json` |
| `Node 'X' not found in workflow` | Open `workflows/mv_workflow_nodes.json` and update the node IDs to match your workflow |
| Premiere cannot find media | All 6 `scene_XX.mp4` files must be in the same folder as the `.xml` file |
| Brief missing `BPM:` line | Add `BPM: 120` (or your tempo) near the top of your music video brief |
| Brief missing `## Lyrics` section | Add a `## Lyrics` heading in your brief file |

---

## Finding Node IDs For A New ComfyUI Workflow

If you swap in a different ComfyUI workflow, update `workflows/mv_workflow_nodes.json` with the correct node IDs. To find them:

```python
import json
with open("workflows/mv_workflow.json") as f:
    wf = json.load(f)
for node_id, node in wf.items():
    inp = node.get("inputs", {})
    if "text" in inp or "value" in inp or "seed" in inp or "noise_seed" in inp:
        print(node_id, node.get("class_type"), list(inp.keys()))
```

Look for:
- **`node_clip_image`** — a `CLIPTextEncode` node whose `text` input is your image/scene description
- **`node_ltx_motion`** — a `CLIPTextEncode` or `PrimitiveStringMultiline` node for the video motion prompt
- **`node_ksampler`** — the `KSampler` node whose `seed` you want randomized
- **`extra_noise_seeds`** — any `RandomNoise` nodes with a `noise_seed` input (LTX pipelines often have 2)
