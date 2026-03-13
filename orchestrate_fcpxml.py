#!/usr/bin/env python3

import argparse
import json
import math
import re
import subprocess
import shutil
from fractions import Fraction
from pathlib import Path
from typing import NamedTuple
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from orchestrate_premxml import (
    DEFAULT_BARS_PER_SCENE,
    DEFAULT_BEATS_PER_BAR,
    FRAME_HEIGHT,
    FRAME_WIDTH,
    SCENE_COUNT,
    classify_energy,
    load_lyrics,
    split_into_scenes,
)


FCPXML_VERSION = "1.5"
FRAME_DURATION = Fraction(1001, 24000)
EXPECTED_SCENE_FILES = tuple(f"scene_{index:02d}.mp4" for index in range(1, SCENE_COUNT + 1))
DIRECTOR_SETTINGS_PATH = Path(__file__).resolve().parent / "config" / "director_settings.json"
SLOW_BPM_THRESHOLD = 100.0
TARGET_MAX_SCENE_SECONDS = 5.0
FRAME_SECONDS = float(FRAME_DURATION)
ADVERTISEMENT_TARGET_SCENE_SECONDS = 5.0
DEFAULT_SCENE_STYLE = {
    "style": "Cinematic",
    "camera": "tracking shot with confident movement and low-angle framing",
    "lighting": "cinematic lighting with motivated practicals, contrast, and atmospheric haze",
    "palette": "steel blue, tungsten amber, and controlled shadow",
}


class EditTimingSpec(NamedTuple):
    song_bpm: float
    effective_bpm: float
    beats_per_bar: int
    bars_per_scene: float
    beats_per_scene: int
    seconds_per_beat: float
    seconds_per_scene: float
    frames_per_scene: int
    total_frames: int
    uses_double_time: bool


class StoryBlueprint(NamedTuple):
    protagonist: str
    setting: str
    wardrobe: str
    atmosphere: str
    visual_arc: tuple[str, ...]


class AdBrief(NamedTuple):
    product_name: str
    audience: str
    core_problem: str
    value_proposition: str
    offer_cta: str
    creative_notes: str
    visual_references: str


class ScenePromptBundle(NamedTuple):
    source_label: str
    source_text: str
    visual_style: str
    shot_card: str
    nano_prompt: str
    ltx_prompt: str
    extra_lines: tuple[str, ...] = ()


def append_clause(base: str, clause: str) -> str:
    if clause in base:
        return base
    return f"{base}, {clause}"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate prompts and a Final Cut Pro FCPXML timeline for a six-scene content package."
    )
    parser.add_argument(
        "--workflow_type",
        choices=("music_video", "advertisement"),
        default="music_video",
        help="Creative workflow to generate. Default: music_video.",
    )
    parser.add_argument(
        "--ad_style",
        choices=("brand_spot", "lifestyle", "ugc"),
        help="Advertisement sub-style. Required when --workflow_type advertisement.",
    )
    parser.add_argument("--lyrics", help="Raw lyrics text or a path to a text file.")
    parser.add_argument("--bpm", type=float, help="Song tempo in beats per minute.")
    parser.add_argument(
        "--brief_file",
        help="Markdown project brief containing BPM and a Lyrics section for end-to-end generation.",
    )
    parser.add_argument("--project_name", required=True, help="Folder and sequence naming prefix.")
    parser.add_argument(
        "--input_dir",
        required=True,
        help="Folder containing scene_01.mp4 through scene_06.mp4 for the FCPXML timeline.",
    )
    parser.add_argument(
        "--beats_per_bar",
        type=int,
        default=DEFAULT_BEATS_PER_BAR,
        help="Time signature numerator for timing math. Default: 4.",
    )
    parser.add_argument(
        "--bars_per_scene",
        type=int,
        default=DEFAULT_BARS_PER_SCENE,
        help="How many bars each scene should span. Default: 2.",
    )
    return parser.parse_args()


def build_edit_timing_spec(song_bpm: float, beats_per_bar: int, bars_per_scene: int) -> EditTimingSpec:
    uses_double_time = song_bpm < SLOW_BPM_THRESHOLD
    effective_bpm = song_bpm * 2 if uses_double_time else song_bpm
    seconds_per_beat = 60.0 / effective_bpm

    if uses_double_time:
        beats_per_scene = max(1, math.floor(TARGET_MAX_SCENE_SECONDS / seconds_per_beat))
    else:
        beats_per_scene = beats_per_bar * bars_per_scene

    seconds_per_scene = beats_per_scene * seconds_per_beat
    frames_per_scene = round(seconds_per_scene * (24000 / 1001))
    total_frames = frames_per_scene * SCENE_COUNT
    return EditTimingSpec(
        song_bpm=song_bpm,
        effective_bpm=effective_bpm,
        beats_per_bar=beats_per_bar,
        bars_per_scene=beats_per_scene / beats_per_bar,
        beats_per_scene=beats_per_scene,
        seconds_per_beat=seconds_per_beat,
        seconds_per_scene=seconds_per_scene,
        frames_per_scene=frames_per_scene,
        total_frames=total_frames,
        uses_double_time=uses_double_time,
    )


def build_ad_timing_spec() -> EditTimingSpec:
    seconds_per_scene = ADVERTISEMENT_TARGET_SCENE_SECONDS
    frames_per_scene = round(seconds_per_scene * (24000 / 1001))
    total_frames = frames_per_scene * SCENE_COUNT
    return EditTimingSpec(
        song_bpm=0.0,
        effective_bpm=0.0,
        beats_per_bar=0,
        bars_per_scene=0.0,
        beats_per_scene=0,
        seconds_per_beat=0.0,
        seconds_per_scene=seconds_per_scene,
        frames_per_scene=frames_per_scene,
        total_frames=total_frames,
        uses_double_time=False,
    )


def fcpx_time_from_frames(frames: int) -> str:
    value = FRAME_DURATION * frames
    if value.denominator == 1:
        return f"{value.numerator}s"
    return f"{value.numerator}/{value.denominator}s"


def fcpx_time_from_seconds(seconds: float) -> str:
    value = Fraction(seconds).limit_denominator(24000)
    if value.denominator == 1:
        return f"{value.numerator}s"
    return f"{value.numerator}/{value.denominator}s"


def frames_from_seconds_floor(seconds: float) -> int:
    return max(1, math.floor(seconds / FRAME_SECONDS + 1e-9))


def seconds_from_frames(frames: int) -> float:
    return float(FRAME_DURATION * frames)


def extract_markdown_section(text: str, heading: str) -> str:
    pattern = rf"(?ims)^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)"
    match = re.search(pattern, text)
    if not match:
        return ""
    return match.group(1).strip()


def load_project_brief(path: Path) -> tuple[str, float, str]:
    if not path.exists() or not path.is_file():
        raise SystemExit(f"Error: brief file not found: {path}")

    brief_text = path.read_text(encoding="utf-8")
    bpm_match = re.search(r"(?im)^BPM:\s*([0-9]+(?:\.[0-9]+)?)\s*$", brief_text)
    if not bpm_match:
        raise SystemExit(f"Error: {path.name} is missing a 'BPM: <number>' line.")

    lyrics = extract_markdown_section(brief_text, "Lyrics")
    if not lyrics:
        raise SystemExit(f"Error: {path.name} is missing a '## Lyrics' section.")

    creative_notes = extract_markdown_section(brief_text, "Creative Notes")
    return lyrics, float(bpm_match.group(1)), creative_notes


def load_ad_brief(path: Path) -> AdBrief:
    if not path.exists() or not path.is_file():
        raise SystemExit(f"Error: brief file not found: {path}")

    brief_text = path.read_text(encoding="utf-8")

    def required_section(name: str) -> str:
        value = extract_markdown_section(brief_text, name)
        if not value:
            raise SystemExit(f"Error: {path.name} is missing a '## {name}' section.")
        return value

    return AdBrief(
        product_name=clean_text(required_section("Product Name")),
        audience=clean_text(required_section("Audience")),
        core_problem=clean_text(required_section("Core Problem")),
        value_proposition=clean_text(required_section("Value Proposition")),
        offer_cta=clean_text(required_section("Offer Or CTA")),
        creative_notes=required_section("Creative Notes"),
        visual_references=clean_text(extract_markdown_section(brief_text, "Visual References")),
    )


def load_creative_brief(path: Path) -> list[dict]:
    """
    Parse a creative brief file into a list of scene dicts.

    Each ## Scene XX block should contain:
        Name: ...
        Image prompt: ...
        LTX prompt: ...

    Returns a list of dicts with keys: name, image_prompt, ltx_prompt
    """
    if not path.exists() or not path.is_file():
        raise SystemExit(f"Error: brief file not found: {path}")

    text = path.read_text(encoding="utf-8")
    scene_blocks = re.split(r"(?m)^##\s+Scene\s+\d+", text)
    # First element is the Project Notes header — skip it
    scene_blocks = [b.strip() for b in scene_blocks[1:] if b.strip()]

    if not scene_blocks:
        raise SystemExit(f"Error: no Scene blocks found in {path.name}. Add '## Scene 01', '## Scene 02', etc.")

    scenes = []
    for i, block in enumerate(scene_blocks, start=1):
        def field(key: str) -> str:
            match = re.search(rf"(?m)^{key}:\s*(.+?)(?=\n[A-Z]|\Z)", block, re.DOTALL)
            return match.group(1).strip() if match else ""

        image_prompt = field("Image prompt")
        ltx_prompt = field("LTX prompt")
        name = field("Name") or f"Scene {i:02d}"

        if not image_prompt:
            raise SystemExit(f"Error: Scene {i:02d} is missing 'Image prompt:' in {path.name}")
        if not ltx_prompt:
            raise SystemExit(f"Error: Scene {i:02d} is missing 'LTX prompt:' in {path.name}")

        scenes.append({"name": name, "image_prompt": image_prompt, "ltx_prompt": ltx_prompt})

    return scenes


def write_creative_outputs(
    project_name: str,
    brief_file: str,
    scenes: list[dict],
    input_dir: Path,
) -> tuple[Path, Path, list[dict]]:
    """
    Build prompts.txt + FCPXML for a creative brief.
    Uses fixed 5-second scene timing. Auto-copies placeholder clips.
    """
    output_dir = Path(project_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve()
    project_label = output_dir.name

    scene_count = len(scenes)
    timing = build_ad_timing_spec()  # 5s per scene, no BPM needed

    # Auto-create placeholder source clips for each scene
    placeholder = Path(__file__).resolve().parent / "placeholder_master.mp4"
    scene_sources: list[tuple[Path, float]] = []
    for i in range(1, scene_count + 1):
        dest = output_dir / f"scene_{i:02d}.mp4"
        if not dest.exists():
            if placeholder.exists():
                shutil.copyfile(placeholder, dest)
            else:
                raise SystemExit(f"Error: placeholder_master.mp4 not found. Add any .mp4 to the repo root.")
        duration = get_media_duration_seconds(dest)
        scene_sources.append((dest, duration))

    timeline_frame_counts = build_timeline_frame_counts(scene_sources, timing)
    timeline_durations = [seconds_from_frames(fc) for fc in timeline_frame_counts]

    # Write prompts.txt
    prompts_path = output_dir / "prompts.txt"
    prompt_lines = [
        f"Project: {project_label}",
        f"Workflow type: creative",
        f"Scenes: {scene_count}",
        f"Target scene length: {timing.seconds_per_scene:.2f}s",
        f"Brief file: {brief_file}",
        "",
    ]
    for i, (scene, duration) in enumerate(zip(scenes, timeline_durations), start=1):
        prompt_lines.append(f"[Scene {i:02d}]")
        prompt_lines.append(f"Name: {scene['name']}")
        prompt_lines.append(f"Timeline duration: {duration:.2f}s")
        prompt_lines.append(f"Image prompt: {scene['image_prompt']}")
        prompt_lines.append(f"LTX prompt: {scene['ltx_prompt']}")
        prompt_lines.append("")
    prompts_path.write_text("\n".join(prompt_lines).rstrip() + "\n", encoding="utf-8")

    # Build FCPXML with a temporary override scene count
    fcpxml_path = output_dir / f"{project_label}.fcpxml"
    fcpxml_path.write_text(
        build_fcpxml(project_label, output_dir, timing, scene_sources, timeline_frame_counts),
        encoding="utf-8",
    )

    bundle_dicts = [
        {
            "scene_id": f"scene_{i:02d}",
            "image_prompt": scene["image_prompt"],
            "video_prompt": scene["ltx_prompt"],
            "duration": timeline_durations[i - 1],
            "style_tag": scene["name"],
        }
        for i, scene in enumerate(scenes, start=1)
    ]
    return prompts_path, fcpxml_path, bundle_dicts


def resolve_music_video_inputs(args: argparse.Namespace) -> tuple[str, float, str]:
    if args.brief_file:
        return load_project_brief(Path(args.brief_file))

    if not args.lyrics:
        raise SystemExit("Error: provide --lyrics or --brief_file.")
    if args.bpm is None:
        raise SystemExit("Error: provide --bpm or use --brief_file with a BPM line.")

    return load_lyrics(args.lyrics), args.bpm, ""


def load_director_settings() -> list[dict[str, str]]:
    if not DIRECTOR_SETTINGS_PATH.exists():
        raise SystemExit(f"Error: missing director settings file: {DIRECTOR_SETTINGS_PATH}")

    try:
        payload = json.loads(DIRECTOR_SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Error: invalid JSON in {DIRECTOR_SETTINGS_PATH.name}: {exc}") from exc

    if not isinstance(payload, list):
        raise SystemExit(f"Error: {DIRECTOR_SETTINGS_PATH.name} must contain a JSON array.")

    normalized: list[dict[str, str]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            normalized.append(DEFAULT_SCENE_STYLE.copy())
            continue

        normalized.append(
            {
                "style": str(entry.get("style", DEFAULT_SCENE_STYLE["style"])).strip()
                or DEFAULT_SCENE_STYLE["style"],
                "camera": str(entry.get("camera", DEFAULT_SCENE_STYLE["camera"])).strip()
                or DEFAULT_SCENE_STYLE["camera"],
                "lighting": str(entry.get("lighting", DEFAULT_SCENE_STYLE["lighting"])).strip()
                or DEFAULT_SCENE_STYLE["lighting"],
                "palette": str(entry.get("palette", DEFAULT_SCENE_STYLE["palette"])).strip()
                or DEFAULT_SCENE_STYLE["palette"],
            }
        )
    return normalized


def get_scene_style(scene_number: int, director_settings: list[dict[str, str]]) -> dict[str, str]:
    if 1 <= scene_number <= len(director_settings):
        return director_settings[scene_number - 1]
    return DEFAULT_SCENE_STYLE.copy()


def apply_creative_notes(scene_style: dict[str, str], creative_notes: str) -> dict[str, str]:
    notes = creative_notes.lower()
    style = scene_style.copy()

    if any(word in notes for word in ("wet", "rain", "reflection", "reflections")):
        style["lighting"] = append_clause(
            style["lighting"],
            "wet reflective highlights and backlit surface sheen",
        )
        style["palette"] = append_clause(style["palette"], "mirror-like chrome reflections")
    if any(word in notes for word in ("haze", "smoke", "fog", "atmosphere")):
        style["lighting"] = append_clause(
            style["lighting"],
            "heavy atmospheric haze with volumetric depth",
        )
    if any(word in notes for word in ("practical", "neon", "glow")):
        style["lighting"] = append_clause(
            style["lighting"],
            "motivated practicals and visible glow sources",
        )
    if any(word in notes for word in ("high-motion", "kinetic", "fast", "aggressive")):
        style["camera"] = append_clause(
            style["camera"],
            "kinetic editorial motion and hard rhythmic movement",
        )
    if any(word in notes for word in ("handheld", "gritty", "raw")):
        style["camera"] = append_clause(
            style["camera"],
            "controlled handheld instability",
        )
    if any(word in notes for word in ("luxury", "premium", "expensive", "polished")):
        style["style"] = f"Premium {style['style']}"
        style["palette"] = append_clause(
            style["palette"],
            "polished premium finish",
        )
    if any(word in notes for word in ("dark", "noir", "shadow")):
        style["lighting"] = append_clause(
            style["lighting"],
            "deep shadow falloff and noir contrast",
        )
    if any(word in notes for word in ("warm", "gold", "amber")):
        style["palette"] = append_clause(style["palette"], "warm amber highlights")
    if any(word in notes for word in ("cool", "blue", "cyan")):
        style["palette"] = append_clause(style["palette"], "cool cyan accents")

    return style


def infer_story_blueprint(lyrics: str, creative_notes: str) -> StoryBlueprint:
    combined = f"{lyrics}\n{creative_notes}".lower()

    if any(word in combined for word in ("apartment", "bedroom", "hallway", "window", "room")):
        setting = "a sleek high-rise apartment at night with long hallways, a bedroom, and a wide city window"
    elif any(word in combined for word in ("car", "street", "city")):
        setting = "a moody night cityscape with a luxury car, wet streets, and isolated interior spaces"
    else:
        setting = "a stylish night interior with polished shadows, soft practical lights, and city glow outside"

    if any(word in combined for word in ("jewelry", "fabric", "premium", "expensive", "luxury", "polished")):
        wardrobe = "tailored dark street-luxury wardrobe, layered jewelry, clean textures, understated expensive details"
    else:
        wardrobe = "clean dark wardrobe with subtle jewelry and refined streetwear textures"

    atmosphere_parts = []
    if any(word in combined for word in ("haze", "smoke", "fog", "atmosphere")):
        atmosphere_parts.append("soft haze hanging in the room")
    if any(word in combined for word in ("wet", "rain", "reflection", "reflections", "glass")):
        atmosphere_parts.append("glass reflections and wet reflective highlights")
    if any(word in combined for word in ("lamp", "practical", "neon", "glow")):
        atmosphere_parts.append("warm practical lamps and subtle neon spill")
    if any(word in combined for word in ("night", "late-night", "nocturnal")):
        atmosphere_parts.append("late-night stillness")
    atmosphere = ", ".join(atmosphere_parts) or "quiet late-night air and polished shadow"

    protagonist = "the same R&B / hip-hop artist in every scene, calm, reflective, and finally able to breathe"
    visual_arc = (
        "boxed-in pressure",
        "private unraveling",
        "recognizing the weight",
        "making peace with the ending",
        "feeling the room open up",
        "stepping into relief",
    )
    return StoryBlueprint(
        protagonist=protagonist,
        setting=setting,
        wardrobe=wardrobe,
        atmosphere=atmosphere,
        visual_arc=visual_arc,
    )


def infer_subject_action(scene_text: str, scene_number: int) -> str:
    lowered = scene_text.lower()
    if any(word in lowered for word in ("autopilot", "numb", "swallowed", "peace")):
        return "sitting on the edge of the bed, staring into space with tension locked in his shoulders"
    if any(word in lowered for word in ("match your mood", "flaw", "normal", "calm")):
        return "walking slowly down a narrow hallway, brushing a hand along the wall as if carrying old pressure"
    if any(word in lowered for word in ("room got bigger", "lighter", "miss who i was")):
        return "standing in front of a mirror, catching his own reflection as relief starts to replace doubt"
    if any(word in lowered for word in ("exhaled", "moving too fast", "mean different")):
        return "leaning by the open window, looking over the city as he finally exhales and lets the moment settle"
    if any(word in lowered for word in ("nights", "spirals", "holding my breath")):
        return "crossing the room alone at night, calm now, with the space around him finally feeling open"
    if any(word in lowered for word in ("space feels like", "took it sooner")):
        return "stepping toward the doorway or window light, choosing peace with quiet certainty"
    if scene_number == 1:
        return "sitting alone in a dim room before speaking the truth to himself"
    if scene_number == 6:
        return "walking toward open space with a lighter expression"
    return "moving through the room in a quiet reflective moment"


def infer_scene_anchor(scene_text: str, scene_number: int, blueprint: StoryBlueprint) -> str:
    lowered = scene_text.lower()
    if any(word in lowered for word in ("mirror", "reflection", "who i was")):
        return "a fogged mirror catching both his face and the city lights behind him"
    if any(word in lowered for word in ("room got bigger", "lighter", "space")):
        return "an empty section of the apartment suddenly feeling larger around him"
    if any(word in lowered for word in ("night", "spirals", "sleep")):
        return "the dark bedroom and the soft lamp glow that no longer feels threatening"
    if any(word in lowered for word in ("exhaled", "window", "bigger")):
        return "the open window and the skyline breathing back at him"
    if scene_number in (2, 5):
        return "the apartment hallway stretching behind him in clean perspective"
    return "the apartment room, city glow, and quiet late-night air"


def build_shot_card(
    scene_text: str,
    scene_number: int,
    blueprint: StoryBlueprint,
    scene_style: dict[str, str],
) -> str:
    action = infer_subject_action(scene_text, scene_number)
    anchor = infer_scene_anchor(scene_text, scene_number, blueprint)
    arc_label = blueprint.visual_arc[min(scene_number - 1, len(blueprint.visual_arc) - 1)]
    return (
        f"{arc_label.title()}: {action}, using {anchor}, shaped by {scene_style['style'].lower()} mood."
    )


def build_nano_banana_prompt(
    scene_text: str,
    scene_number: int,
    blueprint: StoryBlueprint,
    scene_style: dict[str, str],
    timeline_duration: float,
) -> str:
    action = infer_subject_action(scene_text, scene_number)
    emotion = blueprint.visual_arc[min(scene_number - 1, len(blueprint.visual_arc) - 1)]
    return (
        f"Cinematic still frame. R&B music video. "
        f"{blueprint.protagonist}, inside {blueprint.setting}, {action}. "
        f"Lighting: {scene_style['lighting']}. "
        f"Color palette: {scene_style['palette']}. "
        f"Mood: {emotion}. "
        f"No text, no logos, no crowd."
    )


def infer_motion_phrase(scene_text: str, scene_number: int) -> str:
    lowered = scene_text.lower()
    if any(word in lowered for word in ("autopilot", "numb", "swallowed", "peace")):
        return "the artist breathes slowly, lowers his gaze, and subtly shifts forward as if carrying invisible weight"
    if any(word in lowered for word in ("match your mood", "flaw", "normal", "calm")):
        return "he moves down the hallway with a slow measured walk, fingers grazing the wall, shoulders gradually releasing tension"
    if any(word in lowered for word in ("room got bigger", "lighter", "miss who i was")):
        return "he studies his reflection, lifts his chin slightly, and lets the expression soften as recognition lands"
    if any(word in lowered for word in ("night", "spirals", "holding my breath")):
        return "he crosses the room with unhurried confidence, then settles into stillness as the air around him feels lighter"
    if any(word in lowered for word in ("exhaled", "mean different", "moving too fast")):
        return "he leans into the open window light and exhales, letting the body loosen as the city glow flickers behind him"
    if any(word in lowered for word in ("space feels like", "took it sooner")):
        return "he steps toward the open space, pauses, and lets the final moment land with quiet certainty"
    if scene_number == 1:
        return "he holds still, breathes, and subtly tightens then releases his shoulders"
    if scene_number == 6:
        return "he steps forward with calm, deliberate movement and a lighter expression"
    return "the artist makes a subtle grounded movement that reveals emotional release"


def infer_environment_motion(scene_text: str, blueprint: StoryBlueprint) -> str:
    atmosphere = blueprint.atmosphere.lower()
    motions = []
    if "haze" in atmosphere:
        motions.append("soft haze drifting through the light")
    if "reflection" in atmosphere:
        motions.append("reflections shimmering across glass and polished surfaces")
    if "lamp" in atmosphere or "neon" in atmosphere:
        motions.append("practical lights glowing steadily with subtle flicker")
    if not motions:
        motions.append("gentle ambient movement in the room")
    return ", ".join(motions)


def build_ltx_motion_prompt(
    scene_text: str,
    scene_number: int,
    blueprint: StoryBlueprint,
    scene_style: dict[str, str],
    timeline_duration: float,
) -> str:
    motion_phrase = infer_motion_phrase(scene_text, scene_number)
    return (
        f"{timeline_duration:.2f}-second cinematic shot. "
        f"Camera: {scene_style['camera']}. "
        f"Subject: {motion_phrase}. "
        f"Mood: nocturnal, intimate, emotionally relieved. "
        f"No warping, no morphing, no face drift, no text."
    )


def get_ad_scene_plan(ad_style: str, brief: AdBrief) -> list[tuple[str, str]]:
    if ad_style == "brand_spot":
        return [
            ("Hook", f"Open with the product in a high-impact hero moment that immediately signals {brief.value_proposition}."),
            ("Problem", f"Show the frustration of {brief.core_problem} in a polished, relatable way."),
            ("Reveal", f"Introduce {brief.product_name} as the elegant solution."),
            ("Benefit", f"Demonstrate the strongest visual benefit for {brief.audience}."),
            ("Proof", "Show the product looking premium, trustworthy, and desirable in use."),
            ("CTA", f"End on a clean product hero plus offer or CTA: {brief.offer_cta}."),
        ]
    if ad_style == "lifestyle":
        return [
            ("Mood Hook", f"Open inside an aspirational lifestyle moment that instantly attracts {brief.audience}."),
            ("Pain Point", f"Reveal how {brief.core_problem} quietly affects everyday life."),
            ("Discovery", f"Show {brief.product_name} entering the moment naturally."),
            ("Use Case", f"Capture the product being used in a beautiful everyday setting with {brief.value_proposition}."),
            ("Emotional Payoff", "Show how life feels easier, calmer, or better after using the product."),
            ("CTA", f"Close with a soft but clear brand or offer moment: {brief.offer_cta}."),
        ]
    return [
        ("Scroll Stop", f"Open with a direct-to-camera hook about {brief.core_problem}."),
        ("Relatable Problem", f"Show a casual, honest moment where the audience feels the problem."),
        ("Product Intro", f"Bring in {brief.product_name} like a real recommendation from a creator."),
        ("Demo", f"Show a hands-on demo of the value proposition: {brief.value_proposition}."),
        ("Result", "Show believable improvement and a natural reaction shot."),
        ("CTA", f"End with a simple spoken-style call to action: {brief.offer_cta}."),
    ]


def infer_ad_scene_style(ad_style: str, scene_number: int, brief: AdBrief) -> dict[str, str]:
    notes = brief.creative_notes.lower()
    if ad_style == "brand_spot":
        styles = (
            {"style": "Hero Product Intro", "camera": "controlled cinematic push-in with premium product framing", "lighting": "high-contrast commercial lighting with polished specular highlights", "palette": "clean premium brand tones with crisp contrast"},
            {"style": "Problem Tension", "camera": "composed medium shot with subtle dolly tension", "lighting": "soft practical light with controlled shadow and discomfort", "palette": "muted neutrals with slight cool cast"},
            {"style": "Solution Reveal", "camera": "precise beauty-shot movement that lands on the product", "lighting": "glossy reveal lighting with refined edge light", "palette": "brand-led polished color harmony"},
            {"style": "Benefit Demo", "camera": "confident tracking move around hands, product, and user interaction", "lighting": "clean bright commercial lighting with tactile detail", "palette": "fresh premium tones with visual clarity"},
            {"style": "Trust Builder", "camera": "steady cinematic close framing with elegant lifestyle motion", "lighting": "premium naturalistic glow with shape and dimension", "palette": "rich neutrals with soft accent colors"},
            {"style": "CTA Hero", "camera": "hero angle with clean locked composition and slight push-in", "lighting": "brand hero lighting with polished shine", "palette": "sharp brand palette with premium finish"},
        )
    elif ad_style == "lifestyle":
        styles = (
            {"style": "Aspirational Hook", "camera": "gentle floating dolly with intimate lifestyle framing", "lighting": "soft golden practical light with natural texture", "palette": "warm neutrals with refined accent color"},
            {"style": "Quiet Friction", "camera": "observational handheld-light drift with natural framing", "lighting": "real-world interior lighting with slight softness", "palette": "calm lived-in tones"},
            {"style": "Natural Discovery", "camera": "slow reveal move that notices the product inside the moment", "lighting": "inviting natural light with subtle glow", "palette": "organic warm-to-cool balance"},
            {"style": "Use Moment", "camera": "smooth side tracking shot focused on product in use", "lighting": "soft practical and window light working together", "palette": "clean lifestyle color story"},
            {"style": "Emotional Payoff", "camera": "close intimate framing with relaxed motion", "lighting": "comfortable ambient light with flattering skin tones", "palette": "warm soft neutrals"},
            {"style": "Lifestyle CTA", "camera": "simple confident brand close with elegant drift", "lighting": "clean natural-commercial blend", "palette": "brand-aligned soft finish"},
        )
    else:
        styles = (
            {"style": "UGC Hook", "camera": "direct-to-camera phone-style framing with subtle handheld realism", "lighting": "natural room light with believable creator setup", "palette": "casual real-life tones"},
            {"style": "Problem Confession", "camera": "self-shot medium close-up with quick conversational energy", "lighting": "honest indoor practical light", "palette": "real everyday color"},
            {"style": "Recommendation Intro", "camera": "casual desk or bathroom counter demo framing", "lighting": "clean creator light with natural falloff", "palette": "simple product-friendly tones"},
            {"style": "Hands-On Demo", "camera": "close framing on hands and product interaction", "lighting": "bright readable demo lighting", "palette": "clear, functional, product-first color"},
            {"style": "Result Reaction", "camera": "selfie or close reaction framing with authentic movement", "lighting": "friendly natural glow", "palette": "relatable lifestyle tones"},
            {"style": "UGC CTA", "camera": "straight-to-camera closer with confident creator energy", "lighting": "simple direct lighting with clean readability", "palette": "light brand-aware finish"},
        )
    style = styles[min(scene_number - 1, len(styles) - 1)].copy()
    return apply_creative_notes(style, notes)


def build_ad_story_blueprint(ad_style: str, brief: AdBrief) -> StoryBlueprint:
    if ad_style == "brand_spot":
        protagonist = f"{brief.product_name} and polished commercial talent representing {brief.audience}"
        setting = "a clean premium commercial environment designed around the product"
        wardrobe = "brand-appropriate polished wardrobe and premium styling"
        atmosphere = "controlled commercial lighting, clean surfaces, premium product texture"
        visual_arc = ("hook", "problem", "reveal", "benefit", "proof", "cta")
    elif ad_style == "lifestyle":
        protagonist = f"an aspirational version of {brief.audience} using {brief.product_name} naturally"
        setting = "a stylish lived-in environment where the product fits naturally into daily life"
        wardrobe = "effortless elevated lifestyle wardrobe with believable premium detail"
        atmosphere = "soft natural light, calm texture, attractive everyday realism"
        visual_arc = ("aspiration", "friction", "discovery", "use", "payoff", "cta")
    else:
        protagonist = f"a relatable creator speaking directly to {brief.audience} about {brief.product_name}"
        setting = "a believable creator space like a bedroom, desk setup, vanity, kitchen, or car"
        wardrobe = "casual creator wardrobe with natural styling"
        atmosphere = "real-world lighting, social-native framing, conversational energy"
        visual_arc = ("scroll stop", "relatability", "recommendation", "demo", "result", "cta")
    return StoryBlueprint(protagonist, setting, wardrobe, atmosphere, visual_arc)


def build_ad_scene_bundle(
    ad_style: str,
    scene_number: int,
    brief: AdBrief,
    blueprint: StoryBlueprint,
    scene_style: dict[str, str],
    timeline_duration: float,
) -> ScenePromptBundle:
    role, goal = get_ad_scene_plan(ad_style, brief)[scene_number - 1]
    shot_card = f"{role}: {goal}"
    if ad_style == "ugc":
        nano_prompt = (
            f"A single strong frame from a {timeline_duration:.2f}-second UGC-style advertisement scene. "
            f"{blueprint.protagonist} inside {blueprint.setting}. "
            f"The visual goal is: {goal} "
            f"Product focus: {brief.product_name}. Audience: {brief.audience}. "
            f"Core problem: {brief.core_problem}. Value proposition: {brief.value_proposition}. "
            f"Lighting: {scene_style['lighting']}. Color palette: {scene_style['palette']}. Camera angle: {scene_style['camera']}. "
            f"Real, social-native, believable, easy for an image model to interpret. No text overlays, no logos burned in."
        )
        ltx_prompt = (
            f"{timeline_duration:.2f}-second UGC ad shot. Start from the generated image and animate it naturally. "
            f"Camera motion: {scene_style['camera']}. "
            f"Subject motion: subtle direct-to-camera creator movement, natural hand gestures, believable demo motion. "
            f"Environment motion: small natural room movement and realistic handheld energy. "
            f"Keep it authentic, readable, and conversion-focused. No warping, no flicker, no morphing, no extra limbs, no text."
        )
    else:
        nano_prompt = (
            f"A single strong frame from a {timeline_duration:.2f}-second advertisement scene. "
            f"{blueprint.protagonist} inside {blueprint.setting}. "
            f"The visual goal is: {goal} "
            f"Product focus: {brief.product_name}. Audience: {brief.audience}. "
            f"Core problem: {brief.core_problem}. Value proposition: {brief.value_proposition}. Offer or CTA: {brief.offer_cta}. "
            f"Wardrobe: {blueprint.wardrobe}. Atmosphere: {blueprint.atmosphere}. "
            f"Lighting: {scene_style['lighting']}. Color palette: {scene_style['palette']}. Camera angle: {scene_style['camera']}. "
            f"Make it visually specific, commercial, polished, and easy for an image model to interpret. No text overlays, no logos burned in."
        )
        ltx_prompt = (
            f"{timeline_duration:.2f}-second cinematic advertisement shot. Start from the generated image and animate it naturally. "
            f"Camera motion: {scene_style['camera']}. "
            f"Subject motion: subtle product interaction, natural body movement, expressive but controlled action that sells the benefit. "
            f"Environment motion: premium ambient motion that supports the product and setting. "
            f"Keep it clean, readable, and commercially useful. No warping, no flicker, no morphing, no extra limbs, no text."
        )
    return ScenePromptBundle(
        source_label="Scene goal",
        source_text=goal,
        visual_style=scene_style["style"],
        shot_card=shot_card,
        nano_prompt=nano_prompt,
        ltx_prompt=ltx_prompt,
        extra_lines=(
            f"Ad role: {role}",
            f"Product: {brief.product_name}",
            f"Audience: {brief.audience}",
        ),
    )


def build_music_scene_bundle(
    scene_text: str,
    scene_number: int,
    bpm: float,
    timing: EditTimingSpec,
    blueprint: StoryBlueprint,
    scene_style: dict[str, str],
    timeline_duration: float,
) -> ScenePromptBundle:
    beat_start = (scene_number - 1) * timing.beats_per_scene
    beat_end = scene_number * timing.beats_per_scene
    bar_start = (scene_number - 1) * timing.bars_per_scene + 1
    bar_end = scene_number * timing.bars_per_scene
    return ScenePromptBundle(
        source_label="Lyric chunk",
        source_text=scene_text,
        visual_style=scene_style["style"],
        shot_card=build_shot_card(scene_text, scene_number, blueprint, scene_style),
        nano_prompt=build_nano_banana_prompt(
            scene_text,
            scene_number,
            blueprint,
            scene_style,
            timeline_duration,
        ),
        ltx_prompt=build_ltx_motion_prompt(
            scene_text,
            scene_number,
            blueprint,
            scene_style,
            timeline_duration,
        ),
        extra_lines=(
            f"Bar window: {bar_start:.2f} -> {bar_end:.2f}",
            f"Beat window: {beat_start:.2f} -> {beat_end:.2f}",
        ),
    )


def auto_style_for_scene(scene_text: str, scene_number: int, creative_notes: str) -> dict[str, str]:
    energy = classify_energy(scene_text)
    lowered = scene_text.lower()
    notes = creative_notes.lower()

    if energy == "feral, explosive movement":
        style = {
            "style": "Impact Drive",
            "camera": "aggressive tracking shot with low-angle pressure, fast lateral motion, and whip-pan resets",
            "lighting": "hard backlight through haze, flashing practicals, and sharp silhouette edges",
            "palette": "molten amber, electric cyan, and carbon black",
        }
        return apply_creative_notes(style, creative_notes)
    if energy == "moody, nocturnal drift":
        style = {
            "style": "Night Pulse",
            "camera": "slow stalking tracking shot with lens-close movement and compressed framing",
            "lighting": "low-key practical lighting with selective pools of glow in heavy atmosphere",
            "palette": "midnight blue, deep crimson, and silver highlights",
        }
        return apply_creative_notes(style, creative_notes)
    if energy == "intimate, romantic intensity":
        style = {
            "style": "Velvet Intensity",
            "camera": "gliding tracking shot with intimate low angles and tight emotional framing",
            "lighting": "soft practical bloom, glossy skin highlights, and controlled shadow falloff",
            "palette": "rose red, warm gold, and midnight plum",
        }
        return apply_creative_notes(style, creative_notes)
    if energy == "uplifting, expansive lift" or any(word in lowered for word in ("glow", "higher", "sky", "light")):
        style = {
            "style": "Neon Rise",
            "camera": "floating tracking shot with crane-like lift and expansive low-angle reveals",
            "lighting": "radiant neon spill, volumetric beams, and polished reflective highlights",
            "palette": "electric blue, sodium gold, and magenta haze",
        }
        return apply_creative_notes(style, creative_notes)
    if "rain" in notes or "wet" in notes:
        style = {
            "style": "Rain Cinema",
            "camera": "driving tracking shot with dolly pressure and street-level low-angle movement",
            "lighting": "wet practical reflections, backlit rain streaks, and atmospheric contrast",
            "palette": "steel blue, sodium amber, and gunmetal black",
        }
        return apply_creative_notes(style, creative_notes)
    style = {
        "style": f"Cinematic Scene {scene_number:02d}",
        "camera": DEFAULT_SCENE_STYLE["camera"],
        "lighting": DEFAULT_SCENE_STYLE["lighting"],
        "palette": DEFAULT_SCENE_STYLE["palette"],
    }
    return apply_creative_notes(style, creative_notes)


def build_auto_director_settings(scenes: list[str], creative_notes: str) -> list[dict[str, str]]:
    return [
        auto_style_for_scene(scene_text, scene_number, creative_notes)
        for scene_number, scene_text in enumerate(scenes, start=1)
    ]


def write_director_settings(output_dir: Path, director_settings: list[dict[str, str]]) -> Path:
    output_path = output_dir / "director_settings.json"
    output_path.write_text(json.dumps(director_settings, indent=2) + "\n", encoding="utf-8")
    return output_path


def get_media_duration_seconds(path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("Error: ffprobe is required to inspect source clip durations.") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or "unknown ffprobe error"
        raise SystemExit(f"Error: could not inspect duration for {path.name}: {message}") from exc

    try:
        payload = json.loads(result.stdout)
        duration = float(payload["format"]["duration"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Error: ffprobe returned an unreadable duration for {path.name}.") from exc

    if duration <= 0:
        raise SystemExit(f"Error: {path.name} has a non-positive duration.")
    return duration


def validate_input_scenes(input_dir: Path, timing: EditTimingSpec) -> list[tuple[Path, float]]:
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Error: input directory not found: {input_dir}")

    scene_sources: list[tuple[Path, float]] = []
    for file_name in EXPECTED_SCENE_FILES:
        scene_path = input_dir / file_name
        if not scene_path.exists() or not scene_path.is_file():
            raise SystemExit(f"Error: missing required input clip: {scene_path}")

        duration_seconds = get_media_duration_seconds(scene_path)
        scene_sources.append((scene_path, duration_seconds))

    return scene_sources


def build_timeline_frame_counts(
    scene_sources: list[tuple[Path, float]],
    timing: EditTimingSpec,
) -> list[int]:
    return [
        min(frames_from_seconds_floor(source_duration), timing.frames_per_scene)
        for _path, source_duration in scene_sources
    ]


def build_fcpxml(
    project_label: str,
    output_dir: Path,
    timing: EditTimingSpec,
    scene_sources: list[tuple[Path, float]],
    timeline_frame_counts: list[int],
) -> str:
    fcpxml = Element("fcpxml", version=FCPXML_VERSION)
    resources = SubElement(fcpxml, "resources")
    SubElement(
        resources,
        "format",
        id="r1",
        name="FFVideoFormat720p2398",
        frameDuration=str(fcpx_time_from_frames(1)),
        width=str(FRAME_WIDTH),
        height=str(FRAME_HEIGHT),
        fieldOrder="progressive",
    )

    for index, (_, source_duration) in enumerate(scene_sources, start=1):
        clip_id = f"scene_{index:02d}"
        scene_path = (output_dir / f"{clip_id}.mp4").resolve().as_uri()
        SubElement(
            resources,
            "asset",
            id=f"r{index + 1}",
            name=f"{clip_id}.mp4",
            src=scene_path,
            start="0s",
            duration=fcpx_time_from_seconds(source_duration),
            hasVideo="1",
            hasAudio="1",
            format="r1",
            audioSources="1",
            audioChannels="2",
            audioRate="48k",
        )

    library = SubElement(fcpxml, "library")
    event = SubElement(library, "event", name=f"{project_label} Event")
    project = SubElement(event, "project", name=project_label)
    total_timeline_frames = sum(timeline_frame_counts)
    sequence = SubElement(
        project,
        "sequence",
        format="r1",
        duration=fcpx_time_from_frames(total_timeline_frames),
        tcStart="0s",
        tcFormat="NDF",
        audioLayout="stereo",
        audioRate="48k",
    )
    spine = SubElement(sequence, "spine")

    offset_frames = 0
    for index, (_scene_source, timeline_frames) in enumerate(zip(scene_sources, timeline_frame_counts), start=1):
        clip_id = f"scene_{index:02d}"
        offset = fcpx_time_from_frames(offset_frames)
        SubElement(
            spine,
            "video",
            ref=f"r{index + 1}",
            name=f"{clip_id}.mp4",
            offset=offset,
            start="0s",
            duration=fcpx_time_from_frames(timeline_frames),
        )
        offset_frames += timeline_frames

    pretty = minidom.parseString(tostring(fcpxml, encoding="utf-8")).toprettyxml(indent="  ")
    return "\n".join(line for line in pretty.splitlines() if line.strip())


def write_outputs(
    workflow_type: str,
    ad_style: str,
    project_name: str,
    bpm: float,
    primary_text: str,
    timing: EditTimingSpec,
    input_dir: Path,
    brief_file: str,
    creative_notes: str,
    ad_brief: AdBrief | None = None,
) -> tuple[Path, Path, list[dict]]:
    output_dir = Path(project_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve()
    project_label = output_dir.name
    scene_bundles: list[ScenePromptBundle]

    if workflow_type == "music_video":
        scenes = split_into_scenes(primary_text, SCENE_COUNT)
        blueprint = infer_story_blueprint(primary_text, creative_notes)
        if brief_file:
            director_settings = build_auto_director_settings(scenes, creative_notes)
            director_settings_path = write_director_settings(output_dir, director_settings)
        else:
            director_settings = load_director_settings()
            director_settings_path = DIRECTOR_SETTINGS_PATH.resolve()
        workflow_metadata = [
            f"Workflow type: {workflow_type}",
            f"Song BPM: {bpm:.2f}",
            f"Edit BPM: {timing.effective_bpm:.2f}",
            f"Double-time timing: {'yes' if timing.uses_double_time else 'no'}",
            f"Time signature: {timing.beats_per_bar}/4",
            f"Bars per scene: {timing.bars_per_scene:.2f}",
            f"Beats per scene: {timing.beats_per_scene}",
            f"Target scene length: {timing.seconds_per_scene:.2f}s",
            f"Target max scene length: {TARGET_MAX_SCENE_SECONDS:.2f}s",
            f"Story protagonist: {blueprint.protagonist}",
            f"Story setting: {blueprint.setting}",
            f"Story wardrobe: {blueprint.wardrobe}",
            f"Story atmosphere: {blueprint.atmosphere}",
            f"Visual arc: {' | '.join(blueprint.visual_arc)}",
        ]
    else:
        if ad_brief is None:
            raise SystemExit("Error: advertisement workflow requires an ad brief.")
        scenes = [goal for _role, goal in get_ad_scene_plan(ad_style, ad_brief)]
        blueprint = build_ad_story_blueprint(ad_style, ad_brief)
        director_settings = [
            infer_ad_scene_style(ad_style, scene_number, ad_brief)
            for scene_number in range(1, SCENE_COUNT + 1)
        ]
        director_settings_path = write_director_settings(output_dir, director_settings)
        workflow_metadata = [
            f"Workflow type: {workflow_type}",
            f"Ad style: {ad_style}",
            f"Target scene length: {timing.seconds_per_scene:.2f}s",
            f"Product: {ad_brief.product_name}",
            f"Audience: {ad_brief.audience}",
            f"Core problem: {ad_brief.core_problem}",
            f"Value proposition: {ad_brief.value_proposition}",
            f"Offer or CTA: {ad_brief.offer_cta}",
            f"Story protagonist: {blueprint.protagonist}",
            f"Story setting: {blueprint.setting}",
            f"Story wardrobe: {blueprint.wardrobe}",
            f"Story atmosphere: {blueprint.atmosphere}",
            f"Visual arc: {' | '.join(blueprint.visual_arc)}",
            f"Visual references: {ad_brief.visual_references or 'none'}",
        ]

    scene_sources = validate_input_scenes(input_dir.resolve(), timing)
    timeline_frame_counts = build_timeline_frame_counts(scene_sources, timing)
    timeline_durations = [seconds_from_frames(frame_count) for frame_count in timeline_frame_counts]
    prompts_path = output_dir / "prompts.txt"
    fcpxml_path = output_dir / f"{project_label}.fcpxml"

    for index, (source_path, _source_duration) in enumerate(scene_sources, start=1):
        scene_path = output_dir / f"scene_{index:02d}.mp4"
        shutil.copyfile(source_path, scene_path)

    if workflow_type == "music_video":
        scene_bundles = [
            build_music_scene_bundle(
                scene_text,
                index,
                bpm,
                timing,
                blueprint,
                get_scene_style(index, director_settings),
                timeline_durations[index - 1],
            )
            for index, scene_text in enumerate(scenes, start=1)
        ]
    else:
        scene_bundles = [
            build_ad_scene_bundle(
                ad_style,
                index,
                ad_brief,
                blueprint,
                get_scene_style(index, director_settings),
                timeline_durations[index - 1],
            )
            for index in range(1, SCENE_COUNT + 1)
        ]

    prompt_lines = [
        f"Project: {project_label}",
        *workflow_metadata,
        f"Frames per scene: {timing.frames_per_scene}",
        f"Actual timeline length: {sum(timeline_durations):.2f}s",
        f"Input directory: {input_dir.resolve()}",
        f"Timeline type: FCPXML {FCPXML_VERSION}",
        f"Director settings: {director_settings_path}",
        f"Brief file: {brief_file or 'manual CLI inputs'}",
        "",
    ]

    for index, bundle in enumerate(scene_bundles, start=1):
        source_duration = scene_sources[index - 1][1]
        timeline_duration = timeline_durations[index - 1]
        prompt_lines.append(f"[Scene {index:02d}]")
        prompt_lines.append(f"{bundle.source_label}: {bundle.source_text}")
        prompt_lines.append(f"Source clip: {scene_sources[index - 1][0].name}")
        prompt_lines.append(f"Source duration: {source_duration:.2f}s")
        prompt_lines.append(f"Timeline duration used: {timeline_duration:.2f}s")
        prompt_lines.append(f"Visual style: {bundle.visual_style}")
        prompt_lines.extend(bundle.extra_lines)
        prompt_lines.append(f"Shot card: {bundle.shot_card}")
        prompt_lines.append(f"Nano Banana prompt: {bundle.nano_prompt}")
        prompt_lines.append(f"LTX prompt: {bundle.ltx_prompt}")
        prompt_lines.append("")

    prompts_path.write_text("\n".join(prompt_lines).rstrip() + "\n", encoding="utf-8")
    fcpxml_path.write_text(
        build_fcpxml(project_label, output_dir, timing, scene_sources, timeline_frame_counts),
        encoding="utf-8",
    )
    bundle_dicts: list[dict] = [
        {
            "scene_id": f"scene_{index:02d}",
            "image_prompt": bundle.nano_prompt,
            "video_prompt": bundle.ltx_prompt,
            "duration": timeline_durations[index - 1],
            "style_tag": bundle.visual_style,
        }
        for index, bundle in enumerate(scene_bundles, start=1)
    ]
    return prompts_path, fcpxml_path, bundle_dicts


def main() -> None:
    args = parse_args()
    ad_brief: AdBrief | None = None
    bpm = 0.0
    primary_text = ""
    creative_notes = ""

    if args.workflow_type == "music_video":
        primary_text, bpm, creative_notes = resolve_music_video_inputs(args)
        if not primary_text:
            raise SystemExit("Lyrics input is empty.")
        if bpm <= 0:
            raise SystemExit("BPM must be greater than 0.")
        if args.beats_per_bar <= 0:
            raise SystemExit("beats_per_bar must be greater than 0.")
        if args.bars_per_scene <= 0:
            raise SystemExit("bars_per_scene must be greater than 0.")
        timing = build_edit_timing_spec(bpm, args.beats_per_bar, args.bars_per_scene)
    else:
        if not args.ad_style:
            raise SystemExit("Error: --ad_style is required when --workflow_type advertisement.")
        if not args.brief_file:
            raise SystemExit("Error: advertisement workflow requires --brief_file.")
        ad_brief = load_ad_brief(Path(args.brief_file))
        primary_text = ad_brief.product_name
        creative_notes = ad_brief.creative_notes
        timing = build_ad_timing_spec()

    prompts_path, fcpxml_path, _bundles = write_outputs(
        args.workflow_type,
        args.ad_style or "",
        args.project_name,
        bpm,
        primary_text,
        timing,
        Path(args.input_dir),
        args.brief_file or "",
        creative_notes,
        ad_brief,
    )
    print(f"Wrote prompts: {prompts_path}")
    print(f"Wrote FCPXML: {fcpxml_path}")


if __name__ == "__main__":
    main()
