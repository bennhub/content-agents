# Content Agents

`Content Agents` turns lyrics and tempo into a six-scene prompt package plus an edit timeline.

This repo now has two separate workflows:

- [`orchestrate_splurge.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge.py): Premiere/XMEML test workflow using one placeholder clip copied six times
- [`orchestrate_splurge_fcpxml.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge_fcpxml.py): Final Cut Pro workflow using six real clips and a style-driven prompt system

## What The Project Produces

Depending on the script you run, the project generates:

- `prompts.txt` with one descriptive prompt per scene
- a six-clip edit timeline
- copied scene media inside the output project folder

Timeline formats:

- Premiere workflow: `.xml`
- Final Cut Pro workflow: `.fcpxml`

## How Prompt Generation Works

Both workflows:

- read lyrics from inline text or a text file
- split the lyrics into 6 scenes
- calculate timing from BPM and bars

The Final Cut Pro workflow adds a creative layer:

- it loads [`director_style_v1.md`](/Users/ben/Git%20Projects/Content-Agents/director_style_v1.md)
- it uses that file as a reusable director brief for every scene prompt
- it changes the scene vibe based on lyric content
- it varies camera language, lighting, color, and texture scene by scene

The current style brief is called `High-Motion LTX 2.3` and emphasizes:

- cinematic lighting
- 4k-grade texture detail
- tracking shots
- low-angle framing
- aggressive motion and editorially useful composition

## Shared Timing Model

Both scripts use the same timing math:

- seconds per beat = `60 / BPM`
- beats per scene = `beats_per_bar * bars_per_scene`
- seconds per scene = `beats_per_scene * (60 / BPM)`
- frames per scene = `seconds_per_scene * 23.976`

Defaults:

- `beats_per_bar = 4`
- `bars_per_scene = 2`
- `scene_count = 6`

Example at `120 BPM`, `4/4`, `2 bars per scene`:

- 1 beat = `0.5s`
- 1 bar = `2.0s`
- 2 bars = `4.0s`
- each scene clip lands at `4.0s`
- total timeline length is `24.0s`

## Requirements

You need:

- Python 3
- `ffprobe` for the FCPXML workflow

Check them with:

```bash
python3 --version
ffprobe -version
```

No external Python packages are required.

Premiere test workflow only:

- [`placeholder_master.mp4`](/Users/ben/Git%20Projects/Content-Agents/placeholder_master.mp4) must exist in the repo root

## Project Files

Main files:

- [`orchestrate_splurge.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge.py)
- [`orchestrate_splurge_fcpxml.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge_fcpxml.py)
- [`director_style_v1.md`](/Users/ben/Git%20Projects/Content-Agents/director_style_v1.md)
- [`premiere_xml_logic.md`](/Users/ben/Git%20Projects/Content-Agents/premiere_xml_logic.md)

Current repo layout:

```text
Content-Agents/
├── orchestrate_splurge.py
├── orchestrate_splurge_fcpxml.py
├── director_style_v1.md
├── placeholder_master.mp4
├── premiere_xml_logic.md
└── README.md
```

## How To Run

Run commands from the repo root.

### 1. Premiere Test Workflow

Use this when you want a quick timing/import test in Premiere with placeholder media.

Command:

```bash
python3 orchestrate_splurge.py \
  --lyrics lyrics.txt \
  --bpm 120 \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name premiere_test
```

This creates:

```text
premiere_test/
├── premiere_test.xml
├── prompts.txt
├── scene_01.mp4
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
├── scene_06.mp4
└── template_reference.txt
```

What it does:

- copies `placeholder_master.mp4` to all six scene files
- writes a Premiere-importable XMEML timeline
- writes six prompts based on the lyrics

### 2. Final Cut Pro Real Workflow

Use this when you want a real six-clip import test in Final Cut Pro.

First create an input folder like this:

```text
input_scenes/
├── scene_01.mp4
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
└── scene_06.mp4
```

Rules:

- filenames must match exactly
- each clip must be at least as long as the required scene duration
- the script trims in the FCPXML timeline, not by re-encoding files

Command:

```bash
python3 orchestrate_splurge_fcpxml.py \
  --input_dir input_scenes \
  --lyrics lyrics.txt \
  --bpm 120 \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name fcpx_test
```

This creates:

```text
fcpx_test/
├── fcpx_test.fcpxml
├── prompts.txt
├── scene_01.mp4
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
└── scene_06.mp4
```

What it does:

- validates all six source clips with `ffprobe`
- fails if any clip is too short
- copies the six real clips into the output folder
- writes an FCPXML timeline with each clip trimmed to the beat-based duration
- writes scene prompts using the director style brief plus lyric-based vibe changes

## Final Cut Pro Prompt System

[`orchestrate_splurge_fcpxml.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge_fcpxml.py) reads [`director_style_v1.md`](/Users/ben/Git%20Projects/Content-Agents/director_style_v1.md) at runtime.

That file acts as the base creative brief for every generated scene prompt.

The script then adjusts the mood of each scene from the lyric text. Current vibe patterns include:

- high-energy lines like `fire`, `crash`, `run`, `break` shift toward a volatile ignition look
- uplift lines like `glow`, `light`, `higher`, `rise` shift toward a neon ascent look
- darker or intimate lines like `night`, `shadow`, `dream`, `hold`, `love` shift toward an after-dark mood

Each FCP scene prompt includes:

- the base style brief
- lyric-sensitive vibe
- camera direction
- lighting direction
- palette direction
- texture direction
- timing constraints tied to BPM and bars

## Example Commands

Inline lyrics with the FCP workflow:

```bash
python3 orchestrate_splurge_fcpxml.py \
  --input_dir input_scenes \
  --lyrics "City lights burn through the haze
We run until the skyline breaks
Hands up in the static glow
No sleep, no brakes, just let it show
Crash the silence, start the fire
We lift higher and higher" \
  --bpm 120 \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name real_fcpx_test
```

Inline lyrics with the Premiere workflow:

```bash
python3 orchestrate_splurge.py \
  --lyrics "City lights burn through the haze
We run until the skyline breaks
Hands up in the static glow
No sleep, no brakes, just let it show
Crash the silence, start the fire
We lift higher and higher" \
  --bpm 120 \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name demo_premiere
```

## What To Expect In The Output

`prompts.txt` includes:

- project metadata
- BPM and timing info
- lyric chunk per scene
- bar and beat window per scene
- source clip info for the FCP workflow
- one prompt per scene

FCP prompts additionally reflect:

- [`director_style_v1.md`](/Users/ben/Git%20Projects/Content-Agents/director_style_v1.md)
- lyric-based vibe changes
- camera, lighting, palette, and texture direction

## Import Checklist

### Premiere

1. Run `orchestrate_splurge.py`.
2. Import `<project_name>/<project_name>.xml` into Premiere.
3. Confirm six clips appear in order.
4. Replace placeholder clips later if needed.

### Final Cut Pro

1. Put six real clips in `input_scenes/`.
2. Run `orchestrate_splurge_fcpxml.py`.
3. Import `<project_name>/<project_name>.fcpxml` into Final Cut Pro.
4. Confirm clips appear in order from `scene_01` to `scene_06`.
5. Confirm cuts land on the expected musical boundary.
6. Confirm total length matches `6 * scene_duration`.
7. Export once to verify Final Cut keeps the cut points.

## Validation

Syntax check:

```bash
python3 -m py_compile orchestrate_splurge.py
python3 -m py_compile orchestrate_splurge_fcpxml.py
```

Inspect generated folders:

```bash
ls -l premiere_test
ls -l fcpx_test
```

## Failure Cases

The FCPXML workflow exits early if:

- `--input_dir` is missing
- any required `scene_0X.mp4` file is missing
- `ffprobe` is not installed
- a clip duration cannot be read
- a clip is shorter than the required scene duration
- [`director_style_v1.md`](/Users/ben/Git%20Projects/Content-Agents/director_style_v1.md) is missing

## Current Limitations

- prompt generation is heuristic, not model-driven
- both workflows are fixed to 6 scenes
- Premiere workflow still uses one placeholder source copied six times
- FCPXML workflow currently expects `.mp4` inputs with exact scene filenames
- no audio analysis is performed beyond BPM math
- no direct Premiere or Final Cut Pro API integration exists; both workflows are file-based
