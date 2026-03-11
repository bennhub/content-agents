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

from orchestrate_splurge import (
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
DIRECTOR_SETTINGS_PATH = Path(__file__).with_name("director_settings.json")
SLOW_BPM_THRESHOLD = 100.0
TARGET_MAX_SCENE_SECONDS = 5.0
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


def append_clause(base: str, clause: str) -> str:
    if clause in base:
        return base
    return f"{base}, {clause}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate LTX prompts and a Final Cut Pro FCPXML timeline for a six-scene visual splurge."
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


def resolve_project_inputs(args: argparse.Namespace) -> tuple[str, float, str]:
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


def build_fcpx_prompt(
    scene_text: str,
    scene_number: int,
    bpm: float,
    timing: EditTimingSpec,
    director_settings: list[dict[str, str]],
    timeline_duration: float,
) -> str:
    scene_style = get_scene_style(scene_number, director_settings)
    energy = classify_energy(scene_text)
    sanitized_lyric = re.sub(r"\s+", " ", scene_text).strip()

    return (
        f"Scene {scene_number:02d} | LTX 2.3 prompt | "
        f"Build a {scene_style['style']} cinematic music-video shot with {energy}. "
        f"Use camera direction: {scene_style['camera']}. "
        f"Use lighting direction: {scene_style['lighting']}. "
        f"Use palette direction: {scene_style['palette']}. "
        f"Keep the frame premium, tactile, high-motion, and editorially useful, with performers and props reacting to the lyric. "
        f"Maintain 720p framing, 23.976 fps playback feel, and hard rhythmic transitions every {timing.beats_per_scene} beats "
        f"({timing.bars_per_scene:.2f} bars in {timing.beats_per_bar}/4) at edit BPM {timing.effective_bpm:.2f} "
        f"from song BPM {bpm:.2f}. "
        f"Design it as one continuous {timeline_duration:.2f}-second shot with no subtitles, no logos, and no watermarks. "
        f'Lyric focus: "{sanitized_lyric}".'
    )


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


def build_timeline_durations(
    scene_sources: list[tuple[Path, float]],
    timing: EditTimingSpec,
) -> list[float]:
    return [min(source_duration, timing.seconds_per_scene) for _path, source_duration in scene_sources]


def build_fcpxml(
    project_label: str,
    output_dir: Path,
    timing: EditTimingSpec,
    scene_sources: list[tuple[Path, float]],
    timeline_durations: list[float],
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
    total_timeline_seconds = sum(timeline_durations)
    sequence = SubElement(
        project,
        "sequence",
        format="r1",
        duration=fcpx_time_from_seconds(total_timeline_seconds),
        tcStart="0s",
        tcFormat="NDF",
        audioLayout="stereo",
        audioRate="48k",
    )
    spine = SubElement(sequence, "spine")

    offset_seconds = 0.0
    for index, (_scene_source, timeline_duration) in enumerate(zip(scene_sources, timeline_durations), start=1):
        clip_id = f"scene_{index:02d}"
        offset = fcpx_time_from_seconds(offset_seconds)
        SubElement(
            spine,
            "video",
            ref=f"r{index + 1}",
            name=f"{clip_id}.mp4",
            offset=offset,
            start="0s",
            duration=fcpx_time_from_seconds(timeline_duration),
        )
        offset_seconds += timeline_duration

    pretty = minidom.parseString(tostring(fcpxml, encoding="utf-8")).toprettyxml(indent="  ")
    return "\n".join(line for line in pretty.splitlines() if line.strip())


def write_outputs(
    project_name: str,
    bpm: float,
    lyrics: str,
    timing: EditTimingSpec,
    input_dir: Path,
    brief_file: str,
    creative_notes: str,
) -> tuple[Path, Path]:
    output_dir = Path(project_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve()
    project_label = output_dir.name
    scenes = split_into_scenes(lyrics, SCENE_COUNT)
    if brief_file:
        director_settings = build_auto_director_settings(scenes, creative_notes)
        director_settings_path = write_director_settings(output_dir, director_settings)
    else:
        director_settings = load_director_settings()
        director_settings_path = DIRECTOR_SETTINGS_PATH.resolve()

    scene_sources = validate_input_scenes(input_dir.resolve(), timing)
    timeline_durations = build_timeline_durations(scene_sources, timing)
    prompts_path = output_dir / "prompts.txt"
    fcpxml_path = output_dir / f"{project_label}.fcpxml"

    for index, (source_path, _source_duration) in enumerate(scene_sources, start=1):
        scene_path = output_dir / f"scene_{index:02d}.mp4"
        shutil.copyfile(source_path, scene_path)

    prompt_lines = [
        f"Project: {project_label}",
        f"Song BPM: {bpm:.2f}",
        f"Edit BPM: {timing.effective_bpm:.2f}",
        f"Double-time timing: {'yes' if timing.uses_double_time else 'no'}",
        f"Time signature: {timing.beats_per_bar}/4",
        f"Bars per scene: {timing.bars_per_scene:.2f}",
        f"Beats per scene: {timing.beats_per_scene}",
        f"Target scene length: {timing.seconds_per_scene:.2f}s",
        f"Target max scene length: {TARGET_MAX_SCENE_SECONDS:.2f}s",
        f"Frames per scene: {timing.frames_per_scene}",
        f"Actual timeline length: {sum(timeline_durations):.2f}s",
        f"Input directory: {input_dir.resolve()}",
        f"Timeline type: FCPXML {FCPXML_VERSION}",
        f"Director settings: {director_settings_path}",
        f"Brief file: {brief_file or 'manual CLI inputs'}",
        "",
    ]

    for index, scene_text in enumerate(scenes, start=1):
        beat_start = (index - 1) * timing.beats_per_scene
        beat_end = index * timing.beats_per_scene
        bar_start = (index - 1) * timing.bars_per_scene + 1
        bar_end = index * timing.bars_per_scene
        source_duration = scene_sources[index - 1][1]
        timeline_duration = timeline_durations[index - 1]
        prompt_lines.append(f"[Scene {index:02d}]")
        prompt_lines.append(f"Lyric chunk: {scene_text}")
        prompt_lines.append(f"Source clip: {scene_sources[index - 1][0].name}")
        prompt_lines.append(f"Source duration: {source_duration:.2f}s")
        prompt_lines.append(f"Timeline duration used: {timeline_duration:.2f}s")
        prompt_lines.append(f"Bar window: {bar_start:.2f} -> {bar_end:.2f}")
        prompt_lines.append(f"Beat window: {beat_start:.2f} -> {beat_end:.2f}")
        prompt_lines.append(
            build_fcpx_prompt(
                scene_text,
                index,
                bpm,
                timing,
                director_settings,
                timeline_duration,
            )
        )
        prompt_lines.append("")

    prompts_path.write_text("\n".join(prompt_lines).rstrip() + "\n", encoding="utf-8")
    fcpxml_path.write_text(
        build_fcpxml(project_label, output_dir, timing, scene_sources, timeline_durations),
        encoding="utf-8",
    )
    return prompts_path, fcpxml_path


def main() -> None:
    args = parse_args()
    lyrics, bpm, creative_notes = resolve_project_inputs(args)
    if not lyrics:
        raise SystemExit("Lyrics input is empty.")
    if bpm <= 0:
        raise SystemExit("BPM must be greater than 0.")
    if args.beats_per_bar <= 0:
        raise SystemExit("beats_per_bar must be greater than 0.")
    if args.bars_per_scene <= 0:
        raise SystemExit("bars_per_scene must be greater than 0.")

    timing = build_edit_timing_spec(bpm, args.beats_per_bar, args.bars_per_scene)
    prompts_path, fcpxml_path = write_outputs(
        args.project_name,
        bpm,
        lyrics,
        timing,
        Path(args.input_dir),
        args.brief_file or "",
        creative_notes,
    )
    print(f"Wrote prompts: {prompts_path}")
    print(f"Wrote FCPXML: {fcpxml_path}")


if __name__ == "__main__":
    main()
