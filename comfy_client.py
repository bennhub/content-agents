"""
comfy_client.py — Headless ComfyUI client for content-agents pipeline.

Loads a workflow_api.json, injects prompts + a randomized seed, and POSTs
to a local ComfyUI server. Returns the queued prompt_id.

Usage:
    from comfy_client import send_to_comfy_headless

    prompt_id = send_to_comfy_headless(
        image_prompt="A cinematic still of city lights at night",
        video_prompt="Scene 01 | LTX 2.3 prompt | anticipation..."
    )

Prerequisites:
    pip install requests
    Export workflow_api.json from ComfyUI: Settings > Dev Mode > Save API Format
"""

import json
import random
import requests
from pathlib import Path


def send_to_comfy_headless(
    image_prompt: str,
    video_prompt: str,
    workflow_path: str = "workflow_api.json",
    comfy_url: str = "http://127.0.0.1:8188",
    node_clip_image: str = "6",
    node_ltx_motion: str = "12",
    node_ksampler: str = "3",
) -> str:
    """
    Load a ComfyUI workflow, inject prompts, randomize seed, and queue the job.

    Args:
        image_prompt:    Static/image description (injected into CLIP text node).
        video_prompt:    Motion/scene description (injected into LTX motion node).
        workflow_path:   Path to workflow_api.json exported from ComfyUI.
        comfy_url:       Base URL of the running ComfyUI server.
        node_clip_image: Node ID for the CLIP/image text input.
        node_ltx_motion: Node ID for the LTX motion text input.
        node_ksampler:   Node ID for KSampler (used to randomize seed).

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
    workflow[node_clip_image]["inputs"]["text"] = image_prompt

    # 3. Inject video/motion prompt
    workflow[node_ltx_motion]["inputs"]["text"] = video_prompt

    # 4. Randomize seed
    seed = random.randint(0, 2**32)
    try:
        workflow[node_ksampler]["inputs"]["seed"] = seed
    except KeyError:
        print(
            f"[comfy_client] WARNING: Node '{node_ksampler}' not found or has no 'seed' input. "
            "LTX 2.3 workflows often store the seed in a RandomNoise or EmptyLTXVLatent node. "
            "Pass the correct node ID via node_ksampler=<id>."
        )

    # 5. POST to ComfyUI
    payload = {"prompt": workflow}
    response = requests.post(f"{comfy_url}/prompt", json=payload)
    response.raise_for_status()

    # 6. Return prompt_id
    prompt_id = response.json()["prompt_id"]
    print(f"[comfy_client] Queued — prompt_id: {prompt_id}")
    return prompt_id


if __name__ == "__main__":
    # Quick smoke test — requires ComfyUI running and workflow_api.json present
    test_image_prompt = "A cinematic still of neon city streets at night, rain-slicked pavement"
    test_video_prompt = (
        "Scene 01 | LTX 2.3 | anticipation. "
        "Use feral, explosive movement. Handheld shaky cam. "
        "Neon reflections pulse. Cut to beat."
    )

    pid = send_to_comfy_headless(
        image_prompt=test_image_prompt,
        video_prompt=test_video_prompt,
    )
    print(f"Job queued with prompt_id: {pid}")
