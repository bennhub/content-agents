# Generation Guide

This guide explains the current repo flow after the reorganization.

## Repo Layout

Use these folders consistently:

- briefs: project briefs you edit before generation
- config: reusable config files the scripts read
- docs: guides, planning notes, and logic references
- input_scenes: the six source clips for FCP generation
- output: generated project folders

## Why The Workflow Uses Six Scenes

The current generator is scoped to 6 scenes on purpose.

The main use case right now is short-form content:

- short ads
- short music video posts
- promo-style social clips

The intended rhythm is:

- each scene is roughly 5 seconds
- 6 scenes produces a package around 30 seconds total

That keeps the workflow practical for fast content generation and testing. The six-scene setup is the current baseline, not the final limit. The project can expand to longer formats later once the workflow types and prompt systems are stable.

## Shared Setup

1. Open the repo:

```bash
cd "/Users/ben/Git Projects/Content-Agents"
```

2. Check tools:

```bash
python3 --version
ffprobe -version
```

3. Put six source clips in `input_scenes/`:

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

- the filenames must match exactly
- the clips are copied into the generated project folder
- if a clip is shorter than the target scene length, the FCP timeline uses the real clip length instead of stretching or looping it

## Music Video Workflow

### Step 1: Fill Out The Brief

Edit [`briefs/music_vid_input.md`](/Users/ben/Git%20Projects/Content-Agents/briefs/music_vid_input.md).

Required sections:

- `BPM:`
- `## Lyrics`
- `## Creative Notes`

### Step 2: Run The Generator

```bash
python3 orchestrate_fcpxml.py \
  --workflow_type music_video \
  --brief_file briefs/music_vid_input.md \
  --input_dir input_scenes \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name output/my_song
```

### Step 3: Review The Output

This creates:

```text
output/my_song/
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

Review:

- `output/my_song/prompts.txt`
- `output/my_song/director_settings.json`

Check:

- the six scenes feel like one connected visual story
- the `Shot card` is usable
- the `Nano Banana prompt` is image-friendly
- the `LTX prompt` is motion-focused

### Step 4: Import Into Final Cut Pro

Import:

- `output/my_song/my_song.fcpxml`

## Manual Music Video Mode

If you do not want brief-driven scene styling, edit [`config/director_settings.json`](/Users/ben/Git%20Projects/Content-Agents/config/director_settings.json) and run:

```bash
python3 orchestrate_fcpxml.py \
  --workflow_type music_video \
  --lyrics lyrics.txt \
  --bpm 120 \
  --input_dir input_scenes \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name output/my_song
```

In this mode:

- lyrics come from `--lyrics`
- BPM comes from `--bpm`
- scene style comes from `config/director_settings.json`

## Advertisement Workflow

### Step 1: Fill Out The Brief

Edit [`briefs/ad_project_input.md`](/Users/ben/Git%20Projects/Content-Agents/briefs/ad_project_input.md).

Required sections:

- `## Product Name`
- `## Audience`
- `## Core Problem`
- `## Value Proposition`
- `## Offer Or CTA`
- `## Creative Notes`

Optional:

- `## Visual References`

### Step 2: Choose The Ad Style

Pick one:

- `brand_spot`
- `lifestyle`
- `ugc`

### Step 3: Run The Generator

Brand spot:

```bash
python3 orchestrate_fcpxml.py \
  --workflow_type advertisement \
  --ad_style brand_spot \
  --brief_file briefs/ad_project_input.md \
  --input_dir input_scenes \
  --project_name output/my_ad
```

Lifestyle:

```bash
python3 orchestrate_fcpxml.py \
  --workflow_type advertisement \
  --ad_style lifestyle \
  --brief_file briefs/ad_project_input.md \
  --input_dir input_scenes \
  --project_name output/my_ad
```

UGC:

```bash
python3 orchestrate_fcpxml.py \
  --workflow_type advertisement \
  --ad_style ugc \
  --brief_file briefs/ad_project_input.md \
  --input_dir input_scenes \
  --project_name output/my_ad
```

### Step 4: Review The Output

This creates:

```text
output/my_ad/
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

Review:

- `output/my_ad/prompts.txt`
- `output/my_ad/director_settings.json`

Check:

- the six scenes follow a clear ad arc
- the ad style reads correctly
- the prompts are usable for Nano Banana and LTX

### Step 5: Import Into Final Cut Pro

Import:

- `output/my_ad/my_ad.fcpxml`

## Common Problems

### Missing Scene Clips

If any `scene_01.mp4` through `scene_06.mp4` files are missing from `input_scenes/`, the script stops.

### Music Video Brief Missing BPM

If [`briefs/music_vid_input.md`](/Users/ben/Git%20Projects/Content-Agents/briefs/music_vid_input.md) does not contain `BPM: <number>`, music-video mode stops.

### Music Video Brief Missing Lyrics

If [`briefs/music_vid_input.md`](/Users/ben/Git%20Projects/Content-Agents/briefs/music_vid_input.md) does not contain `## Lyrics`, music-video mode stops.

### Advertisement Brief Missing Product Sections

If [`briefs/ad_project_input.md`](/Users/ben/Git%20Projects/Content-Agents/briefs/ad_project_input.md) is missing required sections, advertisement mode stops.

### Manual JSON Mode Missing Config

If [`config/director_settings.json`](/Users/ben/Git%20Projects/Content-Agents/config/director_settings.json) is missing or invalid, manual music-video mode stops.

## Quick Version

### Quick Music Video

1. Put 6 clips in `input_scenes/`
2. Fill out `briefs/music_vid_input.md`
3. Run the music-video command
4. Review `output/my_song/prompts.txt`
5. Import `output/my_song/my_song.fcpxml` into Final Cut Pro

### Quick Advertisement

1. Put 6 clips in `input_scenes/`
2. Fill out `briefs/ad_project_input.md`
3. Choose `brand_spot`, `lifestyle`, or `ugc`
4. Run the advertisement command
5. Review `output/my_ad/prompts.txt`
6. Import `output/my_ad/my_ad.fcpxml` into Final Cut Pro
