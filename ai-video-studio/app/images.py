"""Metinden kare (görsel) üretimi — tamamen yerel, ücretsiz modellerle."""
from __future__ import annotations

import random
from pathlib import Path

from . import config
from .drawing import mock_image

_TURBO_SIZES = {"16:9": (768, 432), "9:16": (432, 768), "1:1": (512, 512)}
_XL_SIZES = {"16:9": (1344, 768), "9:16": (768, 1344), "1:1": (1024, 1024)}

IMAGE_MODELS = {
    "sdxl-turbo": {
        "label": "SDXL Turbo — hızlı ve iyi (önerilen)",
        "repo": "stabilityai/sdxl-turbo",
        "xl": True, "steps": 4, "guidance": 0.0, "sizes": _TURBO_SIZES,
    },
    "sd-turbo": {
        "label": "SD Turbo — en hafif, en hızlı",
        "repo": "stabilityai/sd-turbo",
        "xl": False, "steps": 2, "guidance": 0.0, "sizes": _TURBO_SIZES,
    },
    "sdxl": {
        "label": "SDXL Base — en kaliteli, yavaş",
        "repo": "stabilityai/stable-diffusion-xl-base-1.0",
        "xl": True, "steps": 25, "guidance": 6.0, "sizes": _XL_SIZES,
    },
}


def image_size(model: str, aspect: str) -> tuple[int, int]:
    spec = IMAGE_MODELS.get(model, IMAGE_MODELS["sdxl-turbo"])
    return spec["sizes"].get(aspect, spec["sizes"]["16:9"])


def _loader(model: str):
    def load():
        import torch
        from diffusers import AutoencoderKL, AutoPipelineForText2Image

        spec = IMAGE_MODELS[model]
        dev = config.device()
        dtype = torch.float16 if dev in ("mps", "cuda") else torch.float32
        kwargs = {"torch_dtype": dtype}
        if dtype == torch.float16:
            kwargs["variant"] = "fp16"
        if spec["xl"] and dtype == torch.float16:
            # SDXL'in orijinal VAE'si fp16'da siyah kare üretir; düzeltilmiş sürüm.
            kwargs["vae"] = AutoencoderKL.from_pretrained(
                "madebyollin/sdxl-vae-fp16-fix", torch_dtype=dtype
            )
        pipe = AutoPipelineForText2Image.from_pretrained(spec["repo"], **kwargs)
        pipe = pipe.to(dev)
        pipe.enable_attention_slicing()  # 16 GB RAM için bellek tasarrufu
        pipe.set_progress_bar_config(disable=True)
        return pipe

    return load


def generate(
    prompt: str,
    negative: str,
    model: str,
    aspect: str,
    seed: int | None,
    out_path: Path,
    progress=None,
) -> int:
    """Kareyi üretip out_path'e PNG olarak kaydeder. Kullanılan seed'i döndürür."""
    if model not in IMAGE_MODELS:
        model = "sdxl-turbo"
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    size = image_size(model, aspect)
    spec = IMAGE_MODELS[model]

    if config.MOCK:
        import time

        for i in range(4):
            time.sleep(0.15)
            if progress:
                progress((i + 1) / 4)
        mock_image(prompt, size, seed).save(out_path)
        return seed

    import torch

    if progress:
        progress(0.0, "Görsel modeli yükleniyor (ilk seferde indirilir)…")
    pipe = config.get_model(f"image:{model}", _loader(model))
    steps = spec["steps"]

    def on_step(_pipe, step, _t, kwargs):
        if progress:
            progress((step + 1) / steps, f"Kare çiziliyor ({step + 1}/{steps})")
        return kwargs

    args = dict(
        prompt=prompt,
        width=size[0],
        height=size[1],
        num_inference_steps=steps,
        guidance_scale=spec["guidance"],
        generator=torch.Generator("cpu").manual_seed(seed),
        callback_on_step_end=on_step,
    )
    if spec["guidance"] > 1 and negative:
        args["negative_prompt"] = negative
    image = pipe(**args).images[0]
    image.save(out_path)
    return seed
