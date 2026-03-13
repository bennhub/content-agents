#!/usr/bin/env python3
"""
run.py — Unified content pipeline conductor.

Flow: project brief -> prompts + timeline (Premiere or FCP) -> ComfyUI GPU render

Usage examples:

  Music video, Premiere timeline:
    python run.py --type music_video --brief briefs/music_vid_input.md \
        --project_name my_video --input_dir ./scene_clips

  Ad, FCP timeline + push to ComfyUI:
    python run.py --type ad --brief briefs/ad_project_input.md \
        --project_name my_ad --input_dir ./scene_clips \
        --ad_style brand_spot --timeline fcp --comfy

  Both timelines + ComfyUI:
    python run.py --type music_video --brief briefs/music_vid_input.md \
        --project_name my_video --input_dir ./scene_clips \
        --timeline both --comfy
"""

import argparse
import sys
from pathlib import Path

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]

WORKFLOWS_DIR = Path(__file__).resolve().parent / "workflows"
MV_WORKFLOW = WORKFLOWS_DIR / "mv_workflow.json"
AD_WORKFLOW = WORKFLOWS_DIR / "ad_workflow.json"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def check_comfy_health(comfy_url: str) -> bool:
    """Return True if the ComfyUI server is reachable."""
    if _requests is None:
        raise SystemExit("Error: 'requests' library is required. Run: pip install requests")
    try:
        resp = _requests.get(f"{comfy_url}/system_stats", timeout=5)
        return resp.status_code == 200
    except _requests.exceptions.ConnectionError:
        return False


# ---------------------------------------------------------------------------
# Workflow JSON selection
# ---------------------------------------------------------------------------

def resolve_workflow_path(workflow_type: str, override: str | None) -> Path:
    """Return the ComfyUI workflow JSON path for this content type."""
    if override:
        p = Path(override)
        if not p.exists():
            raise SystemExit(f"Error: workflow file not found: {p}")
        return p

    mapping = {
        "music_video": MV_WORKFLOW,
        "ad": AD_WORKFLOW,
    }
    path = mapping[workflow_type]
    if not path.exists():
        raise SystemExit(
            f"Error: workflow file not found: {path}\n"
            f"Place your ComfyUI workflow JSON files in {WORKFLOWS_DIR}/\n"
            f"  Music video workflow -> workflows/mv_workflow.json\n"
            f"  Ad workflow          -> workflows/ad_workflow.json\n"
            "Export from ComfyUI: Settings > Dev Mode > Save (API Format)"
        )
    return path


def load_workflow_nodes(workflow_path: Path) -> dict:
    """
    Load node ID config from a companion _nodes.json file next to the workflow.

    E.g. workflows/mv_workflow.json -> workflows/mv_workflow_nodes.json

    Falls back to empty dict (caller uses CLI defaults) if the file is absent.
    """
    import json as _json
    nodes_path = workflow_path.with_name(
        workflow_path.stem + "_nodes" + workflow_path.suffix
    )
    if not nodes_path.exists():
        return {}
    try:
        return _json.loads(nodes_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[warn] Could not read node config {nodes_path.name}: {exc}")
        return {}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified content pipeline: brief -> prompts -> timeline -> ComfyUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--type", dest="workflow_type",
        choices=["music_video", "ad"],
        required=True,
        help="Content type to generate.",
    )
    parser.add_argument(
        "--brief", dest="brief_file",
        required=True,
        help="Path to project brief markdown file.",
    )
    parser.add_argument(
        "--project_name",
        required=True,
        help="Output folder and sequence name prefix.",
    )
    parser.add_argument(
        "--input_dir",
        default=".",
        help="Folder with scene_01.mp4 – scene_06.mp4 (FCP only). Default: current dir.",
    )
    parser.add_argument(
        "--timeline",
        choices=["prem", "fcp", "both"],
        default="prem",
        help="Timeline format to generate. Default: prem (Premiere Pro XMEML).",
    )
    parser.add_argument(
        "--ad_style",
        choices=["brand_spot", "lifestyle", "ugc"],
        default="brand_spot",
        help="Ad sub-style. Used when --type ad. Default: brand_spot.",
    )
    parser.add_argument("--beats_per_bar", type=int, default=4,
                        help="Time signature numerator. Default: 4.")
    parser.add_argument("--bars_per_scene", type=int, default=2,
                        help="Bars per scene (music video timing). Default: 2.")
    parser.add_argument(
        "--comfy",
        action="store_true",
        help="Push each scene to ComfyUI for GPU rendering after generation.",
    )
    parser.add_argument(
        "--workflow", dest="workflow_path", default=None,
        help="Override ComfyUI workflow JSON. Auto-selected from workflows/ if omitted.",
    )
    parser.add_argument(
        "--comfy_url",
        default="http://127.0.0.1:8188",
        help="ComfyUI server URL. Default: http://127.0.0.1:8188.",
    )
    parser.add_argument("--node_clip_image", default="6",
                        help="ComfyUI node ID for image/CLIP text input. Default: 6.")
    parser.add_argument("--node_ltx_motion", default="12",
                        help="ComfyUI node ID for LTX motion text input. Default: 12.")
    parser.add_argument("--node_ksampler", default="3",
                        help="ComfyUI node ID for KSampler seed. Default: 3.")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Orchestrators
# ---------------------------------------------------------------------------

def run_premiere(args: argparse.Namespace) -> list[dict]:
    """Run the Premiere Pro orchestrator (music video only)."""
    from orchestrate_premxml import (
        build_timing_spec,
        load_lyrics,
        write_outputs,
    )
    from orchestrate_fcpxml import load_project_brief

    if args.workflow_type == "ad":
        print("[prem] NOTE: Premiere orchestrator is music-video only.")
        print("[prem] Skipping Premiere output for ad workflow.")
        return []

    lyrics, bpm, _notes = load_project_brief(Path(args.brief_file))
    if not lyrics:
        raise SystemExit("Error: brief is missing lyrics.")
    if bpm <= 0:
        raise SystemExit("Error: BPM must be greater than 0.")

    timing = build_timing_spec(bpm, args.beats_per_bar, args.bars_per_scene)
    prompts_path, xml_path, scene_bundles = write_outputs(
        args.project_name, bpm, lyrics, timing
    )
    print(f"[prem]  Prompts : {prompts_path}")
    print(f"[prem]  XMEML   : {xml_path}")
    return scene_bundles


def run_fcp(args: argparse.Namespace) -> list[dict]:
    """Run the Final Cut Pro orchestrator (music video + ads)."""
    from orchestrate_fcpxml import (
        AdBrief,
        build_ad_timing_spec,
        build_edit_timing_spec,
        load_ad_brief,
        load_project_brief,
        write_outputs,
    )

    ad_brief: AdBrief | None = None
    bpm = 0.0
    primary_text = ""
    creative_notes = ""

    if args.workflow_type == "music_video":
        primary_text, bpm, creative_notes = load_project_brief(Path(args.brief_file))
        if not primary_text:
            raise SystemExit("Error: brief is missing lyrics.")
        if bpm <= 0:
            raise SystemExit("Error: BPM must be greater than 0.")
        timing = build_edit_timing_spec(bpm, args.beats_per_bar, args.bars_per_scene)
    else:
        ad_brief = load_ad_brief(Path(args.brief_file))
        primary_text = ad_brief.product_name
        creative_notes = ad_brief.creative_notes
        timing = build_ad_timing_spec()

    prompts_path, fcpxml_path, scene_bundles = write_outputs(
        workflow_type=args.workflow_type,
        ad_style=args.ad_style or "",
        project_name=args.project_name,
        bpm=bpm,
        primary_text=primary_text,
        timing=timing,
        input_dir=Path(args.input_dir),
        brief_file=args.brief_file,
        creative_notes=creative_notes,
        ad_brief=ad_brief,
    )
    print(f"[fcp]   Prompts : {prompts_path}")
    print(f"[fcp]   FCPXML  : {fcpxml_path}")
    return scene_bundles


# ---------------------------------------------------------------------------
# ComfyUI push
# ---------------------------------------------------------------------------

def push_to_comfy(
    scene_bundles: list[dict],
    workflow_path: Path,
    comfy_url: str,
    node_overrides: dict,
) -> None:
    """
    Send each scene bundle to ComfyUI for GPU rendering using last-frame/first-frame.

    Scene 1: generates a starting image + video from scratch.
    Scene 2+: extracts the 2nd-to-last frame from the previous video and uses it
              as the first frame input, creating seamless clip-to-clip continuity.

    node_overrides: merged dict from _nodes.json config + any CLI --node_* flags.
    """
    from pathlib import Path as _Path
    from comfy_client import (
        send_to_comfy_headless,
        wait_for_job,
        get_output_video_filename,
        download_output_file,
        extract_second_to_last_frame,
        upload_image_to_comfy,
    )

    node_clip_image = node_overrides.get("node_clip_image", "57:27")
    node_ltx_motion = node_overrides.get("node_ltx_motion")  # None = image-only workflow
    node_ksampler = node_overrides.get("node_ksampler", "57:3")
    extra_noise_seeds = node_overrides.get("extra_noise_seeds") or []
    node_first_frame_input = node_overrides.get("node_first_frame_input", "267:238")
    node_frame_length = node_overrides.get("node_frame_length")
    frame_length_override = node_overrides.get("frame_length_override")

    print(f"\n[comfy] Pushing {len(scene_bundles)} scenes -> {comfy_url}")
    print(f"[comfy] Nodes: image={node_clip_image}  motion={node_ltx_motion}  ksampler={node_ksampler}  noise={extra_noise_seeds}")
    print(f"[comfy] Last-frame/first-frame: first_frame_input_node={node_first_frame_input}")

    tmp_dir = _Path("output/_tmp_frames")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    errors = 0
    first_frame_filename: str | None = None  # Set after scene 1 completes
    prev_image_prompt: str = ""              # Fallback if frame extraction fails

    for i, bundle in enumerate(scene_bundles):
        scene_id = bundle["scene_id"]
        style = bundle["style_tag"]
        is_first_scene = (i == 0)
        print(f"\n  [{i+1}/{len(scene_bundles)}] {scene_id}  [{style}]")

        if not is_first_scene:
            if first_frame_filename:
                print(f"  [last-frame] Using extracted frame: {first_frame_filename}")
            else:
                print(f"  [last-frame] Frame extraction failed — falling back to scene 1 image prompt.")

        try:
            # Scene 2+: use extracted frame if available, otherwise fall back to scene 1's prompt
            if is_first_scene:
                image_prompt = bundle["image_prompt"]
            elif first_frame_filename:
                image_prompt = ""  # LoadImage node handles the visual — skip SD3
            else:
                image_prompt = prev_image_prompt  # Fallback: reuse scene 1 prompt

            prompt_id = send_to_comfy_headless(
                image_prompt=image_prompt,
                video_prompt=bundle["video_prompt"],
                workflow_path=str(workflow_path),
                comfy_url=comfy_url,
                node_clip_image=node_clip_image,
                node_ltx_motion=node_ltx_motion,
                node_ksampler=node_ksampler,
                extra_noise_seeds=extra_noise_seeds,
                first_frame_filename=first_frame_filename if not is_first_scene else None,
                node_first_frame_input=node_first_frame_input,
                node_frame_length=node_frame_length,
                frame_length_override=frame_length_override,
            )
            print(f"  {scene_id}  queued -> {prompt_id}")

            if is_first_scene:
                prev_image_prompt = bundle["image_prompt"]

            # Wait for completion and extract the last frame for the next scene
            if node_ltx_motion is not None and i < len(scene_bundles) - 1:
                print(f"  Waiting for {scene_id} to finish before extracting last frame...")
                try:
                    history = wait_for_job(prompt_id, comfy_url)
                    video_filename = get_output_video_filename(history)
                    if video_filename:
                        video_path = download_output_file(video_filename, comfy_url, tmp_dir / f"{scene_id}.mp4")
                        frame_path = tmp_dir / f"{scene_id}_last_frame.png"
                        extract_second_to_last_frame(video_path, frame_path)
                        first_frame_filename = upload_image_to_comfy(frame_path, comfy_url)
                        print(f"  [last-frame] Ready for next scene: {first_frame_filename}")
                    else:
                        print(f"  [last-frame] WARNING: No video found in job output — next scene will use fallback image prompt.")
                        first_frame_filename = None
                except Exception as extract_exc:
                    print(f"  [last-frame] WARNING: Frame extraction failed ({extract_exc}) — next scene will use fallback image prompt.")
                    first_frame_filename = None

        except Exception as exc:
            print(f"  {scene_id}  ERROR  — {exc}", file=sys.stderr)
            errors += 1
            first_frame_filename = None

    if errors:
        print(f"\n[comfy] Done with {errors} error(s). Check output above.")
    else:
        print("\n[comfy] All scenes queued.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # 1. Health check — fail fast before heavy generation if ComfyUI is down
    workflow_path: Path | None = None
    if args.comfy:
        print(f"[health] Checking ComfyUI at {args.comfy_url} ...")
        if not check_comfy_health(args.comfy_url):
            raise SystemExit(
                f"Error: ComfyUI not reachable at {args.comfy_url}\n"
                "Start ComfyUI first, or omit --comfy to skip GPU rendering."
            )
        print("[health] ComfyUI is up.\n")
        workflow_path = resolve_workflow_path(args.workflow_type, args.workflow_path)
        # Load companion _nodes.json; CLI --node_* flags override if provided
        node_config = load_workflow_nodes(workflow_path)
        if args.node_clip_image != "6":   # user explicitly overrode the default
            node_config["node_clip_image"] = args.node_clip_image
        if args.node_ltx_motion != "12":
            node_config["node_ltx_motion"] = args.node_ltx_motion
        if args.node_ksampler != "3":
            node_config["node_ksampler"] = args.node_ksampler
        print(f"[workflow] {workflow_path}")
        print(f"[nodes]    {node_config}\n")

    # 2. Run orchestrator(s) and collect scene bundles
    scene_bundles: list[dict] = []

    if args.timeline == "prem":
        scene_bundles = run_premiere(args)

    elif args.timeline == "fcp":
        scene_bundles = run_fcp(args)

    elif args.timeline == "both":
        prem_bundles = run_premiere(args)
        fcp_bundles = run_fcp(args)
        # Prefer FCP bundles (richer prompts); fall back to prem if ad workflow skipped FCP
        scene_bundles = fcp_bundles or prem_bundles

    # 3. Push to ComfyUI
    if args.comfy:
        if not scene_bundles:
            print("[comfy] No scene bundles to send — skipping ComfyUI push.")
        else:
            push_to_comfy(
                scene_bundles=scene_bundles,
                workflow_path=workflow_path,  # type: ignore[arg-type]
                comfy_url=args.comfy_url,
                node_overrides=node_config,  # type: ignore[possibly-undefined]
            )

    print("\nDone.")


if __name__ == "__main__":
    main()
