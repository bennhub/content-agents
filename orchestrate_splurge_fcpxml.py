#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import shutil
from fractions import Fraction
from pathlib import Path
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from orchestrate_splurge import (
    DEFAULT_BARS_PER_SCENE,
    DEFAULT_BEATS_PER_BAR,
    FRAME_HEIGHT,
    FRAME_WIDTH,
    SCENE_COUNT,
    TimingSpec,
    build_timing_spec,
    classify_energy,
    load_lyrics,
    split_into_scenes,
)


FCPXML_VERSION = "1.5"
FRAME_DURATION = Fraction(1001, 24000)
EXPECTED_SCENE_FILES = tuple(f"scene_{index:02d}.mp4" for index in range(1, SCENE_COUNT + 1))
DIRECTOR_SETTINGS_PATH = Path(__file__).with_name("director_settings.json")
DEFAULT_SCENE_STYLE = {
    "style": "Cinematic",
    "camera": "tracking shot with confident movement and low-angle framing",
    "lighting": "cinematic lighting with motivated practicals, contrast, and atmospheric haze",
    "palette": "steel blue, tungsten amber, and controlled shadow",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate LTX prompts and a Final Cut Pro FCPXML timeline for a six-scene visual splurge."
    )
    parser.add_argument("--lyrics", required=True, help="Raw lyrics text or a path to a text file.")
    parser.add_argument("--bpm", required=True, type=float, help="Song tempo in beats per minute.")
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


def build_fcpx_prompt(
    scene_text: str,
    scene_number: int,
    bpm: float,
    timing: TimingSpec,
    director_settings: list[dict[str, str]],
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
        f"({timing.bars_per_scene} bars in {timing.beats_per_bar}/4) at {bpm:.2f} BPM. "
        f"Design it as one continuous {timing.seconds_per_scene:.2f}-second shot with no subtitles, no logos, and no watermarks. "
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


def validate_input_scenes(input_dir: Path, timing: TimingSpec) -> list[tuple[Path, float]]:
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Error: input directory not found: {input_dir}")

    required_duration = timing.seconds_per_scene
    scene_sources: list[tuple[Path, float]] = []
    for file_name in EXPECTED_SCENE_FILES:
        scene_path = input_dir / file_name
        if not scene_path.exists() or not scene_path.is_file():
            raise SystemExit(f"Error: missing required input clip: {scene_path}")

        duration_seconds = get_media_duration_seconds(scene_path)
        if duration_seconds + 0.001 < required_duration:
            raise SystemExit(
                f"Error: {scene_path.name} is too short ({duration_seconds:.2f}s). "
                f"Required minimum is {required_duration:.2f}s."
            )
        scene_sources.append((scene_path, duration_seconds))

    return scene_sources


def build_fcpxml(
    project_label: str,
    output_dir: Path,
    timing: TimingSpec,
    scene_sources: list[tuple[Path, float]],
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
    sequence = SubElement(
        project,
        "sequence",
        format="r1",
        duration=fcpx_time_from_frames(timing.total_frames),
        tcStart="0s",
        tcFormat="NDF",
        audioLayout="stereo",
        audioRate="48k",
    )
    spine = SubElement(sequence, "spine")

    for index, _scene_source in enumerate(scene_sources, start=1):
        clip_id = f"scene_{index:02d}"
        offset = fcpx_time_from_frames((index - 1) * timing.frames_per_scene)
        SubElement(
            spine,
            "video",
            ref=f"r{index + 1}",
            name=f"{clip_id}.mp4",
            offset=offset,
            start="0s",
            duration=fcpx_time_from_frames(timing.frames_per_scene),
        )

    pretty = minidom.parseString(tostring(fcpxml, encoding="utf-8")).toprettyxml(indent="  ")
    return "\n".join(line for line in pretty.splitlines() if line.strip())


def write_outputs(
    project_name: str,
    bpm: float,
    lyrics: str,
    timing: TimingSpec,
    input_dir: Path,
) -> tuple[Path, Path]:
    output_dir = Path(project_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve()
    project_label = output_dir.name
    director_settings = load_director_settings()
    scene_sources = validate_input_scenes(input_dir.resolve(), timing)

    scenes = split_into_scenes(lyrics, SCENE_COUNT)
    prompts_path = output_dir / "prompts.txt"
    fcpxml_path = output_dir / f"{project_label}.fcpxml"

    for index, (source_path, _source_duration) in enumerate(scene_sources, start=1):
        scene_path = output_dir / f"scene_{index:02d}.mp4"
        shutil.copyfile(source_path, scene_path)

    prompt_lines = [
        f"Project: {project_label}",
        f"BPM: {bpm:.2f}",
        f"Time signature: {timing.beats_per_bar}/4",
        f"Bars per scene: {timing.bars_per_scene}",
        f"Beats per scene: {timing.beats_per_scene}",
        f"Scene length: {timing.seconds_per_scene:.2f}s",
        f"Frames per scene: {timing.frames_per_scene}",
        f"Input directory: {input_dir.resolve()}",
        f"Timeline type: FCPXML {FCPXML_VERSION}",
        f"Director settings: {DIRECTOR_SETTINGS_PATH.resolve()}",
        "",
    ]

    for index, scene_text in enumerate(scenes, start=1):
        beat_start = (index - 1) * timing.beats_per_scene
        beat_end = index * timing.beats_per_scene
        bar_start = (index - 1) * timing.bars_per_scene + 1
        bar_end = index * timing.bars_per_scene
        source_duration = scene_sources[index - 1][1]
        prompt_lines.append(f"[Scene {index:02d}]")
        prompt_lines.append(f"Lyric chunk: {scene_text}")
        prompt_lines.append(f"Source clip: {scene_sources[index - 1][0].name}")
        prompt_lines.append(f"Source duration: {source_duration:.2f}s")
        prompt_lines.append(f"Bar window: {bar_start} -> {bar_end}")
        prompt_lines.append(f"Beat window: {beat_start:.2f} -> {beat_end:.2f}")
        prompt_lines.append(build_fcpx_prompt(scene_text, index, bpm, timing, director_settings))
        prompt_lines.append("")

    prompts_path.write_text("\n".join(prompt_lines).rstrip() + "\n", encoding="utf-8")
    fcpxml_path.write_text(build_fcpxml(project_label, output_dir, timing, scene_sources), encoding="utf-8")
    return prompts_path, fcpxml_path


def main() -> None:
    args = parse_args()
    lyrics = load_lyrics(args.lyrics)
    if not lyrics:
        raise SystemExit("Lyrics input is empty.")
    if args.bpm <= 0:
        raise SystemExit("BPM must be greater than 0.")
    if args.beats_per_bar <= 0:
        raise SystemExit("beats_per_bar must be greater than 0.")
    if args.bars_per_scene <= 0:
        raise SystemExit("bars_per_scene must be greater than 0.")

    timing = build_timing_spec(args.bpm, args.beats_per_bar, args.bars_per_scene)
    prompts_path, fcpxml_path = write_outputs(
        args.project_name,
        args.bpm,
        lyrics,
        timing,
        Path(args.input_dir),
    )
    print(f"Wrote prompts: {prompts_path}")
    print(f"Wrote FCPXML: {fcpxml_path}")


if __name__ == "__main__":
    main()
