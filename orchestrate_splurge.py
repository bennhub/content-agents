#!/usr/bin/env python3

import argparse
import math
import re
import shutil
from pathlib import Path
from textwrap import fill
from typing import NamedTuple
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring


FPS = 23.976
TIMEBASE = 24
SCENE_COUNT = 6
DEFAULT_BEATS_PER_BAR = 4
DEFAULT_BARS_PER_SCENE = 2
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
TEMPLATE_PATH = Path(__file__).with_name("premiere_xml_logic.md")
PLACEHOLDER_MASTER_PATH = Path(__file__).with_name("placeholder_master.mp4")

VISUAL_MOTIFS = [
    "chrome reflections, lens grime, drifting smoke, restless handheld momentum",
    "neon spill, rolling shadows, strobe pulses, aggressive parallax",
    "heat shimmer, glitter particles, whip pans, fractured mirror textures",
    "rain-slick streets, halation blooms, rolling dolly pressure, kinetic blur",
    "burnt film edges, overcranked motion, light leaks, sharp silhouette contrast",
    "laser haze, sweeping cranes, ghosted double exposure, relentless camera energy",
]

PALETTES = [
    "sodium gold and bruised teal",
    "crimson, obsidian, and electric cyan",
    "silver, asphalt black, and toxic lime",
    "sunset amber, magenta haze, and deep navy",
    "ice blue, graphite, and hard white flashes",
    "copper, scarlet, and oil-slick violet",
]

EMOTIONS = [
    "anticipation",
    "ignition",
    "euphoria",
    "instability",
    "defiance",
    "aftermath",
]


class TimingSpec(NamedTuple):
    beats_per_bar: int
    bars_per_scene: int
    beats_per_scene: int
    seconds_per_beat: float
    seconds_per_bar: float
    seconds_per_scene: float
    frames_per_scene: int
    total_frames: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate LTX prompts and a Premiere/FCP7 XML timeline for a six-scene visual splurge."
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


def build_timing_spec(bpm: float, beats_per_bar: int, bars_per_scene: int) -> TimingSpec:
    beats_per_scene = beats_per_bar * bars_per_scene
    seconds_per_beat = 60.0 / bpm
    seconds_per_bar = seconds_per_beat * beats_per_bar
    seconds_per_scene = seconds_per_bar * bars_per_scene
    frames_per_scene = round(seconds_per_scene * FPS)
    total_frames = frames_per_scene * SCENE_COUNT
    return TimingSpec(
        beats_per_bar=beats_per_bar,
        bars_per_scene=bars_per_scene,
        beats_per_scene=beats_per_scene,
        seconds_per_beat=seconds_per_beat,
        seconds_per_bar=seconds_per_bar,
        seconds_per_scene=seconds_per_scene,
        frames_per_scene=frames_per_scene,
        total_frames=total_frames,
    )


def load_template() -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Missing XML template: {TEMPLATE_PATH}")
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def load_lyrics(value: str) -> str:
    candidate = Path(value)
    if candidate.exists() and candidate.is_file():
        return candidate.read_text(encoding="utf-8").strip()
    return value.strip()


def tokenize_lyrics(lyrics: str) -> list[str]:
    lines = [line.strip() for line in lyrics.splitlines() if line.strip()]
    if lines:
        return lines
    phrases = [part.strip() for part in re.split(r"(?<=[,.;!?])\s+|\s{2,}", lyrics) if part.strip()]
    return phrases or [lyrics.strip()]


def split_into_scenes(lyrics: str, scene_count: int = SCENE_COUNT) -> list[str]:
    units = tokenize_lyrics(lyrics)
    if not units:
        return ["Instrumental mood bridge"] * scene_count

    scenes: list[str] = []
    total = len(units)
    for index in range(scene_count):
        start = math.floor(index * total / scene_count)
        end = math.floor((index + 1) * total / scene_count)
        chunk = units[start:end]
        if not chunk:
            fallback = units[min(index, total - 1)]
            chunk = [fallback]
        scenes.append(" ".join(chunk))
    return scenes


def classify_energy(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("fire", "burn", "riot", "crash", "run", "wild")):
        return "feral, explosive movement"
    if any(word in lowered for word in ("night", "shadow", "slow", "ghost", "dream", "moon")):
        return "moody, nocturnal drift"
    if any(word in lowered for word in ("love", "touch", "heart", "kiss", "hold")):
        return "intimate, romantic intensity"
    if any(word in lowered for word in ("rise", "light", "gold", "shine", "sky")):
        return "uplifting, expansive lift"
    return "cinematic, pulse-driven urgency"


def build_prompt(scene_text: str, scene_number: int, bpm: float, timing: TimingSpec) -> str:
    motif = VISUAL_MOTIFS[(scene_number - 1) % len(VISUAL_MOTIFS)]
    palette = PALETTES[(scene_number - 1) % len(PALETTES)]
    emotion = EMOTIONS[(scene_number - 1) % len(EMOTIONS)]
    energy = classify_energy(scene_text)
    sanitized_lyric = re.sub(r"\s+", " ", scene_text).strip()

    return (
        f"Scene {scene_number:02d} | LTX 2.3 prompt | {emotion}. "
        f"Use {energy}, {motif}, palette of {palette}, 720p cinematic music-video framing, "
        f"23.976 fps playback feel, dense environmental detail, performers and props reacting on beat, "
        f"hard rhythmic transitions every {timing.beats_per_scene} beats "
        f"({timing.bars_per_scene} bars in {timing.beats_per_bar}/4) at {bpm:.2f} BPM, "
        f"continuous {timing.seconds_per_scene:.2f}-second shot, high motion, editorially useful composition, "
        f"no subtitles, no logos. "
        f'Lyric focus: "{sanitized_lyric}".'
    )


def make_text_element(parent: Element, tag: str, text: str) -> Element:
    element = SubElement(parent, tag)
    element.text = text
    return element


def build_xml(project_name: str, output_dir: Path, timing: TimingSpec, scene_count: int = SCENE_COUNT) -> str:
    xmeml = Element("xmeml", version="4")
    sequence = SubElement(xmeml, "sequence")
    make_text_element(sequence, "name", f"{project_name}_Visual_Splurge")

    rate = SubElement(sequence, "rate")
    make_text_element(rate, "timebase", str(TIMEBASE))
    make_text_element(rate, "ntsc", "TRUE")

    make_text_element(sequence, "duration", str(timing.total_frames))

    media = SubElement(sequence, "media")
    video = SubElement(media, "video")
    format_element = SubElement(video, "format")
    sample_characteristics = SubElement(format_element, "samplecharacteristics")
    rate2 = SubElement(sample_characteristics, "rate")
    make_text_element(rate2, "timebase", str(TIMEBASE))
    make_text_element(rate2, "ntsc", "TRUE")
    make_text_element(sample_characteristics, "width", str(FRAME_WIDTH))
    make_text_element(sample_characteristics, "height", str(FRAME_HEIGHT))
    make_text_element(sample_characteristics, "anamorphic", "FALSE")
    make_text_element(sample_characteristics, "pixelaspectratio", "square")
    make_text_element(sample_characteristics, "fielddominance", "none")

    track = SubElement(video, "track")

    for index in range(scene_count):
        scene_number = index + 1
        clip_id = f"scene_{scene_number:02d}"
        start_frame = index * timing.frames_per_scene
        end_frame = start_frame + timing.frames_per_scene

        clipitem = SubElement(track, "clipitem", id=clip_id)
        make_text_element(clipitem, "name", f"{clip_id}.mp4")
        make_text_element(clipitem, "duration", str(timing.frames_per_scene))

        file_element = SubElement(clipitem, "file", id=f"file_{scene_number:02d}")
        make_text_element(file_element, "name", f"{clip_id}.mp4")
        make_text_element(file_element, "duration", str(timing.frames_per_scene))
        file_rate = SubElement(file_element, "rate")
        make_text_element(file_rate, "timebase", str(TIMEBASE))
        make_text_element(file_rate, "ntsc", "TRUE")
        make_text_element(file_element, "pathurl", f"{clip_id}.mp4")
        media2 = SubElement(file_element, "media")
        video2 = SubElement(media2, "video")
        sample_characteristics2 = SubElement(video2, "samplecharacteristics")
        rate3 = SubElement(sample_characteristics2, "rate")
        make_text_element(rate3, "timebase", str(TIMEBASE))
        make_text_element(rate3, "ntsc", "TRUE")
        make_text_element(sample_characteristics2, "width", str(FRAME_WIDTH))
        make_text_element(sample_characteristics2, "height", str(FRAME_HEIGHT))

        make_text_element(clipitem, "start", str(start_frame))
        make_text_element(clipitem, "end", str(end_frame))
        make_text_element(clipitem, "in", "0")
        make_text_element(clipitem, "out", str(timing.frames_per_scene))

    pretty = minidom.parseString(tostring(xmeml, encoding="utf-8")).toprettyxml(indent="  ")
    return "\n".join(line for line in pretty.splitlines() if line.strip())


def write_outputs(
    project_name: str,
    bpm: float,
    lyrics: str,
    template: str,
    timing: TimingSpec,
) -> tuple[Path, Path]:
    output_dir = Path(project_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve()

    if not PLACEHOLDER_MASTER_PATH.exists():
        raise SystemExit(
            "Error: placeholder_master.mp4 not found in root. Please add a test video file to continue."
        )

    scenes = split_into_scenes(lyrics, SCENE_COUNT)
    prompts_path = output_dir / "prompts.txt"
    xml_path = output_dir / f"{project_name}.xml"

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
        f"Template source: {TEMPLATE_PATH.name}",
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
        prompt_lines.append(fill(build_prompt(scene_text, index, bpm, timing), width=100))
        prompt_lines.append("")

    prompts_path.write_text("\n".join(prompt_lines).rstrip() + "\n", encoding="utf-8")
    xml_path.write_text(build_xml(project_name, output_dir, timing), encoding="utf-8")

    template_copy = output_dir / "template_reference.txt"
    template_copy.write_text(template.strip() + "\n", encoding="utf-8")
    return prompts_path, xml_path


def main() -> None:
    args = parse_args()
    template = load_template()
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
    prompts_path, xml_path = write_outputs(args.project_name, args.bpm, lyrics, template, timing)
    print(f"Wrote prompts: {prompts_path}")
    print(f"Wrote XML: {xml_path}")


if __name__ == "__main__":
    main()
