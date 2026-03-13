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
import requests
from pathlib import Path


def send_to_comfy_headless(
    image_prompt: str,
    video_prompt: str,
    workflow_path: str = "workflows/mv_workflow.json",
    comfy_url: str = "http://127.0.0.1:8188",
    node_clip_image: str = "57:27",
    node_ltx_motion: str | None = "267:266",
    node_ksampler: str = "57:3",
    extra_noise_seeds: list[str] | None = None,
) -> str:
    """
    Load a ComfyUI workflow, inject prompts, randomize seeds, and queue the job.

    Args:
        image_prompt:       Static frame description → CLIP/image text node.
        video_prompt:       Motion description → LTX video text node (skipped if None).
        workflow_path:      Path to workflow JSON exported from ComfyUI.
        comfy_url:          Base URL of the running ComfyUI server.
        node_clip_image:    Node ID for the image/CLIP text input.
        node_ltx_motion:    Node ID for the LTX motion text input. Pass None for
                            image-only workflows (e.g. ad_workflow.json).
        node_ksampler:      Node ID for KSampler seed randomization.
        extra_noise_seeds:  Additional node IDs with a 'noise_seed' input to
                            randomize (e.g. RandomNoise nodes in LTX pipelines).

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
