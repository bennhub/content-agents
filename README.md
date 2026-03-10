# Content Agents

`Content Agents` is a small utility project for turning song lyrics and tempo into:

- a six-scene visual treatment for AI video generation
- a `prompts.txt` file for a ComfyUI or prompt-driven video workflow
- a Premiere-compatible Final Cut Pro 7 XML (`.xml`) timeline
- six placeholder clip files so Premiere can place media on the timeline immediately

The current script in this repo is built around a specific workflow:

1. Take lyrics and BPM from a song.
2. Break the song concept into 6 scenes.
3. Calculate scene timing from BPM and musical bars.
4. Generate one dense LTX 2.3-style prompt per scene.
5. Create an XML timeline that places `scene_01.mp4` through `scene_06.mp4` back-to-back.
6. Copy `placeholder_master.mp4` into the output folder for each scene so Premiere can resolve media paths immediately.

## What This Project Does

The main script is [`orchestrate_splurge.py`](/Users/ben/Git Projects/Content-Agents/orchestrate_splurge.py).

It accepts:

- `--lyrics`: raw lyric text or a path to a text file
- `--bpm`: the song tempo
- `--project_name`: the name of the output folder and XML sequence prefix
- `--beats_per_bar`: time signature numerator, default `4`
- `--bars_per_scene`: bars per scene, default `2`

It then generates:

- `prompts.txt`: six scene prompts based on the lyric content and BPM
- `<project_name>.xml`: a Premiere-importable XMEML timeline
- `scene_01.mp4` to `scene_06.mp4`: copies of `placeholder_master.mp4` inside the output folder
- `template_reference.txt`: a copy of the XML logic template used by the script

The XML logic reference lives in [`premiere_xml_logic.md`](/Users/ben/Git Projects/Content-Agents/premiere_xml_logic.md).

## Project Structure

Current repo layout:

```text
Content-Agents/
├── orchestrate_splurge.py
├── premiere_xml_logic.md
├── README.md
└── <generated project folders>/
```

Example generated output:

```text
demo_splurge/
├── demo_splurge.xml
├── prompts.txt
├── scene_01.mp4
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
├── scene_06.mp4
└── template_reference.txt
```

## Requirements

You only need Python 3.

Check that Python is available:

```bash
python3 --version
```

No external Python packages are required right now. The script uses only the Python standard library.

You also need [`placeholder_master.mp4`](/Users/ben/Git Projects/Content-Agents/placeholder_master.mp4) in the repo root. The script copies that file into each generated project folder as the six scene clips used by the XML.

## How The Script Works

### 1. Lyrics Input

The script accepts lyrics in two ways:

- inline text passed directly to `--lyrics`
- a text file path passed to `--lyrics`

If the value you pass is a valid file path, the script reads the file contents. Otherwise it treats the value as the lyric text itself.

### 2. Scene Splitting

The script creates exactly 6 scenes.

- If your lyrics have multiple lines, it uses the lines as the base units.
- If your lyrics are one long block, it splits them into phrases.
- Those units are distributed across 6 scene buckets.

### 3. BPM And Bar Timing

The script now derives scene duration from musical timing instead of using a hardcoded 5-second segment.

The timing math is:

- seconds per beat = `60 / BPM`
- beats per scene = `beats_per_bar * bars_per_scene`
- seconds per scene = `beats_per_scene * (60 / BPM)`
- frames per scene = `seconds_per_scene * 23.976`

Default timing:

- `beats_per_bar = 4`
- `bars_per_scene = 2`

That means the default scene length is `8 beats`.

Example at `120 BPM`:

- `0.5s` per beat
- `8 beats` per scene
- `4.00s` per scene
- `96` frames per scene

### 4. Prompt Generation

For each scene, the script creates a prompt with:

- a scene number
- an emotional phase
- a visual motif
- a color palette
- a motion style
- BPM-aware beat timing
- bar window
- the lyric chunk that scene is based on

These prompts are written to `prompts.txt`.

### 5. XML Timeline Generation

The script writes a Final Cut Pro 7 XML file (`XMEML version 4`) with:

- 720p video settings
- `timebase` 24
- `ntsc` set to `TRUE`
- 6 clips on one video track
- frame duration derived from BPM timing
- clip names `scene_01.mp4` through `scene_06.mp4`
- `pathurl` entries pointing to the absolute path of the generated output folder

### 6. Placeholder Media Creation

The script also creates:

- `scene_01.mp4`
- `scene_02.mp4`
- `scene_03.mp4`
- `scene_04.mp4`
- `scene_05.mp4`
- `scene_06.mp4`

These are copies of `placeholder_master.mp4`. Their purpose is to make Premiere see media at the expected paths immediately after XML import.

Important detail:

- The script requires `placeholder_master.mp4` in the repo root.
- If it is missing, the script exits with a clear error.
- In a real workflow, you can replace the generated `scene_01.mp4` through `scene_06.mp4` files with final renders that keep the same filenames.

## Commands To Run The Script

### Basic Command

Run from the repo root:

```bash
python3 orchestrate_splurge.py --lyrics "Your lyrics here" --bpm 128 --project_name my_project
```

### BPM-Locked Command

```bash
python3 orchestrate_splurge.py --lyrics lyrics.txt --bpm 120 --project_name my_project --beats_per_bar 4 --bars_per_scene 2
```

### Using A Lyrics File

If you have a lyrics text file:

```bash
python3 orchestrate_splurge.py --lyrics lyrics.txt --bpm 120 --project_name my_project --beats_per_bar 4 --bars_per_scene 2
```

### Example With Multi-Line Lyrics

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
  --project_name demo_splurge
```

## What Happens After Running

If you run:

```bash
python3 orchestrate_splurge.py --lyrics lyrics.txt --bpm 120 --project_name demo_splurge --beats_per_bar 4 --bars_per_scene 2
```

The script creates:

```text
demo_splurge/
├── demo_splurge.xml
├── prompts.txt
├── scene_01.mp4
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
├── scene_06.mp4
└── template_reference.txt
```

And prints output like:

```text
Wrote prompts: /absolute/path/to/demo_splurge/prompts.txt
Wrote XML: /absolute/path/to/demo_splurge/demo_splurge.xml
```

## How To Use This In Practice

### Workflow Overview

Use this project when you want to go from song concept to edit prep quickly.

Recommended workflow:

1. Write or collect your lyrics.
2. Decide the BPM of the track.
3. Decide the musical structure, usually `4/4` and `2 bars per scene` to start.
4. Run `orchestrate_splurge.py`.
5. Open the generated `prompts.txt`.
6. Use each scene prompt to generate one visual clip in your video generation pipeline.
7. Import the generated `.xml` file into Premiere to test the cut layout.
8. Replace the placeholder `scene_01.mp4` through `scene_06.mp4` files with your real rendered clips if needed.
9. Review the timeline and adjust timing or shot choices as needed.

### Premiere Import Steps

1. Generate a project folder with the script.
2. Keep the generated clip filenames exactly the same.
3. In Premiere Pro, import the XML file from the generated project folder.
4. Premiere should place the copied placeholder clips on the timeline according to the XML sequence structure.
5. Replace those placeholder clips with real renders later if needed.

### ComfyUI Or Prompt Workflow Steps

1. Open `prompts.txt`.
2. Copy the prompt under `[Scene 01]` into your video generation tool.
3. Render and save the resulting clip as `scene_01.mp4`.
4. Repeat for scenes 2 through 6.
5. Put all six rendered clips in the generated output folder.
6. Import the XML into Premiere once your clips are ready.

## Output Files Explained

### `prompts.txt`

Contains:

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
- one full prompt for each scene

### `<project_name>.xml`

Contains:

- sequence metadata
- video track layout
- one clip item for each scene
- timing information
- absolute media paths

### `template_reference.txt`

Contains a copy of the XML template reference used by the generator. This is there for transparency and debugging.

## Commands For Validation

To verify the script syntax:

```bash
python3 -m py_compile orchestrate_splurge.py
```

To run a quick test:

```bash
python3 orchestrate_splurge.py --lyrics lyrics.txt --bpm 120 --project_name test_project --beats_per_bar 4 --bars_per_scene 2
```

To inspect generated files:

```bash
ls -l test_project
```

## Common Notes

### Why are the generated `.mp4` files copies of the same video?

They are copied from `placeholder_master.mp4` so the XML points to media files that already exist at import time.

### What happens if `placeholder_master.mp4` is missing?

The script exits with:

```text
Error: placeholder_master.mp4 not found in root. Please add a test video file to continue.
```

### Why does the XML use `timebase 24` if the target is 23.976 fps?

This is normal in older FCP7/XMEML style exports when paired with `ntsc TRUE`. The script follows the requested XML convention.

### Can I change the number of scenes?

Not yet from the command line. The current script is fixed to 6 scenes.

### Can I change the scene length?

Yes. Change:

- `--bpm`
- `--beats_per_bar`
- `--bars_per_scene`

At `120 BPM`:

- `2 bars per scene` in `4/4` = `4.00s`
- `4 bars per scene` in `4/4` = `8.00s`

## Current Limitations

- prompt generation is heuristic, not model-driven
- the script always creates exactly 6 scenes
- all six placeholder clips are copies of the same source video
- no audio analysis is performed beyond BPM math
- no direct Premiere API integration exists; this is XML-based only

## Next Improvements You Could Add

- support `--scene-count`
- support reading lyrics from `.md` or `.json` project files
- generate real color/mood metadata as JSON
- emit shot lists or storyboard cards
- create generated placeholder videos automatically instead of copying one master file
- add tests for scene splitting and XML generation

## Quick Start

If you only want the shortest path:

1. Put lyrics into `lyrics.txt`
2. Run:

```bash
python3 orchestrate_splurge.py --lyrics lyrics.txt --bpm 120 --project_name my_song --beats_per_bar 4 --bars_per_scene 2
```

3. Open `my_song/prompts.txt`
4. Import `my_song/my_song.xml` into Premiere to confirm the cut layout
5. Generate your six real clips
6. Replace `scene_01.mp4` to `scene_06.mp4` if needed

## command example
```bash
python3 orchestrate_splurge.py --lyrics "City lights burn through the haze
  We run until the skyline breaks
  Hands up in the static glow
  No sleep, no brakes, just let it show
  Crash the silence, start the fire
  We lift higher and higher" --bpm 120 --beats_per_bar 4 --bars_per_scene 1 --project_name two_second_test
  ```