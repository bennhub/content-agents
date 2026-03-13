# Future Implementation — Replacing z-image-turbo with Nano Banana API

## What This Is

This document outlines how to swap the **z-image-turbo static frame generation step**
in the current ComfyUI workflow for a direct call to the **Nano Banana API**.

This is not implemented yet. Use this as a build guide when the time comes.

---

## Current Flow

Right now, for each scene the pipeline does this:

```
scene bundle (image_prompt + video_prompt)
        |
        v
ComfyUI mv_workflow.json
  ├─ z-image-turbo node (57:27)   ← generates the static keyframe from image_prompt
  └─ LTX i2v nodes                ← animates the keyframe using video_prompt
        |
        v
rendered scene_XX.mp4
```

The `image_prompt` field in each scene bundle (the Nano Banana-formatted prompt from
`build_nano_banana_prompt()`) currently feeds into the z-image-turbo CLIP node inside
ComfyUI. The prompts are already written in the right style — the only change is WHERE
they get sent.

---

## What Changes With Nano Banana

Instead of ComfyUI generating the static frame internally, Nano Banana generates it
externally via API call. You then feed that image into the LTX i2v step as the
starting frame.

```
scene bundle (image_prompt + video_prompt)
        |
        ├─ image_prompt ──> Nano Banana API ──> keyframe.png (downloaded locally)
        |
        └─ video_prompt + keyframe.png ──> ComfyUI LTX i2v ──> scene_XX.mp4
```

---

## What Already Exists In The Codebase

The Nano Banana prompts are **already being generated**. Every scene bundle has:

```python
bundle["image_prompt"]  # this IS the Nano Banana prompt from build_nano_banana_prompt()
```

`build_nano_banana_prompt()` in `orchestrate_fcpxml.py` (line 445) produces a structured
cinematic still-frame description specifically designed for image generation models.
These prompts are already written into `prompts.txt` under `Nano Banana prompt:` for
every scene.

Nothing in the prompt pipeline needs to change — only the delivery mechanism.

---

## Implementation Plan

### Step 1 — Create `nano_banana_client.py`

New file alongside `comfy_client.py`. Responsible for:

1. Accepting an `image_prompt` string
2. POSTing to the Nano Banana API endpoint
3. Downloading the returned image to a local temp path
4. Returning the local file path

```python
def generate_keyframe(
    image_prompt: str,
    api_key: str,
    output_path: str,
    # add Nano Banana-specific params here (model, resolution, steps, etc.)
) -> str:
    """
    Send image_prompt to Nano Banana API, save result to output_path.
    Returns the saved file path.
    """
    ...
```

### Step 2 — Update the ComfyUI workflow

The current `mv_workflow.json` generates the static frame internally via z-image-turbo.
You need a version of the workflow where the starting frame comes from an external image
file instead — using a `LoadImage` node as the entry point.

Export this as `workflows/mv_workflow_ltx_only.json` (LTX i2v only, no image gen).

Update the node config file `workflows/mv_workflow_ltx_only_nodes.json`:

```json
{
  "node_clip_image": null,
  "node_ltx_motion": "267:266",
  "node_ksampler": "57:3",
  "node_load_image": "269",
  "extra_noise_seeds": ["267:216", "267:237"]
}
```

### Step 3 — Update `comfy_client.py`

Add an optional `input_image_path` parameter to `send_to_comfy_headless()`:

```python
def send_to_comfy_headless(
    ...
    input_image_path: str | None = None,  # path to pre-generated keyframe
    node_load_image: str | None = None,   # LoadImage node ID
) -> str:
    ...
    # If an external image is provided, upload it to ComfyUI and inject into LoadImage node
    if input_image_path and node_load_image:
        uploaded_name = upload_image_to_comfy(input_image_path, comfy_url)
        workflow[node_load_image]["inputs"]["image"] = uploaded_name
```

ComfyUI has a `/upload/image` endpoint for this:

```python
def upload_image_to_comfy(image_path: str, comfy_url: str) -> str:
    """Upload a local image to ComfyUI and return the filename it was saved as."""
    with open(image_path, "rb") as f:
        response = requests.post(
            f"{comfy_url}/upload/image",
            files={"image": f},
        )
    response.raise_for_status()
    return response.json()["name"]
```

### Step 4 — Update `run.py`

Add a `--nano_banana` flag and `--nano_banana_key` argument. The push loop becomes:

```python
if args.nano_banana:
    from nano_banana_client import generate_keyframe

    keyframe_path = generate_keyframe(
        image_prompt=bundle["image_prompt"],
        api_key=args.nano_banana_key,
        output_path=f"{output_dir}/keyframe_{bundle['scene_id']}.png",
    )
    # then send to LTX-only ComfyUI workflow with keyframe injected
    send_to_comfy_headless(
        image_prompt=bundle["image_prompt"],   # still passed for reference
        video_prompt=bundle["video_prompt"],
        workflow_path="workflows/mv_workflow_ltx_only.json",
        input_image_path=keyframe_path,
        node_load_image=node_config.get("node_load_image"),
        ...
    )
```

---

## Files To Create

| File | Purpose |
|---|---|
| `nano_banana_client.py` | API client — generates keyframe from image_prompt |
| `workflows/mv_workflow_ltx_only.json` | ComfyUI workflow starting from LoadImage (no z-image) |
| `workflows/mv_workflow_ltx_only_nodes.json` | Node config for the LTX-only workflow |

## Files To Modify

| File | Change |
|---|---|
| `comfy_client.py` | Add `input_image_path` + `node_load_image` params, add `upload_image_to_comfy()` |
| `run.py` | Add `--nano_banana` and `--nano_banana_key` flags, update push loop |

---

## Notes

- The `image_prompt` values in scene bundles are **already Nano Banana formatted** —
  `build_nano_banana_prompt()` was written specifically for this. No prompt changes needed.
- The `ad_workflow` path would need the same treatment if ads ever go to video.
- Store `NANO_BANANA_API_KEY` in a `.env` file and load with `python-dotenv` rather than
  passing it on the CLI.
- Keep `--comfy` (z-image internal) as the default path so nothing breaks while this is
  being built out.
