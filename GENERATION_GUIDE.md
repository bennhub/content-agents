# Generation Guide

This guide shows the full step-by-step flow for generating a Final Cut Pro package with prompts, scene styles, copied clips, and an `.fcpxml` timeline.

## What You Need

Before you start, make sure you have:

- Python 3 installed
- `ffprobe` installed
- 6 source video clips
- your lyrics
- the repo open in the terminal

Check your tools:

```bash
python3 --version
ffprobe -version
```

## Step 1: Open The Repo

In Terminal:

```bash
cd "/Users/ben/Git Projects/Content-Agents"
```

## Step 2: Prepare Your Input Clips

Create a folder called `input_scenes` in the repo root and put your 6 clips inside it using these exact names:

```text
input_scenes/
├── scene_01.mp4
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
└── scene_06.mp4
```

Important:

- the names must match exactly
- each clip must be long enough for the scene timing you want
- at `120 BPM`, `4/4`, `2 bars per scene`, each clip must be at least `4.0s`

## Step 3: Fill Out The Project Brief

Open [`project_input.md`](/Users/ben/Git%20Projects/Content-Agents/project_input.md).

Edit:

- `BPM:`
- the `## Lyrics` section
- the `## Creative Notes` section

Example:

```md
# Project Input

BPM: 120

## Lyrics

City lights burn through the haze
We run until the skyline breaks
Hands up in the static glow
No sleep, no brakes, just let it show
Crash the silence, start the fire
We lift higher and higher

## Creative Notes

Keep it premium, high-motion, and cinematic.
Lean into wet reflections, haze, and strong practical lighting.
```

How the app uses this file:

- `BPM:` sets timing
- `## Lyrics` gets split into 6 scenes
- `## Creative Notes` influences the auto-generated camera, lighting, and palette choices

## Step 4: Run The Generator

Run:it

```bash
python3 orchestrate_splurge_fcpxml.py \
  --brief_file project_input.md \
  --input_dir input_scenes \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name my_song
```

What happens during this step:

1. The app reads `project_input.md`
2. It extracts BPM
3. It extracts lyrics
4. It splits the lyrics into 6 scenes
5. It examines the lyrics and creative notes
6. It auto-generates a `director_settings.json` for those 6 scenes
7. It validates the 6 input clips with `ffprobe`
8. It copies those clips into the output folder
9. It generates `prompts.txt`
10. It generates `my_song.fcpxml`

## Step 5: Check The Output Folder

After the script finishes, you should get:

```text
my_song/
├── my_song.fcpxml
├── prompts.txt
├── director_settings.json
├── scene_01.mp4
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
└── scene_06.mp4
```

What each file is for:

- `my_song.fcpxml`: import this into Final Cut Pro
- `prompts.txt`: scene prompts for generation or review
- `director_settings.json`: the auto-generated scene visual direction
- `scene_01.mp4` to `scene_06.mp4`: copied media used by the timeline

## Step 6: Review The Generated Scene Direction

Open:

- `my_song/prompts.txt`
- `my_song/director_settings.json`

Check that:

- the 6 lyric chunks make sense
- the prompts match the mood of the lyrics
- the generated camera, lighting, and palette feel right

If you want a different look:

1. change `## Creative Notes` in `project_input.md`
2. run the generator again

## Step 7: Import Into Final Cut Pro

In Final Cut Pro:

1. Import `my_song/my_song.fcpxml`
2. Check that the 6 clips appear in order
3. Check that cuts land on the expected timing
4. Check total sequence length

At `120 BPM`, `4/4`, `2 bars per scene`:

- each clip should land at `4s`
- total timeline length should be `24s`

## Step 8: Export A Test

Export once from Final Cut Pro and confirm:

- the clips stay in order
- the cut points remain correct
- Final Cut does not shift or rewrite the timing in a bad way

## If You Want Manual Control Instead

If you do not want automatic scene style generation, you can run the app in manual mode using the root-level [`director_settings.json`](/Users/ben/Git%20Projects/Content-Agents/director_settings.json).

Command:

```bash
python3 orchestrate_splurge_fcpxml.py \
  --lyrics lyrics.txt \
  --bpm 120 \
  --input_dir input_scenes \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name my_song
```

In that mode:

- lyrics come from `--lyrics`
- BPM comes from `--bpm`
- scene styles come from the repo-level `director_settings.json`

## Common Problems

### Missing BPM

If `project_input.md` does not contain a line like:

```md
BPM: 120
```

the script will stop.

### Missing Lyrics Section

If `project_input.md` does not contain:

```md
## Lyrics
```

the script will stop.

### Missing Scene Clips

If any of these files are missing:

- `scene_01.mp4`
- `scene_02.mp4`
- `scene_03.mp4`
- `scene_04.mp4`
- `scene_05.mp4`
- `scene_06.mp4`

the script will stop.

### Clips Too Short

If a clip is shorter than the required scene length, the script will stop before it generates a broken timeline.

## Quick Version

If you just want the shortest possible checklist:

1. Put 6 clips in `input_scenes/`
2. Fill out `project_input.md`
3. Run the generator command
4. Open the output folder
5. Import the `.fcpxml` into Final Cut Pro
