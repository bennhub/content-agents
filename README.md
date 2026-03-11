# Content Agents

`Content Agents` turns lyrics and tempo into a six-scene prompt package plus an edit timeline.

This repo has two workflows:

- [`orchestrate_splurge.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge.py): Premiere/XMEML test workflow using one placeholder clip copied six times
- [`orchestrate_splurge_fcpxml.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge_fcpxml.py): Final Cut Pro workflow with an end-to-end input → create → output path

## End-To-End FCP Workflow

The Final Cut Pro path is now linked together:

1. Input: put lyrics and BPM into [`project_input.md`](/Users/ben/Git%20Projects/Content-Agents/project_input.md)
2. Create: run `orchestrate_splurge_fcpxml.py`
3. Output:
   - scene prompts in `prompts.txt`
   - auto-generated `director_settings.json`
   - copied scene clips
   - Final Cut Pro timeline in `.fcpxml`

The script examines the lyric chunks, builds six scenes, auto-generates visual direction for each scene, and writes everything into the output project folder.

## Project Files

Main files:

- [`orchestrate_splurge.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge.py)
- [`orchestrate_splurge_fcpxml.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge_fcpxml.py)
- [`project_input.md`](/Users/ben/Git%20Projects/Content-Agents/project_input.md)
- [`director_settings.json`](/Users/ben/Git%20Projects/Content-Agents/director_settings.json)
- [`director_style_v1.md`](/Users/ben/Git%20Projects/Content-Agents/director_style_v1.md)
- [`premiere_xml_logic.md`](/Users/ben/Git%20Projects/Content-Agents/premiere_xml_logic.md)

Current repo layout:

```text
Content-Agents/
├── orchestrate_splurge.py
├── orchestrate_splurge_fcpxml.py
├── project_input.md
├── director_settings.json
├── director_style_v1.md
├── placeholder_master.mp4
├── premiere_xml_logic.md
└── README.md
```

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

## How To Run

Run commands from the repo root.

### Premiere Test Workflow

Use this when you want a quick timing/import test in Premiere with placeholder media.

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

### Final Cut Pro Workflow: Recommended Brief-Driven Mode

1. Edit [`project_input.md`](/Users/ben/Git%20Projects/Content-Agents/project_input.md):

```md
# Project Input

BPM: 120

## Lyrics

Your lyrics here...

## Creative Notes

Optional notes here...
```

2. Put six clips in an input folder:

```text
input_scenes/
├── scene_01.mp4
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
└── scene_06.mp4
```

3. Run:

```bash
python3 orchestrate_splurge_fcpxml.py \
  --brief_file project_input.md \
  --input_dir input_scenes \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name fcpx_test
```

This creates:

```text
fcpx_test/
├── fcpx_test.fcpxml
├── prompts.txt
├── director_settings.json
├── scene_01.mp4
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
└── scene_06.mp4
```

What this mode does:

- reads BPM and lyrics from `project_input.md`
- splits the lyrics into 6 scenes
- auto-generates `director_settings.json` from the lyric content
- validates all six source clips with `ffprobe`
- copies the clips into the output folder
- writes the scene prompts and `.fcpxml` timeline

### Final Cut Pro Workflow: Manual JSON Mode

If you want to hand-author the scene direction instead of auto-generating it, keep using the root-level [`director_settings.json`](/Users/ben/Git%20Projects/Content-Agents/director_settings.json).

```bash
python3 orchestrate_splurge_fcpxml.py \
  --lyrics lyrics.txt \
  --bpm 120 \
  --input_dir input_scenes \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name fcpx_test
```

In this mode the script:

- reads lyrics from `--lyrics`
- reads BPM from `--bpm`
- reads scene styles from the repo-level `director_settings.json`

## Final Cut Pro Prompt And Scene Style System

The FCP script supports two style sources:

1. Auto-generated mode via `--brief_file`
2. Manual JSON mode via repo-level `director_settings.json`

In auto-generated mode:

- the script reads BPM and lyrics from the markdown brief
- it splits the lyrics into scenes
- it examines each lyric chunk
- it creates a matching `style`, `camera`, `lighting`, and `palette`
- it writes those settings to `<project_name>/director_settings.json`

In manual mode:

- the script reads [`director_settings.json`](/Users/ben/Git%20Projects/Content-Agents/director_settings.json) from the repo root
- each array item maps to a scene index

JSON scene mapping:

- item `0` = scene 1
- item `1` = scene 2
- item `2` = scene 3
- item `3` = scene 4
- item `4` = scene 5
- item `5` = scene 6

Each scene entry can define:

- `style`
- `camera`
- `lighting`
- `palette`

If a scene entry is missing, the script falls back to a generic `Cinematic` style.

## What To Expect In The Output

`prompts.txt` includes:

- project metadata
- BPM and timing info
- lyric chunk per scene
- bar and beat window per scene
- source clip info
- one prompt per scene

In brief-driven mode, the output folder also contains:

- auto-generated `director_settings.json`

The FCP prompts combine:

- the lyric chunk
- energy inferred from the lyric text
- scene camera direction
- scene lighting direction
- scene palette direction
- timing constraints tied to BPM and bars

## Import Checklist

### Premiere

1. Run `orchestrate_splurge.py`.
2. Import `<project_name>/<project_name>.xml` into Premiere.
3. Confirm six clips appear in order.
4. Replace placeholder clips later if needed.

### Final Cut Pro

1. Put six real clips in `input_scenes/`.
2. Fill out [`project_input.md`](/Users/ben/Git%20Projects/Content-Agents/project_input.md) or update [`director_settings.json`](/Users/ben/Git%20Projects/Content-Agents/director_settings.json).
3. Run `orchestrate_splurge_fcpxml.py`.
4. Import `<project_name>/<project_name>.fcpxml` into Final Cut Pro.
5. Confirm clips appear in order from `scene_01` to `scene_06`.
6. Confirm cuts land on the expected musical boundary.
7. Confirm total length matches `6 * scene_duration`.
8. Export once to verify Final Cut keeps the cut points.

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
- neither `--brief_file` nor `--lyrics` is provided
- no BPM is available from `--bpm` or the markdown brief
- the brief file is missing a `BPM:` line
- the brief file is missing a `## Lyrics` section
- any required `scene_0X.mp4` file is missing
- `ffprobe` is not installed
- a clip duration cannot be read
- a clip is shorter than the required scene duration
- manual mode is used and [`director_settings.json`](/Users/ben/Git%20Projects/Content-Agents/director_settings.json) is missing
- manual mode is used and [`director_settings.json`](/Users/ben/Git%20Projects/Content-Agents/director_settings.json) is not a valid JSON array

## Current Limitations

- prompt generation is heuristic, not model-driven
- both workflows are fixed to 6 scenes
- Premiere workflow still uses one placeholder source copied six times
- FCPXML workflow currently expects `.mp4` inputs with exact scene filenames
- FCP scene style generation is heuristic
- no audio analysis is performed beyond BPM math
- no direct Premiere or Final Cut Pro API integration exists; both workflows are file-based
