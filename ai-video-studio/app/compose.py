"""Kareleri / klipleri tek bir MP4'te birleştirir.

- Hızlı mod: her kareye kamera hareketi (yakınlaşma, kaydırma) uygulanır.
- AI mod: LTX'in ürettiği klipler kullanılır.
- Sahneler arasında yumuşak geçiş, isteğe bağlı altyazı ve müzik.
Kareler akış halinde yazılır; uzun videolar bile belleği doldurmaz.
"""
from __future__ import annotations

import collections
import subprocess
from pathlib import Path
from typing import Iterator

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image

from .drawing import caption_overlay

RESOLUTIONS = {
    "480p": {"16:9": (848, 480), "9:16": (480, 848), "1:1": (480, 480)},
    "720p": {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (720, 720)},
    "1080p": {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)},
}

EFFECTS = ["zoom_in", "pan_right", "zoom_out", "pan_left", "pan_up", "pan_down"]
ALL_EFFECTS = EFFECTS + ["static"]


def output_size(resolution: str, aspect: str) -> tuple[int, int]:
    return RESOLUTIONS.get(resolution, RESOLUTIONS["720p"]).get(aspect, (1280, 720))


def _ease(t: float) -> float:
    return t * t * (3 - 2 * t)  # smoothstep


def kenburns(image_path: Path, size: tuple[int, int], frames: int, effect: str) -> Iterator[Image.Image]:
    W, H = size
    src = Image.open(image_path).convert("RGB")
    # Kaynağı çıktının ~1.35 katı kaplayacak şekilde ölçekle (kaliteli ve hızlı kırpma için)
    s = max(W / src.width, H / src.height) * 1.35
    src = src.resize((max(1, round(src.width * s)), max(1, round(src.height * s))), Image.LANCZOS)
    iw, ih = src.size
    base = max(W / iw, H / ih)  # z=1 iken pencere tüm görüntüyü kaplar

    for i in range(frames):
        t = _ease(i / max(1, frames - 1))
        if effect == "zoom_in":
            z, fx, fy = 1.0 + 0.18 * t, 0.5, 0.5
        elif effect == "zoom_out":
            z, fx, fy = 1.18 - 0.18 * t, 0.5, 0.5
        elif effect == "pan_right":
            z, fx, fy = 1.15, t, 0.5
        elif effect == "pan_left":
            z, fx, fy = 1.15, 1 - t, 0.5
        elif effect == "pan_down":
            z, fx, fy = 1.15, 0.5, t
        elif effect == "pan_up":
            z, fx, fy = 1.15, 0.5, 1 - t
        else:
            z, fx, fy = 1.0, 0.5, 0.5
        cw, ch = W / base / z, H / base / z
        x0 = (iw - cw) * fx
        y0 = (ih - ch) * fy
        yield src.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def clip_frames(clip_path: Path, size: tuple[int, int]) -> Iterator[Image.Image]:
    W, H = size
    reader = imageio.get_reader(clip_path)
    try:
        for arr in reader:
            img = Image.fromarray(arr).convert("RGB")
            s = max(W / img.width, H / img.height)
            nw, nh = round(img.width * s), round(img.height * s)
            img = img.resize((nw, nh), Image.BICUBIC)
            x, y = (nw - W) // 2, (nh - H) // 2
            yield img.crop((x, y, x + W, y + H))
    finally:
        reader.close()


def count_clip_frames(clip_path: Path) -> int:
    reader = imageio.get_reader(clip_path)
    try:
        n = reader.count_frames()
    finally:
        reader.close()
    return n


def _with_caption(frames: Iterator[Image.Image], overlay: Image.Image | None) -> Iterator[np.ndarray]:
    for f in frames:
        if overlay is not None:
            f = Image.alpha_composite(f.convert("RGBA"), overlay).convert("RGB")
        yield np.asarray(f)


def render(
    segments: list[dict],
    size: tuple[int, int],
    fps: int,
    fade_seconds: float,
    out_path: Path,
    music_path: Path | None = None,
    progress=None,
) -> float:
    """segments: [{"image": Path, "clip": Path|None, "seconds": float, "effect": str, "caption": str}]

    Videonun süresini (sn) döndürür.
    """
    if not segments:
        raise ValueError("Videoya eklenecek sahne yok")

    # her segmentin kare sayısı
    plans = []
    for i, seg in enumerate(segments):
        effect = seg.get("effect") or "auto"
        if effect == "auto" or effect not in ALL_EFFECTS:
            effect = EFFECTS[i % len(EFFECTS)]
        if seg.get("clip"):
            n = count_clip_frames(seg["clip"])
        else:
            n = max(2, int(round(seg["seconds"] * fps)))
        plans.append((seg, effect, n))

    min_len = min(n for _, _, n in plans)
    fade = int(round(fade_seconds * fps))
    fade = max(0, min(fade, min_len // 2))
    total = sum(n for _, _, n in plans) - fade * (len(plans) - 1)

    tmp = out_path.with_name(out_path.stem + ".video.mp4")
    writer = imageio.get_writer(
        tmp, fps=fps, codec="libx264", quality=8, pixelformat="yuv420p",
        macro_block_size=1, ffmpeg_params=["-preset", "medium", "-movflags", "+faststart"],
    )
    written = 0

    def write(arr: np.ndarray) -> None:
        nonlocal written
        writer.append_data(arr)
        written += 1
        if progress and written % 6 == 0:
            progress(written / total, f"Video birleştiriliyor ({written}/{total} kare)")

    try:
        tail: list[np.ndarray] = []
        for seg, effect, n in plans:
            overlay = caption_overlay(size, seg.get("caption", ""))
            if seg.get("clip"):
                frames = clip_frames(seg["clip"], size)
            else:
                frames = kenburns(seg["image"], size, n, effect)
            stream = _with_caption(frames, overlay)

            # önceki sahnenin son karelerini bu sahnenin ilk kareleriyle harmanla
            for k, prev in enumerate(tail):
                cur = next(stream, None)
                if cur is None:
                    break
                a = (k + 1) / (len(tail) + 1)
                write((prev.astype(np.float32) * (1 - a) + cur.astype(np.float32) * a).astype(np.uint8))

            held: collections.deque = collections.deque()
            for arr in stream:
                held.append(arr)
                if len(held) > fade:
                    write(held.popleft())
            tail = list(held)
        for arr in tail:
            write(arr)
    finally:
        writer.close()

    duration = written / fps
    if music_path and music_path.exists():
        if progress:
            progress(0.99, "Müzik ekleniyor")
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        fade_out = min(2.0, duration / 3)
        cmd = [
            ffmpeg, "-y", "-loglevel", "error",
            "-i", str(tmp), "-stream_loop", "-1", "-i", str(music_path),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-af", f"afade=t=in:st=0:d=0.5,afade=t=out:st={max(0.0, duration - fade_out):.2f}:d={fade_out:.2f}",
            "-t", f"{duration:.3f}", "-movflags", "+faststart", str(out_path),
        ]
        subprocess.run(cmd, check=True)
        tmp.unlink(missing_ok=True)
    else:
        tmp.replace(out_path)
    return duration
