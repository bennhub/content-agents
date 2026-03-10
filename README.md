# Content Agents

`Content Agents` turns song lyrics and tempo into:

- a six-scene visual treatment for AI video generation
- a `prompts.txt` file for prompt-driven video workflows
- a Premiere-compatible Final Cut Pro 7 XML (`.xml`) timeline
- a Final Cut Pro FCPXML (`.fcpxml`) timeline

There are now two separate generator scripts:

- [`orchestrate_splurge.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge.py): Premiere/XMEML workflow using six copied placeholder clips
- [`orchestrate_splurge_fcpxml.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge_fcpxml.py): Final Cut Pro workflow using six real input clips from a folder

## What Each Script Does

### Premiere Test Workflow

[`orchestrate_splurge.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge.py) is the original test workflow.

It:

1. Reads lyrics and BPM.
2. Splits the lyrics into 6 scenes.
3. Calculates scene timing from BPM and bars.
4. Generates one prompt per scene.
5. Writes a Premiere-importable `.xml` timeline.
6. Copies [`placeholder_master.mp4`](/Users/ben/Git%20Projects/Content-Agents/placeholder_master.mp4) to `scene_01.mp4` through `scene_06.mp4` so Premiere can place media immediately.

Use this when you want a quick placeholder timeline test in Premiere.

### Final Cut Pro Real-Clip Workflow

[`orchestrate_splurge_fcpxml.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_splurge_fcpxml.py) is the Final Cut Pro workflow.

It:

1. Reads lyrics and BPM.
2. Splits the lyrics into 6 scenes.
3. Calculates scene timing from BPM and bars.
4. Validates six real source clips from an input folder.
5. Fails if any clip is shorter than the required scene length.
6. Copies those six clips into the generated project folder.
7. Writes a `.fcpxml` timeline that trims each clip to the beat-based scene duration.

Use this when you want a real import test in Final Cut Pro with six distinct clips.

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

Example at `120 BPM` in `4/4` with `2 bars per scene`:

- 1 beat = `0.5s`
- 1 bar = `2.0s`
- 2 bars = `4.0s`
- each scene clip is placed as `4.0s`
- total timeline length is `24.0s`

## Requirements

You need:

- Python 3
- `ffprobe` for the FCPXML real-clip workflow

Check them with:

```bash
python3 --version
ffprobe -version
```

No external Python packages are required.

For the Premiere test workflow, you also need [`placeholder_master.mp4`](/Users/ben/Git%20Projects/Content-Agents/placeholder_master.mp4) in the repo root.

## Project Structure

Current repo layout:

```text
Content-Agents/
├── orchestrate_splurge.py
├── orchestrate_splurge_fcpxml.py
├── placeholder_master.mp4
├── premiere_xml_logic.md
└── README.md
```

## Premiere Test Workflow

### Inputs

`orchestrate_splurge.py` accepts:

- `--lyrics`
- `--bpm`
- `--project_name`
- `--beats_per_bar` default `4`
- `--bars_per_scene` default `2`

### Output

It generates:

- `prompts.txt`
- `<project_name>.xml`
- `scene_01.mp4` through `scene_06.mp4` copied from `placeholder_master.mp4`
- `template_reference.txt`

### Example Command

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

### Example Output

```text
demo_premiere/
├── demo_premiere.xml
├── prompts.txt
├── scene_01.mp4
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
├── scene_06.mp4
└── template_reference.txt
```

### Notes

- All six generated clips are copies of the same placeholder source.
- This is intended for timing/import testing, not a real six-clip edit.

## Final Cut Pro Real-Clip Workflow

### Inputs

`orchestrate_splurge_fcpxml.py` accepts:

- `--input_dir`
- `--lyrics`
- `--bpm`
- `--project_name`
- `--beats_per_bar` default `4`
- `--bars_per_scene` default `2`

### Required Input Folder Layout

`--input_dir` must contain exactly these six files:

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
- the script inspects duration with `ffprobe`
- the script trims in the FCPXML timeline only; it does not re-encode or pre-trim media files

### Output

It generates:

- `prompts.txt`
- `<project_name>.fcpxml`
- `scene_01.mp4` through `scene_06.mp4` copied from `--input_dir`

### Example Command

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

### Example Output

```text
real_fcpx_test/
├── real_fcpx_test.fcpxml
├── prompts.txt
├── scene_01.mp4
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
└── scene_06.mp4
```

### Final Cut Pro Behavior

The generated FCPXML:

- creates one asset for each copied scene clip
- preserves each source clip's full duration in the asset definition
- places six clips back-to-back on the primary storyline
- trims each clip instance to the beat-derived scene length

At `120 BPM`, `4/4`, `2 bars per scene`, each imported clip should land at `4s` and the total timeline should be `24s`.

### Failure Cases

The FCPXML script exits early if:

- `--input_dir` is missing
- any required `scene_0X.mp4` file is missing
- `ffprobe` is not installed
- a clip duration cannot be read
- a clip is shorter than the required scene duration

### Real Test Checklist

For a clean Final Cut Pro test:

1. Put six real clips in `input_scenes/` named `scene_01.mp4` through `scene_06.mp4`.
2. Make sure each clip is at least as long as the target scene duration.
3. Run `orchestrate_splurge_fcpxml.py` with `--input_dir input_scenes`.
4. Import `<project_name>/<project_name>.fcpxml` into Final Cut Pro.
5. Confirm the clips appear in order from `scene_01` to `scene_06`.
6. Confirm each cut lands on the expected musical boundary.
7. Confirm the total timeline length matches `6 * scene_duration`.
8. Export once to verify Final Cut keeps the cut points unchanged.

## Prompts Output

Both scripts write `prompts.txt` containing:

- project metadata
- BPM
- time signature
- bars per scene
- beats per scene
- scene length
- frame count per scene
- lyric chunk for each scene
- bar window for each scene
- beat window for each scene
- one full LTX-style prompt for each scene

The FCPXML workflow also records:

- input directory
- source clip filename for each scene
- source clip duration for each scene

## Validation Commands

Syntax check:

```bash
python3 -m py_compile orchestrate_splurge.py
python3 -m py_compile orchestrate_splurge_fcpxml.py
```

Quick Premiere test:

```bash
python3 orchestrate_splurge.py \
  --lyrics lyrics.txt \
  --bpm 120 \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name premiere_test
```

Quick Final Cut Pro test:

```bash
python3 orchestrate_splurge_fcpxml.py \
  --input_dir input_scenes \
  --lyrics lyrics.txt \
  --bpm 120 \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name fcpx_test
```

Inspect generated files:

```bash
ls -l premiere_test
ls -l fcpx_test
```

## Current Limitations

- prompt generation is heuristic, not model-driven
- both workflows are fixed to 6 scenes
- Premiere workflow still uses one placeholder source copied six times
- FCPXML workflow currently expects `.mp4` inputs with exact scene filenames
- no audio analysis is performed beyond BPM math
- no direct Premiere or Final Cut Pro API integration exists; both workflows are file-based

## Quick Start

If you only want the shortest path for Final Cut Pro:

1. Put six real clips in `input_scenes/` named `scene_01.mp4` through `scene_06.mp4`.
2. Put lyrics into `lyrics.txt`.
3. Run:

```bash
python3 orchestrate_splurge_fcpxml.py \
  --input_dir input_scenes \
  --lyrics lyrics.txt \
  --bpm 120 \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name my_song
```

4. Import `my_song/my_song.fcpxml` into Final Cut Pro.
5. Confirm each cut lands on the expected musical boundary.
