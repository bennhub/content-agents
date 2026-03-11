# Content Agents

`Content Agents` generates prompt packages plus edit timelines for multiple content workflows.

## How The Project Works

This project is not just “a script that does everything by itself.”

The actual operating model is:

- a coding agent such as Codex or Claude Code works through the CLI
- the agent reads the project brief and repo structure
- the Python scripts execute the workflow logic
- the scripts generate prompts, scene direction, and edit timeline files
- those outputs are then used in tools like Nano Banana, LTX, Premiere, or Final Cut Pro

So the real engine is:

- AI coding agent
- CLI workflow
- Python generation scripts

The scripts are the execution layer. The higher-level workflow reasoning, brief handling, repo updates, and process orchestration come from the agent operating in the terminal.

Current workflows:

- [`orchestrate_premxml.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_premxml.py): Premiere/XMEML placeholder test workflow
- [`orchestrate_fcpxml.py`](/Users/ben/Git%20Projects/Content-Agents/orchestrate_fcpxml.py): Final Cut Pro workflow for `music_video` and `advertisement`

## Repo Structure

```text
Content-Agents/
├── orchestrate_premxml.py
├── orchestrate_fcpxml.py
├── briefs/
│   ├── music_vid_input.md
│   └── ad_project_input.md
├── config/
│   └── director_settings.json
├── docs/
│   ├── BACKLOG.md
│   ├── GENERATION_GUIDE.md
│   └── premiere_xml_logic.md
├── input_scenes/
└── output/
```

Use:

- [`briefs/music_vid_input.md`](/Users/ben/Git%20Projects/Content-Agents/briefs/music_vid_input.md) for music video briefs
- [`briefs/ad_project_input.md`](/Users/ben/Git%20Projects/Content-Agents/briefs/ad_project_input.md) for advertisement briefs
- [`config/director_settings.json`](/Users/ben/Git%20Projects/Content-Agents/config/director_settings.json) for manual music-video scene styling
- [`docs/GENERATION_GUIDE.md`](/Users/ben/Git%20Projects/Content-Agents/docs/GENERATION_GUIDE.md) for step-by-step usage
- [`docs/BACKLOG.md`](/Users/ben/Git%20Projects/Content-Agents/docs/BACKLOG.md) for planned next workflows

## Requirements

You need:

- Python 3
- `ffprobe` for the FCP workflow

Check them with:

```bash
python3 --version
ffprobe -version
```

## Why Six Scenes

This repo is currently optimized around 6 input clips because the primary target is short-form content:

- short ads
- short music video posts
- other social-first vertical or promo edits

The working assumption is:

- each scene lands at roughly 5 seconds
- 6 scenes gives you a package around 30 seconds total

That makes the workflow fast to generate, easy to review, and practical for short-form testing.

This is a starting constraint, not a permanent one. The current system is intentionally scoped to a simple six-scene structure first so the prompt generation, timing logic, and edit export flow stay reliable while the project expands into more workflows later.

## How To Run

Run commands from the repo root.

### Premiere Test Workflow

```bash
python3 orchestrate_premxml.py \
  --lyrics lyrics.txt \
  --bpm 120 \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name output/premiere_test
```

This writes a Premiere test package to `output/premiere_test/`.

### Final Cut Pro: Music Video

1. Fill out [`briefs/music_vid_input.md`](/Users/ben/Git%20Projects/Content-Agents/briefs/music_vid_input.md).
2. Put six clips in `input_scenes/` named `scene_01.mp4` through `scene_06.mp4`.
3. Run:

```bash
python3 orchestrate_fcpxml.py \
  --workflow_type music_video \
  --brief_file briefs/music_vid_input.md \
  --input_dir input_scenes \
  --beats_per_bar 4 \
  --bars_per_scene 2 \
  --project_name output/my_song
```

This writes:

- `output/my_song/my_song.fcpxml`
- `output/my_song/prompts.txt`
- `output/my_song/director_settings.json`
- copied scene clips

### Final Cut Pro: Advertisement

1. Fill out [`briefs/ad_project_input.md`](/Users/ben/Git%20Projects/Content-Agents/briefs/ad_project_input.md).
2. Put six clips in `input_scenes/`.
3. Run one of these:

```bash
python3 orchestrate_fcpxml.py \
  --workflow_type advertisement \
  --ad_style brand_spot \
  --brief_file briefs/ad_project_input.md \
  --input_dir input_scenes \
  --project_name output/my_ad
```

Supported ad styles:

- `brand_spot`
- `lifestyle`
- `ugc`

### Final Cut Pro: Manual Music Video JSON Mode

If you want to hand-author scene style, edit [`config/director_settings.json`](/Users/ben/Git%20Projects/Content-Agents/config/director_settings.json) and run:

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

## Outputs

The FCP workflow writes:

- `prompts.txt`
- `director_settings.json`
- copied scene clips
- one `.fcpxml` timeline

Music video prompts include:

- `Shot card`
- `Nano Banana prompt`
- `LTX prompt`

Advertisement prompts include the same structure, but the scene logic is based on product brief sections instead of lyrics.

## Notes

- `director_style_v1.md` was removed because it is no longer used by the scripts.
- The Premiere template logic now lives at [`docs/premiere_xml_logic.md`](/Users/ben/Git%20Projects/Content-Agents/docs/premiere_xml_logic.md).
- For the full walkthrough, use [`docs/GENERATION_GUIDE.md`](/Users/ben/Git%20Projects/Content-Agents/docs/GENERATION_GUIDE.md).
