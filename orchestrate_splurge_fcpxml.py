#!/usr/bin/env python3

import argparse
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
    PLACEHOLDER_MASTER_PATH,
    SCENE_COUNT,
    TimingSpec,
    build_prompt,
    build_timing_spec,
    load_lyrics,
    split_into_scenes,
)


FCPXML_VERSION = "1.5"
FRAME_DURATION = Fraction(1001, 24000)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate LTX prompts and a Final Cut Pro FCPXML timeline for a six-scene visual splurge."
    )
    parser.add_argument("--lyrics", required=True, help="Raw lyrics text or a path to a text file.")
    parser.add_argument("--bpm", required=True, type=float, help="Song tempo in beats per minute.")
    parser.add_argument("--project_name", required=True, help="Folder and sequence naming prefix.")
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


def make_text_element(parent: Element, tag: str, text: str) -> Element:
    element = SubElement(parent, tag)
    element.text = text
    return element


def build_fcpxml(project_name: str, output_dir: Path, timing: TimingSpec, scene_count: int = SCENE_COUNT) -> str:
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

    asset_duration = fcpx_time_from_frames(timing.frames_per_scene)
    for index in range(scene_count):
        scene_number = index + 1
        clip_id = f"scene_{scene_number:02d}"
        scene_path = (output_dir / f"{clip_id}.mp4").resolve().as_uri()
        SubElement(
            resources,
            "asset",
            id=f"r{scene_number + 1}",
            name=f"{clip_id}.mp4",
            src=scene_path,
            start="0s",
            duration=asset_duration,
            hasVideo="1",
            hasAudio="1",
            format="r1",
            audioSources="1",
            audioChannels="2",
            audioRate="48k",
        )

    library = SubElement(fcpxml, "library")
    event = SubElement(library, "event", name=f"{project_name} Event")
    project = SubElement(event, "project", name=project_name)
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

    for index in range(scene_count):
        scene_number = index + 1
        clip_id = f"scene_{scene_number:02d}"
        offset = fcpx_time_from_frames(index * timing.frames_per_scene)
        SubElement(
            spine,
            "video",
            ref=f"r{scene_number + 1}",
            name=f"{clip_id}.mp4",
            offset=offset,
            start="0s",
            duration=fcpx_time_from_frames(timing.frames_per_scene),
        )

    pretty = minidom.parseString(tostring(fcpxml, encoding="utf-8")).toprettyxml(indent="  ")
    return "\n".join(line for line in pretty.splitlines() if line.strip())


def write_outputs(project_name: str, bpm: float, lyrics: str, timing: TimingSpec) -> tuple[Path, Path]:
    output_dir = Path(project_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve()

    if not PLACEHOLDER_MASTER_PATH.exists():
        raise SystemExit(
            "Error: placeholder_master.mp4 not found in root. Please add a test video file to continue."
        )

    scenes = split_into_scenes(lyrics, SCENE_COUNT)
    prompts_path = output_dir / "prompts.txt"
    fcpxml_path = output_dir / f"{project_name}.fcpxml"

    for index in range(1, SCENE_COUNT + 1):
        scene_path = output_dir / f"scene_{index:02d}.mp4"
        shutil.copyfile(PLACEHOLDER_MASTER_PATH, scene_path)

    prompt_lines = [
        f"Project: {project_name}",
        f"BPM: {bpm:.2f}",
        f"Time signature: {timing.beats_per_bar}/4",
        f"Bars per scene: {timing.bars_per_scene}",
        f"Beats per scene: {timing.beats_per_scene}",
        f"Scene length: {timing.seconds_per_scene:.2f}s",
        f"Frames per scene: {timing.frames_per_scene}",
        f"Timeline type: FCPXML {FCPXML_VERSION}",
        "",
    ]

    for index, scene_text in enumerate(scenes, start=1):
        beat_start = (index - 1) * timing.beats_per_scene
        beat_end = index * timing.beats_per_scene
        bar_start = (index - 1) * timing.bars_per_scene + 1
        bar_end = index * timing.bars_per_scene
        prompt_lines.append(f"[Scene {index:02d}]")
        prompt_lines.append(f"Lyric chunk: {scene_text}")
        prompt_lines.append(f"Bar window: {bar_start} -> {bar_end}")
        prompt_lines.append(f"Beat window: {beat_start:.2f} -> {beat_end:.2f}")
        prompt_lines.append(build_prompt(scene_text, index, bpm, timing))
        prompt_lines.append("")

    prompts_path.write_text("\n".join(prompt_lines).rstrip() + "\n", encoding="utf-8")
    fcpxml_path.write_text(build_fcpxml(project_name, output_dir, timing), encoding="utf-8")
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
    prompts_path, fcpxml_path = write_outputs(args.project_name, args.bpm, lyrics, timing)
    print(f"Wrote prompts: {prompts_path}")
    print(f"Wrote FCPXML: {fcpxml_path}")


if __name__ == "__main__":
    main()
