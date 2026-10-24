"""One offline image per process; exiting releases the diffusion model's memory."""
import argparse
import json
import os
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    import torch
    from diffusers import StableDiffusionPipeline
    request = json.loads((args.folder/"request.json").read_text(encoding="utf-8"))
    started = time.monotonic()
    torch.set_num_threads(4)
    # Load fp16 safetensors as float32 for this CPU. No pickle or remote code.
    pipe = StableDiffusionPipeline.from_pretrained(str(args.model), local_files_only=True,
        use_safetensors=True, variant="fp16", torch_dtype=torch.float32, low_cpu_mem_usage=True)
    pipe.to("cpu")
    pipe.enable_attention_slicing()
    pipe.enable_vae_tiling()
    token_count = len(pipe.tokenizer(request["resolved_prompt"], truncation=False).input_ids)
    max_tokens = pipe.tokenizer.model_max_length
    def progress(_pipe, step, timestep, kwargs):
        (args.folder/"progress.json").write_text(json.dumps({"step": step+1}), encoding="utf-8")
        return kwargs
    with torch.inference_mode():
        result = pipe(prompt=request["resolved_prompt"], height=512, width=512,
            num_inference_steps=request["steps"], guidance_scale=0.0,
            generator=torch.Generator("cpu").manual_seed(request["seed"]),
            callback_on_step_end=progress)
    result.images[0].save(args.folder/"raw.png")
    (args.folder/"result.json").write_text(json.dumps({"device": "cpu", "dtype": "float32",
        "elapsed_seconds": round(time.monotonic()-started, 2), "torch": torch.__version__,
        "width": 512, "height": 512, "steps": request["steps"], "guidance_scale": 0.0,
        "prompt_tokens": token_count, "max_prompt_tokens": max_tokens,
        "prompt_truncated": token_count > max_tokens}), encoding="utf-8")


if __name__ == "__main__":
    main()
