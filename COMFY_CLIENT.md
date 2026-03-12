# comfy_client.py — How It Works & How to Run It

## What It Does

`comfy_client.py` is the bridge between the prompt generation pipeline and your GPU.

The overall flow is:

```
lyrics + BPM
    → orchestrate_splurge.py  (generates scene prompts + XML timeline)
    → comfy_client.py         (sends prompts to ComfyUI → video files rendered on GPU)
```

Instead of you manually copy-pasting prompts into ComfyUI, this script does it automatically — it loads your saved ComfyUI workflow, swaps in the new prompts, randomizes the seed so each render is unique, and queues the job via ComfyUI's HTTP API.

---

## How It Works (Step by Step)

1. **Loads `workflow_api.json`** — this is your ComfyUI workflow exported in API format. It contains every node and connection in your graph.

2. **Injects the image prompt** into the CLIP text node (default node ID `"6"`). This is your static scene description.

3. **Injects the video/motion prompt** into the LTX motion node (default node ID `"12"`). This drives the movement and energy of the clip.

4. **Randomizes the seed** on the KSampler node (default node ID `"3"`). This ensures every generation is different. If the seed lives in a `RandomNoise` or `EmptyLTXVLatent` node instead (common in LTX 2.3 workflows), it prints a warning and you can pass the correct node ID manually.

5. **POSTs the workflow** to `http://127.0.0.1:8188/prompt` — ComfyUI's local API endpoint.

6. **Returns the `prompt_id`** — a unique ID you can use to track the job in the ComfyUI UI.

---

## Prerequisites

### 1. Install the dependency

```bash
pip install requests
```

### 2. Have ComfyUI running

ComfyUI must be running locally before you call this script. Start it with:

```bash
python main.py
```

Then confirm it's accessible at `http://127.0.0.1:8188` in your browser.

### 3. Export your workflow in API format

1. Open ComfyUI in your browser
2. Go to **Settings** (gear icon)
3. Enable **Dev Mode**
4. Back in the graph, click **Save (API Format)**
5. Save the file as `workflow_api.json` in the same folder as `comfy_client.py`

> **Important:** This must be the **API format**, not the regular save. The regular save produces a different JSON structure that this script cannot read.

---

## Running the Smoke Test

Once ComfyUI is running and `workflow_api.json` is in place:

```bash
python comfy_client.py
```

If everything is wired up correctly you'll see:

```
[comfy_client] Queued — prompt_id: abc123-xxxx-xxxx-xxxx
Job queued with prompt_id: abc123-xxxx-xxxx-xxxx
```

Then check the ComfyUI browser UI — you should see the job in the queue.

---

## Using It from the Main Pipeline

```python
from comfy_client import send_to_comfy_headless

prompt_id = send_to_comfy_headless(
    image_prompt="A cinematic still of city lights at night",
    video_prompt="Scene 01 | LTX 2.3 | anticipation. Use feral, explosive movement..."
)
```

---

## Function Parameters

| Parameter | Default | Description |
|---|---|---|
| `image_prompt` | required | Static scene description (CLIP text node) |
| `video_prompt` | required | Motion/energy description (LTX motion node) |
| `workflow_path` | `"workflow_api.json"` | Path to your exported workflow |
| `comfy_url` | `"http://127.0.0.1:8188"` | ComfyUI server URL |
| `node_clip_image` | `"6"` | Node ID for image prompt input |
| `node_ltx_motion` | `"12"` | Node ID for video/motion prompt input |
| `node_ksampler` | `"3"` | Node ID for seed randomization |

---

## Finding Your Node IDs

The default node IDs (`"6"`, `"12"`, `"3"`) may not match your workflow. To find the correct ones:

1. Open `workflow_api.json` in a text editor
2. Search for the text field where your image description goes — the parent key (e.g. `"6"`) is the node ID
3. Do the same for the motion prompt and seed fields
4. Pass the correct IDs when calling the function:

```python
send_to_comfy_headless(
    image_prompt="...",
    video_prompt="...",
    node_clip_image="42",
    node_ltx_motion="17",
    node_ksampler="9",
)
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `FileNotFoundError: workflow_api.json not found` | Export the workflow from ComfyUI in API format and place it next to `comfy_client.py` |
| `Connection refused` on port 8188 | ComfyUI is not running — start it first |
| `WARNING: Node '3' not found` | Your seed is in a different node — check `workflow_api.json` for the `RandomNoise` or `EmptyLTXVLatent` node ID |
| Job queued but nothing renders | Check the ComfyUI UI for error messages in the queue |
