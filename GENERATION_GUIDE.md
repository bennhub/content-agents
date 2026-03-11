# Generation Guide

This guide explains how to generate Final Cut Pro packages for both supported workflows:

- `music_video`
- `advertisement`

Each workflow creates:

- `prompts.txt`
- `director_settings.json`
- copied scene clips
- an `.fcpxml` timeline for Final Cut Pro

## Before You Start

Make sure you have:

- Python 3
- `ffprobe`
- 6 source video clips
- this repo open in Terminal

Check your tools:

```bash
python3 --version
ffprobe -version
```

Open the repo:

```bash
cd "/Users/ben/Git Projects/Content-Agents"
```

## Shared Clip Setup

Both workflows expect 6 input clips in a folder like this:

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

- the names must match exactly
- the clips are copied into the generated output folder
- if a clip is shorter than the target scene length, the script uses the real clip length in the timeline instead of stretching or looping it

## Music Video Workflow

Use this when you want lyric-driven scenes for Nano Banana, LTX, and Final Cut Pro.

### Step 1: Fill Out The Music Brief

Open [music_vid_input.md](/Users/ben/Git%20Projects/Content-Agents/music_vid_input.md).

It should contain:

- `BPM:`
- `## Lyrics`
- `## Creative Notes`

Example structure:

```md
# Project Input

BPM: 120

## Lyrics

Your lyrics here...

## Creative Notes

Moody late-night R&B video, polished lighting, soft haze, reflective surfaces.
```

What the script uses:

- `BPM` for timing
- `Lyrics` for the six scene chunks
- `Creative Notes` for the visual storyline, look, and scene direction

### Step 2: Run The Music Video Generator

```bash
python3 orchestrate_splurge_fcpxml.py \
  --workflow_type music_video \
  --brief_file music_vid_input.md \
  --input_dir input_scenes \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name my_song
```

### Step 3: Review The Output

This creates:

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

Open:

- `my_song/prompts.txt`
- `my_song/director_settings.json`

Check that:

- the six scenes feel like one connected story
- the `Shot card` is clear
- the `Nano Banana prompt` is visually specific
- the `LTX prompt` is motion-focused

### Step 4: Import Into Final Cut Pro

Import:

- `my_song/my_song.fcpxml`

Then check:

- clips are in order
- scene timing feels right
- sequence length looks correct

### Music Video Manual Mode

If you do not want brief-driven auto scene direction, you can run music-video mode manually with lyrics, BPM, and the repo-level [director_settings.json](/Users/ben/Git%20Projects/Content-Agents/director_settings.json):

```bash
python3 orchestrate_splurge_fcpxml.py \
  --workflow_type music_video \
  --lyrics lyrics.txt \
  --bpm 120 \
  --input_dir input_scenes \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name my_song
```

## Advertisement Workflow

Use this when you want six ad scenes built around a product brief instead of lyrics.

### Supported Ad Styles

Advertisement mode supports:

- `brand_spot`
- `lifestyle`
- `ugc`

### Step 1: Fill Out The Ad Brief

Open [ad_project_input.md](/Users/ben/Git%20Projects/Content-Agents/ad_project_input.md).

It should contain:

- `## Product Name`
- `## Audience`
- `## Core Problem`
- `## Value Proposition`
- `## Offer Or CTA`
- `## Creative Notes`
- optional `## Visual References`

What the script uses:

- `Product Name` as the brand/product focus
- `Audience` to shape the ad scenes
- `Core Problem` to create the pain point and hook
- `Value Proposition` to create reveal/demo/benefit scenes
- `Offer Or CTA` for the close
- `Creative Notes` to shape tone and styling
- `Visual References` to support the look

### Step 2: Choose The Ad Style

Pick one:

- `brand_spot` for polished product commercials
- `lifestyle` for aspirational real-life usage
- `ugc` for creator-style or social-native ads

### Step 3: Run The Advertisement Generator

Brand spot example:

```bash
python3 orchestrate_splurge_fcpxml.py \
  --workflow_type advertisement \
  --ad_style brand_spot \
  --brief_file ad_project_input.md \
  --input_dir input_scenes \
  --project_name my_ad
```

Lifestyle example:

```bash
python3 orchestrate_splurge_fcpxml.py \
  --workflow_type advertisement \
  --ad_style lifestyle \
  --brief_file ad_project_input.md \
  --input_dir input_scenes \
  --project_name my_ad
```

UGC example:

```bash
python3 orchestrate_splurge_fcpxml.py \
  --workflow_type advertisement \
  --ad_style ugc \
  --brief_file ad_project_input.md \
  --input_dir input_scenes \
  --project_name my_ad
```

### Step 4: Review The Ad Output

This creates:

```text
my_ad/
├── my_ad.fcpxml
├── prompts.txt
├── director_settings.json
├── scene_01.mp4
├── scene_02.mp4
├── scene_03.mp4
├── scene_04.mp4
├── scene_05.mp4
└── scene_06.mp4
```

Open:

- `my_ad/prompts.txt`
- `my_ad/director_settings.json`

Check that:

- the six scenes follow a clear ad progression
- the ad style is correct for `brand_spot`, `lifestyle`, or `ugc`
- the `Shot card` clearly describes the sales purpose of the scene
- the `Nano Banana prompt` is visually readable
- the `LTX prompt` is usable for motion

### Step 5: Import Into Final Cut Pro

Import:

- `my_ad/my_ad.fcpxml`

Then check:

- the clips are in order
- each scene lands at the expected length
- the ad arc feels correct from hook to CTA

## Common Problems

### Missing Scene Clips

If any of these files are missing, the script stops:

- `scene_01.mp4`
- `scene_02.mp4`
- `scene_03.mp4`
- `scene_04.mp4`
- `scene_05.mp4`
- `scene_06.mp4`

### Music Video: Missing BPM

If [music_vid_input.md](/Users/ben/Git%20Projects/Content-Agents/music_vid_input.md) does not contain a line like:

```md
BPM: 120
```

music-video mode stops.

### Music Video: Missing Lyrics Section

If [music_vid_input.md](/Users/ben/Git%20Projects/Content-Agents/music_vid_input.md) does not contain:

```md
## Lyrics
```

music-video mode stops.

### Advertisement: Missing Product Sections

If [ad_project_input.md](/Users/ben/Git%20Projects/Content-Agents/ad_project_input.md) is missing any required ad section, advertisement mode stops.

### Advertisement: Missing Ad Style

If you run `--workflow_type advertisement` without `--ad_style`, the script stops.

## Quick Version

### Quick Music Video

1. Put 6 clips in `input_scenes/`
2. Fill out `music_vid_input.md`
3. Run the `music_video` command
4. Open the output folder
5. Import the `.fcpxml` into Final Cut Pro

### Quick Advertisement

1. Put 6 clips in `input_scenes/`
2. Fill out `ad_project_input.md`
3. Choose `brand_spot`, `lifestyle`, or `ugc`
4. Run the `advertisement` command
5. Open the output folder
6. Import the `.fcpxml` into Final Cut Pro
