"""AI Video Stüdyo — yerel web sunucusu (http://127.0.0.1:8765)."""
from __future__ import annotations

import hashlib
import io
import random
import time

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from . import compose, config, images, jobs, projects
from .translate import to_english

app = FastAPI(title="AI Video Stüdyo")


# ---------------------------------------------------------------------------
# yardımcılar
# ---------------------------------------------------------------------------
def _load(pid: str) -> dict:
    try:
        return projects.load(pid)
    except KeyError:
        raise HTTPException(404, "Proje bulunamadı")


def _stage(job: jobs.Job, start: float, end: float):
    """İşin bir aşamasının ilerlemesini genel ilerlemeye eşler."""

    def progress(p: float, message: str | None = None) -> None:
        job.update(start + (end - start) * p, message)

    return progress


def _build_prompt(p: dict, scene: dict) -> str:
    parts = []
    if p.get("translate"):
        parts.append(to_english(scene["prompt"]))
        if p.get("style"):
            parts.append(to_english(p["style"]))
    else:
        parts += [scene["prompt"], p.get("style", "")]
    return ", ".join(x.strip() for x in parts if x and x.strip())


def _motion_prompt(p: dict, scene: dict) -> str:
    text = scene.get("motion") or scene["prompt"]
    return to_english(text) if p.get("translate") else text


def _ts() -> int:
    return int(time.time() * 1000)


def _generate_scene_image(job, pid: str, sid: str, new_seed: bool, progress) -> None:
    p = projects.load(pid)
    scene = projects.get_scene(p, sid)
    if not scene["prompt"].strip():
        raise ValueError("Sahnenin istemi boş — önce ne görmek istediğini yaz.")
    progress(0.0, "İstem hazırlanıyor")
    prompt = _build_prompt(p, scene)
    seed = None if new_seed else scene.get("seed")
    rel = f"frames/{sid}_{_ts()}.png"
    used = images.generate(
        prompt, p.get("negative", ""), p["image_model"], p["aspect"], seed,
        projects.project_dir(pid) / rel, progress,
    )
    projects.set_scene_fields(pid, sid, image=rel, seed=used, clip=None, clip_key=None,
                              used_prompt=prompt)


# ---------------------------------------------------------------------------
# durum
# ---------------------------------------------------------------------------
@app.get("/api/status")
def status():
    return {
        "mock": config.MOCK,
        "device": config.device(),
        "image_models": {k: v["label"] for k, v in images.IMAGE_MODELS.items()},
        "effects": compose.ALL_EFFECTS,
        "resolutions": list(compose.RESOLUTIONS),
    }


# ---------------------------------------------------------------------------
# projeler
# ---------------------------------------------------------------------------
@app.get("/api/projects")
def list_projects():
    return projects.list_all()


@app.post("/api/projects")
def create_project(body: dict | None = None):
    return projects.create((body or {}).get("title", "Yeni proje"))


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    return _load(pid)


@app.put("/api/projects/{pid}")
def update_project(pid: str, body: dict):
    _load(pid)
    return projects.update_from_client(pid, body)


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    _load(pid)
    projects.delete(pid)
    return {"ok": True}


# ---------------------------------------------------------------------------
# kareler
# ---------------------------------------------------------------------------
@app.post("/api/projects/{pid}/scenes/{sid}/image")
def generate_image(pid: str, sid: str, body: dict | None = None):
    p = _load(pid)
    try:
        scene = projects.get_scene(p, sid)
    except KeyError:
        raise HTTPException(404, "Sahne bulunamadı")
    new_seed = bool((body or {}).get("new_seed", True))
    idx = p["scenes"].index(scene) + 1

    def run(job):
        _generate_scene_image(job, pid, sid, new_seed, _stage(job, 0, 1))
        return {"scene": sid}

    return jobs.submit("image", pid, f"Sahne {idx} karesi", run).to_dict()


@app.post("/api/projects/{pid}/images")
def generate_all_images(pid: str, body: dict | None = None):
    _load(pid)
    only_missing = bool((body or {}).get("only_missing", True))

    def run(job):
        p = projects.load(pid)
        todo = [s["id"] for s in p["scenes"]
                if s["prompt"].strip() and (not only_missing or not s.get("image"))]
        for i, sid in enumerate(todo):
            stage = _stage(job, i / len(todo), (i + 1) / len(todo))
            stage(0, f"Kare {i + 1}/{len(todo)}")
            _generate_scene_image(job, pid, sid, True,
                                  lambda q, m=None, st=stage, i=i: st(q, f"Kare {i + 1}/{len(todo)}: {m or ''}"))
        return {"count": len(todo)}

    return jobs.submit("images", pid, "Tüm kareler", run).to_dict()


@app.post("/api/projects/{pid}/scenes/{sid}/upload")
async def upload_image(pid: str, sid: str, file: UploadFile = File(...)):
    p = _load(pid)
    try:
        projects.get_scene(p, sid)
    except KeyError:
        raise HTTPException(404, "Sahne bulunamadı")
    data = await file.read()
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Bu dosya bir görsel değil")
    rel = f"frames/{sid}_{_ts()}.png"
    img.save(projects.project_dir(pid) / rel)
    return projects.set_scene_fields(pid, sid, image=rel, clip=None, clip_key=None)


# ---------------------------------------------------------------------------
# müzik
# ---------------------------------------------------------------------------
_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


@app.post("/api/projects/{pid}/music")
async def upload_music(pid: str, file: UploadFile = File(...)):
    p = _load(pid)
    name = (file.filename or "").lower()
    ext = name[name.rfind("."):] if "." in name else ""
    if ext not in _AUDIO_EXT:
        raise HTTPException(400, "Desteklenen ses dosyaları: " + ", ".join(sorted(_AUDIO_EXT)))
    if p.get("music"):
        (projects.project_dir(pid) / p["music"]).unlink(missing_ok=True)
    rel = f"music{ext}"
    (projects.project_dir(pid) / rel).write_bytes(await file.read())
    return projects.set_fields(pid, music=rel, music_name=file.filename)


@app.delete("/api/projects/{pid}/music")
def delete_music(pid: str):
    p = _load(pid)
    if p.get("music"):
        (projects.project_dir(pid) / p["music"]).unlink(missing_ok=True)
    return projects.set_fields(pid, music=None, music_name=None)


# ---------------------------------------------------------------------------
# video
# ---------------------------------------------------------------------------
def _clip_key(p: dict, scene: dict) -> str:
    v = p["video"]
    raw = "|".join(str(x) for x in (
        scene.get("image"), _motion_prompt(p, scene), p["aspect"], v["ai_quality"],
        v["ai_seconds"], v["ai_steps"], config.MOCK,
    ))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _make_ai_clips(job, pid: str, progress) -> None:
    from . import video_ai

    p = projects.load(pid)
    v = p["video"]
    need = [s for s in p["scenes"] if s.get("image") and
            not (s.get("clip") and s.get("clip_key") == _clip_key(p, s)
                 and projects.file_path(pid, s["clip"]).exists())]
    if not need:
        return
    seconds = float(v["ai_seconds"])
    steps = int(v["ai_steps"])

    if config.MOCK:  # AI yoksa: hareketli sahte klip
        import imageio.v2 as imageio
        import numpy as np

        size = video_ai.QUALITY_SIZES["low"][p["aspect"]]
        for i, s in enumerate(need):
            progress(i / len(need), f"(mock) Klip {i + 1}/{len(need)}")
            rel = f"clips/{s['id']}_{_ts()}.mp4"
            with imageio.get_writer(projects.project_dir(pid) / rel, fps=video_ai.FPS,
                                    codec="libx264", pixelformat="yuv420p", macro_block_size=1) as w:
                for f in compose.kenburns(projects.file_path(pid, s["image"]), size,
                                          video_ai.frame_count(seconds), "zoom_in"):
                    w.append_data(np.asarray(f))
            projects.set_scene_fields(pid, s["id"], clip=rel, clip_key=_clip_key(p, s))
        return

    prompts = [_motion_prompt(p, s) for s in need]
    embeds = video_ai.encode_prompts(prompts, "", lambda q, m=None: progress(0.1 * q, m))
    for i, (s, emb) in enumerate(zip(need, embeds)):
        lo = 0.1 + 0.9 * i / len(need)
        hi = 0.1 + 0.9 * (i + 1) / len(need)

        def sub(q, m=None, lo=lo, hi=hi, i=i):
            progress(lo + (hi - lo) * q, f"Klip {i + 1}/{len(need)}: {m or ''}")

        sub(0, "Video modeli yükleniyor…")
        rel = f"clips/{s['id']}_{_ts()}.mp4"
        video_ai.animate(
            projects.file_path(pid, s["image"]), emb, p["aspect"], v["ai_quality"], seconds,
            steps, s.get("seed") or random.randint(0, 2**31 - 1),
            projects.project_dir(pid) / rel, sub,
        )
        projects.set_scene_fields(pid, s["id"], clip=rel, clip_key=_clip_key(p, s))


@app.post("/api/projects/{pid}/render")
def render(pid: str, body: dict | None = None):
    p = _load(pid)
    if body:
        projects.update_from_client(pid, body)
        p = projects.load(pid)
    mode = p["video"]["mode"]

    def run(job):
        # 1) eksik kareleri üret
        p = projects.load(pid)
        missing = [s["id"] for s in p["scenes"] if s["prompt"].strip() and not s.get("image")]
        img_end = 0.3 if missing else 0.0
        for i, sid in enumerate(missing):
            stage = _stage(job, img_end * i / len(missing), img_end * (i + 1) / len(missing))
            _generate_scene_image(job, pid, sid, True,
                                  lambda q, m=None, st=stage, i=i: st(q, f"Eksik kare {i + 1}/{len(missing)}"))

        # 2) AI modunda klipleri üret
        clip_end = img_end
        if mode == "ai":
            clip_end = img_end + (1 - img_end) * 0.85
            _make_ai_clips(job, pid, _stage(job, img_end, clip_end))
            config.release_models()

        # 3) birleştir
        p = projects.load(pid)
        v = p["video"]
        segments = []
        for s in p["scenes"]:
            if not s.get("image"):
                continue
            seg = {
                "image": projects.file_path(pid, s["image"]),
                "clip": projects.file_path(pid, s.get("clip")) if mode == "ai" else None,
                "seconds": float(v["seconds"]),
                "effect": s.get("effect", "auto"),
                "caption": s.get("caption", "") if v.get("captions", True) else "",
            }
            if seg["clip"] is not None and not seg["clip"].exists():
                seg["clip"] = None
            segments.append(seg)
        if not segments:
            raise ValueError("Hiç kare yok. Önce sahnelere istem yazıp kare üret.")

        rel = f"output_{_ts()}.mp4"
        music = projects.file_path(pid, p.get("music"))
        duration = compose.render(
            segments,
            compose.output_size(v["resolution"], p["aspect"]),
            int(v["fps"]),
            float(v["fade"]),
            projects.project_dir(pid) / rel,
            music,
            _stage(job, clip_end, 1.0),
        )
        old = p.get("output")
        projects.set_fields(pid, output=rel, output_duration=round(duration, 2))
        if old:
            (projects.project_dir(pid) / old).unlink(missing_ok=True)
        return {"output": rel, "duration": duration}

    label = "AI video" if mode == "ai" else "Hızlı video"
    return jobs.submit("render", pid, label, run).to_dict()


# ---------------------------------------------------------------------------
# işler
# ---------------------------------------------------------------------------
@app.get("/api/jobs")
def list_jobs(project: str | None = None):
    return jobs.recent(project)


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    job = jobs.get(jid)
    if not job:
        raise HTTPException(404, "İş bulunamadı")
    return job.to_dict()


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str):
    job = jobs.get(jid)
    if not job:
        raise HTTPException(404, "İş bulunamadı")
    job.cancel()
    return job.to_dict()


@app.post("/api/release")
def release():
    config.release_models()
    return {"ok": True}


# ---------------------------------------------------------------------------
# dosyalar ve arayüz
# ---------------------------------------------------------------------------
@app.get("/files/{pid}/{path:path}")
def project_file(pid: str, path: str):
    try:
        f = projects.file_path(pid, path)
    except KeyError:
        f = None
    if not f or not f.is_file():
        raise HTTPException(404)
    return FileResponse(f)


app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
