# Backlog

This file tracks the next workflow expansions for `orchestrate_fcpxml.py`.

## Next Major Workflow: Animated Scene

Goal:

Add a new `animated_scene` workflow that supports multiple kinds of animation, not just cartoon character animation.

Why:

- the current system already supports `music_video` and `advertisement`
- animation is the next natural workflow family
- the same FCPXML/media-copy/output structure can stay in place while the creative generation layer changes

### Animated Scene Subtypes To Support

- `character_animation`
  - stylized characters
  - creature animation
  - anime-inspired or cinematic animated scenes

- `motion_graphics`
  - shape-based design animation
  - graphic transitions
  - bold design compositions

- `kinetic_typography`
  - animated text in the world
  - giant words interacting with real locations
  - example: large letters dropping from the sky onto a bridge

- `composite_fx`
  - graphics composited onto live-action or realistic scenes
  - floating UI
  - surreal overlay effects
  - title elements integrated into the world

- `abstract_animation`
  - non-literal animated visuals
  - texture animation
  - symbolic motion
  - design-first sequences

## Animated Scene Brief Template

Add a new input file:

- `animated_scene_input.md`

Suggested sections:

- `## Concept`
- `## Animation Type`
- `## Characters`
- `## World`
- `## Visual Style`
- `## Scene Arc`
- `## Creative Notes`
- optional `## Visual References`

## Animated Scene Workflow Design

Add:

- `--workflow_type animated_scene`
- `--animation_style character_animation|motion_graphics|kinetic_typography|composite_fx|abstract_animation`

Behavior:

- parse the animated-scene brief
- build six animation scenes
- generate `director_settings.json`
- generate:
  - `Shot card`
  - `Nano Banana prompt`
  - `LTX prompt`
- keep the shared FCPXML/media-copy pipeline

## Prompt Design Goals For Animated Scenes

### Nano Banana Prompt Goals

- describe one visually strong animation frame
- clearly state subject, world, composition, and animation type
- make stylization explicit
- be easier for image generation to interpret than technical design notes

### LTX Prompt Goals

- focus on motion only
- describe how the animated scene moves over 5 seconds
- specify:
  - object motion
  - text motion
  - environment motion
  - camera motion
  - stylization stability

### Kinetic Typography Specific Goals

- support text as a physical object in space
- support giant text integrated into architecture or landscape
- support falling, drifting, colliding, landing, dissolving, or transforming text
- support text interacting with bridges, roads, buildings, sky, water, or city space

## Other Workflow Expansions

### Film Scene Workflow

Possible future workflow:

- `film_scene`

Focus:

- narrative cinematic scenes
- dialogue moments
- tension beats
- realism and blocking
- less music-video styling, less ad structure

Suggested brief sections:

- `## Scene Premise`
- `## Characters`
- `## Setting`
- `## Tone`
- `## Scene Beats`
- `## Creative Notes`

### Creative Scene Workflow

Possible future workflow:

- `creative_scene`

Focus:

- open-ended visual experimentation
- surreal ideas
- symbolic imagery
- concept-first scenes

Suggested brief sections:

- `## Concept`
- `## Theme`
- `## Visual Language`
- `## Mood`
- `## Creative Notes`

## Cross-Workflow Improvements

These improvements should apply across workflows over time:

- clearer workflow-specific guide docs
- one brief template per workflow
- cleaner prompt formatting in `prompts.txt`
- stronger distinction between Nano Banana prompts and LTX prompts
- better per-workflow `director_settings.json` generation
- optional workflow-specific validation in the brief parser
- more reusable prompt builder helpers to reduce logic duplication

## Short-Term Priorities

Recommended order:

1. `animated_scene`
2. `film_scene`
3. `creative_scene`

Within `animated_scene`, recommended order:

1. `kinetic_typography`
2. `motion_graphics`
3. `composite_fx`
4. `character_animation`
5. `abstract_animation`
