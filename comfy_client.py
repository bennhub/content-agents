"""
comfy_client.py — Headless ComfyUI client for content-agents pipeline.

Loads a workflow JSON, injects prompts + randomized seeds, and POSTs
to a local ComfyUI server. Returns the queued prompt_id.

Usage:
    from comfy_client import send_to_comfy_headless

    prompt_id = send_to_comfy_headless(
        image_prompt="A cinematic still of city lights at night",
        video_prompt="Scene 01 | LTX 2.3 prompt | anticipation...",
        workflow_path="workflows/mv_workflow.json",
        node_clip_image="57:27",
        node_ltx_motion="267:266",
        node_ksampler="57:3",
        extra_noise_seeds=["267:216", "267:237"],
    )

Prerequisites:
    pip install requests
    Export workflow JSON from ComfyUI: Settings > Dev Mode > Save (API Format)
"""

import json
import random
import subprocess
import time
import requests
from pathlib import Path


def wait_for_job(prompt_id: str, comfy_url: str = "http://127.0.0.1:8188", timeout: int = 600, poll_interval: int = 5) -> dict:
    """
    Poll ComfyUI until the job completes. Returns the history entry for the prompt.

    Raises TimeoutError if the job doesn't finish within `timeout` seconds.
    """
    deadline = time.time() + timeout
    url = f"{comfy_url}/history/{prompt_id}"
    print(f"[comfy_client] Waiting for job {prompt_id} ...")
    while time.time() < deadline:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        history = resp.json()
        if prompt_id in history:
            print(f"[comfy_client] Job {prompt_id} complete.")
            return history[prompt_id]
        time.sleep(poll_interval)
    raise TimeoutError(f"ComfyUI job {prompt_id} did not finish within {timeout}s")


def get_output_video_filename(history_entry: dict) -> str | None:
    """
    Extract the first video output filename from a completed job's history entry.
    Returns the filename string, or None if no video output is found.
    """
    outputs = history_entry.get("outputs", {})
    print(f"[comfy_client] Scanning {len(outputs)} output nodes for video file...")
    video_extensions = (".mp4", ".webm", ".avi", ".mov", ".mkv")
    for node_id, node_outputs in outputs.items():
        for key in ("gifs", "videos", "files", "animated", "images"):
            for item in node_outputs.get(key, []):
                if isinstance(item, dict) and "filename" in item:
                    fname = item["filename"]
                    subfolder = item.get("subfolder", "")
                    if any(fname.lower().endswith(ext) for ext in video_extensions):
                        print(f"[comfy_client] Found video in node {node_id}['{key}']: {fname} (subfolder='{subfolder}')")
                        return item  # Return full item so caller has subfolder too
    print(f"[comfy_client] WARNING: No video output found. Node output keys: "
          f"{ {nid: list(v.keys()) for nid, v in outputs.items()} }")
    return None


def download_output_file(file_info: dict | str, comfy_url: str, dest_path: Path) -> Path:
    """Download a file from ComfyUI's output directory to dest_path.

    file_info can be a dict with 'filename'/'subfolder' keys (from get_output_video_filename)
    or a plain filename string for backwards compatibility.
    """
    if isinstance(file_info, dict):
        filename = file_info["filename"]
        subfolder = file_info.get("subfolder", "")
    else:
        filename = file_info
        subfolder = ""

    params = f"filename={filename}&type=output"
    if subfolder:
        params += f"&subfolder={subfolder}"
    url = f"{comfy_url}/view?{params}"
    resp = requests.get(url, timeout=60, stream=True)
    resp.raise_for_status()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with dest_path.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"[comfy_client] Downloaded {filename} -> {dest_path}")
    return dest_path


def extract_second_to_last_frame(video_path: Path, output_image_path: Path) -> Path:
    """
    Use ffmpeg to extract the 2nd-to-last frame from a video file.
    The extracted frame is saved as a PNG at output_image_path.
    """
    # Get the video's frame rate and duration via ffprobe
    probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,nb_frames",
        "-of", "json",
        str(video_path),
    ]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(probe_result.stdout)
    stream = probe_data["streams"][0]

    # Parse frame rate (e.g. "24000/1001")
    fps_parts = stream["r_frame_rate"].split("/")
    fps = int(fps_parts[0]) / int(fps_parts[1])

    nb_frames = int(stream.get("nb_frames", 0))
    if nb_frames < 2:
        # Fallback: grab frame 0.1s before the very end
        target_frame = 0
    else:
        target_frame = nb_frames - 2  # 0-indexed second-to-last

    timestamp = target_frame / fps

    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_image_path),
    ]
    subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
    print(f"[comfy_client] Extracted 2nd-to-last frame (frame {target_frame}) -> {output_image_path}")
    return output_image_path


def upload_image_to_comfy(image_path: Path, comfy_url: str = "http://127.0.0.1:8188") -> str:
    """
    Upload an image to ComfyUI's input directory.
    Returns the filename as stored by ComfyUI (use this in LoadImage nodes).
    """
    with image_path.open("rb") as f:
        resp = requests.post(
            f"{comfy_url}/upload/image",
            files={"image": (image_path.name, f, "image/png")},
            data={"overwrite": "true"},
            timeout=30,
        )
    resp.raise_for_status()
    stored_name = resp.json()["name"]
    print(f"[comfy_client] Uploaded {image_path.name} -> ComfyUI input/{stored_name}")
    return stored_name


def send_to_comfy_headless(
    image_prompt: str,
    video_prompt: str,
    workflow_path: str = "workflows/mv_workflow.json",
    comfy_url: str = "http://127.0.0.1:8188",
    node_clip_image: str = "57:27",
    node_ltx_motion: str | None = "267:266",
    node_ksampler: str = "57:3",
    extra_noise_seeds: list[str] | None = None,
    first_frame_filename: str | None = None,
    node_first_frame_input: str | None = "267:238",
    node_frame_length: str | None = None,
    frame_length_override: int | None = None,
) -> str:
    """
    Load a ComfyUI workflow, inject prompts, randomize seeds, and queue the job.

    Args:
        image_prompt:           Static frame description → CLIP/image text node.
        video_prompt:           Motion description → LTX video text node (skipped if None).
        workflow_path:          Path to workflow JSON exported from ComfyUI.
        comfy_url:              Base URL of the running ComfyUI server.
        node_clip_image:        Node ID for the image/CLIP text input.
        node_ltx_motion:        Node ID for the LTX motion text input. Pass None for
                                image-only workflows (e.g. ad_workflow.json).
        node_ksampler:          Node ID for KSampler seed randomization.
        extra_noise_seeds:      Additional node IDs with a 'noise_seed' input to
                                randomize (e.g. RandomNoise nodes in LTX pipelines).
        first_frame_filename:   If provided, injects a LoadImage node into the workflow
                                and rewires node_first_frame_input to use it as the
                                starting frame (last-frame/first-frame workflow).
        node_first_frame_input: Node ID whose 'input' connection gets rewired to the
                                injected LoadImage node when first_frame_filename is set.

    Returns:
        prompt_id string returned by ComfyUI.
    """
    # 1. Load workflow
    wf_path = Path(workflow_path)
    if not wf_path.exists():
        raise FileNotFoundError(
            f"Workflow file not found: {wf_path.resolve()}\n"
            "Export it from ComfyUI: Settings > Dev Mode > Save (API Format)"
        )

    with wf_path.open() as f:
        workflow = json.load(f)

    # 2. Inject image prompt
    if node_clip_image not in workflow:
        raise KeyError(
            f"Node '{node_clip_image}' not found in workflow. "
            "Check node_clip_image in your workflow _nodes.json config."
        )
    workflow[node_clip_image]["inputs"]["text"] = image_prompt

    # 3. Inject video/motion prompt (skip for image-only workflows)
    if node_ltx_motion is not None:
        if node_ltx_motion not in workflow:
            print(
                f"[comfy_client] WARNING: LTX motion node '{node_ltx_motion}' not found. "
                "Skipping video prompt injection."
            )
        else:
            node = workflow[node_ltx_motion]
            key = "text" if "text" in node["inputs"] else "value"
            node["inputs"][key] = video_prompt

    # 4a. Override frame length (for faster test renders)
    if node_frame_length and frame_length_override is not None:
        if node_frame_length in workflow:
            workflow[node_frame_length]["inputs"]["value"] = frame_length_override
            print(f"[comfy_client] Frame length set to {frame_length_override} frames (~{frame_length_override/24:.1f}s)")

    # 4b. Inject first-frame image (last-frame/first-frame workflow)
    if first_frame_filename and node_first_frame_input:
        load_node_id = "_first_frame_loader"
        workflow[load_node_id] = {
            "inputs": {"image": first_frame_filename, "upload": "image"},
            "class_type": "LoadImage",
            "_meta": {"title": "First Frame Loader"},
        }
        if node_first_frame_input in workflow:
            workflow[node_first_frame_input]["inputs"]["input"] = [load_node_id, 0]
            print(f"[comfy_client] First-frame injected: {first_frame_filename} -> node {node_first_frame_input}")
        else:
            print(f"[comfy_client] WARNING: node_first_frame_input '{node_first_frame_input}' not found. Skipping first-frame injection.")

    # 4. Randomize KSampler seed
    seed = random.randint(0, 2**32)
    if node_ksampler in workflow and "seed" in workflow[node_ksampler]["inputs"]:
        workflow[node_ksampler]["inputs"]["seed"] = seed
    else:
        print(
            f"[comfy_client] WARNING: KSampler node '{node_ksampler}' not found or "
            "has no 'seed' input. Seed not randomized for this node."
        )

    # 5. Randomize extra noise seed nodes (e.g. RandomNoise in LTX pipelines)
    for noise_node_id in (extra_noise_seeds or []):
        if noise_node_id in workflow:
            inp = workflow[noise_node_id]["inputs"]
            if "noise_seed" in inp:
                inp["noise_seed"] = random.randint(0, 2**32)
            elif "seed" in inp:
                inp["seed"] = random.randint(0, 2**32)

    # 6. POST to ComfyUI
    payload = {"prompt": workflow}
    response = requests.post(f"{comfy_url}/prompt", json=payload)
    response.raise_for_status()

    # 7. Return prompt_id
    prompt_id = response.json()["prompt_id"]
    print(f"[comfy_client] Queued — prompt_id: {prompt_id}")
    return prompt_id


if __name__ == "__main__":
    # Quick smoke test — requires ComfyUI running and workflows/mv_workflow.json present
    test_image_prompt = "A cinematic still of neon city streets at night, rain-slicked pavement"
    test_video_prompt = (
        "Scene 01 | LTX 2.3 | anticipation. "
        "Use feral, explosive movement. Handheld shaky cam. "
        "Neon reflections pulse. Cut to beat."
    )

    pid = send_to_comfy_headless(
        image_prompt=test_image_prompt,
        video_prompt=test_video_prompt,
        workflow_path="workflows/mv_workflow.json",
        node_clip_image="57:27",
        node_ltx_motion="267:266",
        node_ksampler="57:3",
        extra_noise_seeds=["267:216", "267:237"],
    )
    print(f"Job queued with prompt_id: {pid}")
