"""Kareyi gerçek AI hareketiyle videoya çevirir (LTX-Video, image-to-video).

16 GB RAM'e sığması için iki aşamada çalışır:
  1. Metin kodlayıcı (T5, büyük) yüklenir, tüm sahnelerin istemleri kodlanır, bellekten atılır.
  2. Video modeli (2B parametre) yüklenir ve her sahne için klip üretilir.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from . import config

LTX_REPO = "Lightricks/LTX-Video"
FPS = 24

# Genişlik/yükseklik 32'nin katı olmalı.
QUALITY_SIZES = {
    "low": {"16:9": (512, 288), "9:16": (288, 512), "1:1": (384, 384)},
    "medium": {"16:9": (704, 384), "9:16": (384, 704), "1:1": (512, 512)},
}

DEFAULT_NEGATIVE = "worst quality, inconsistent motion, blurry, jittery, distorted"


def frame_count(seconds: float) -> int:
    # LTX: kare sayısı 8k+1 olmalı
    n = max(9, int(round(seconds * FPS)))
    return (n - 1) // 8 * 8 + 1


def cover_resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    w, h = size
    scale = max(w / img.width, h / img.height)
    nw, nh = round(img.width * scale), round(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    x, y = (nw - w) // 2, (nh - h) // 2
    return img.crop((x, y, x + w, y + h))


def encode_prompts(prompts: list[str], negative: str, progress=None) -> list[tuple]:
    import torch
    from diffusers import LTXImageToVideoPipeline

    config.release_models()
    if progress:
        progress(0.0, "Metin kodlayıcı yükleniyor (ilk seferde büyük indirme)…")
    pipe = LTXImageToVideoPipeline.from_pretrained(
        LTX_REPO, transformer=None, vae=None, torch_dtype=torch.bfloat16
    )
    # T5 ~9 GB: GPU bellek sınırına takılmasın diye CPU'da çalıştırılır (biraz yavaş, güvenli).
    enc_device = "cpu"
    out = []
    try:
        with torch.no_grad():
            for i, p in enumerate(prompts):
                if progress:
                    progress(i / len(prompts), f"İstemler kodlanıyor ({i + 1}/{len(prompts)})")
                pe, pm, ne, nm = pipe.encode_prompt(
                    prompt=p,
                    negative_prompt=negative or DEFAULT_NEGATIVE,
                    do_classifier_free_guidance=True,
                    num_videos_per_prompt=1,
                    max_sequence_length=128,
                    device=enc_device,
                )
                out.append(tuple(t.to("cpu") for t in (pe, pm, ne, nm)))
    finally:
        del pipe
        config.free_memory()
    return out


def _load_video_pipe():
    import torch
    from diffusers import LTXImageToVideoPipeline

    pipe = LTXImageToVideoPipeline.from_pretrained(
        LTX_REPO, text_encoder=None, tokenizer=None, torch_dtype=torch.bfloat16
    )
    pipe = pipe.to(config.device())
    try:
        pipe.vae.enable_tiling()  # kod çözme sırasında bellek tasarrufu
    except Exception:
        pass
    pipe.set_progress_bar_config(disable=True)
    return pipe


def animate(
    image_path: Path,
    embeds: tuple,
    aspect: str,
    quality: str,
    seconds: float,
    steps: int,
    seed: int,
    out_path: Path,
    progress=None,
) -> None:
    import imageio.v2 as imageio
    import numpy as np
    import torch

    size = QUALITY_SIZES.get(quality, QUALITY_SIZES["low"]).get(aspect, (512, 288))
    pipe = config.get_model("video:ltx", _load_video_pipe)
    dev = config.device()
    pe, pm, ne, nm = (t.to(dev) for t in embeds)
    image = cover_resize(Image.open(image_path).convert("RGB"), size)

    def on_step(_pipe, step, _t, kwargs):
        if progress:
            progress((step + 1) / (steps + 1), f"Hareket üretiliyor ({step + 1}/{steps})")
        return kwargs

    frames = pipe(
        image=image,
        prompt_embeds=pe,
        prompt_attention_mask=pm,
        negative_prompt_embeds=ne,
        negative_prompt_attention_mask=nm,
        width=size[0],
        height=size[1],
        num_frames=frame_count(seconds),
        frame_rate=FPS,
        num_inference_steps=steps,
        guidance_scale=3.0,
        decode_timestep=0.03,
        decode_noise_scale=0.025,
        generator=torch.Generator("cpu").manual_seed(seed),
        callback_on_step_end=on_step,
    ).frames[0]

    with imageio.get_writer(
        out_path, fps=FPS, codec="libx264", quality=9, pixelformat="yuv420p", macro_block_size=1
    ) as w:
        for f in frames:
            w.append_data(np.asarray(f.convert("RGB")))
