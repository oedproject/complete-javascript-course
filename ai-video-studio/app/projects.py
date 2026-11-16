"""Projeleri diskte (projects/<id>/project.json) saklar."""
from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from pathlib import Path

from .config import PROJECTS_DIR

_lock = threading.RLock()

ASPECTS = {"16:9", "9:16", "1:1"}

DEFAULT_VIDEO = {
    "mode": "fast",  # fast | ai
    "seconds": 3.0,  # sahne başına süre (hızlı mod)
    "fade": 0.6,  # geçiş süresi (sn)
    "resolution": "720p",  # 480p | 720p | 1080p
    "fps": 24,
    "ai_seconds": 2.0,  # AI klip süresi
    "ai_steps": 30,
    "ai_quality": "low",  # low | medium
    "captions": True,
}


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def project_dir(pid: str) -> Path:
    if not pid.isalnum():
        raise KeyError(pid)
    return PROJECTS_DIR / pid


def _path(pid: str) -> Path:
    return project_dir(pid) / "project.json"


def new_scene(prompt: str = "", caption: str = "") -> dict:
    return {
        "id": _new_id(),
        "prompt": prompt,
        "caption": caption,
        "effect": "auto",
        "motion": "",  # AI video için hareket tarifi (boşsa prompt kullanılır)
        "seed": None,
        "image": None,
        "clip": None,
        "clip_key": None,
    }


def create(title: str = "Yeni proje") -> dict:
    pid = _new_id()
    d = project_dir(pid)
    (d / "frames").mkdir(parents=True)
    (d / "clips").mkdir()
    now = time.time()
    p = {
        "id": pid,
        "title": title or "Yeni proje",
        "created": now,
        "updated": now,
        "idea": "",
        "style": "cinematic, highly detailed, dramatic lighting",
        "negative": "blurry, low quality, deformed, watermark, text",
        "aspect": "16:9",
        "image_model": "sdxl-turbo",
        "translate": True,
        "video": dict(DEFAULT_VIDEO),
        "music": None,
        "scenes": [new_scene()],
        "output": None,
    }
    save(p)
    return p


def load(pid: str) -> dict:
    with _lock:
        path = _path(pid)
        if not path.exists():
            raise KeyError(pid)
        p = json.loads(path.read_text("utf-8"))
        p["video"] = {**DEFAULT_VIDEO, **p.get("video", {})}
        return p


def save(p: dict) -> dict:
    with _lock:
        p["updated"] = time.time()
        path = _path(p["id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(p, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(path)
        return p


def list_all() -> list[dict]:
    out = []
    for f in PROJECTS_DIR.glob("*/project.json"):
        try:
            p = json.loads(f.read_text("utf-8"))
            thumb = next((s["image"] for s in p["scenes"] if s.get("image")), None)
            out.append(
                {"id": p["id"], "title": p["title"], "updated": p["updated"], "thumb": thumb,
                 "scenes": len(p["scenes"])}
            )
        except Exception:
            continue
    return sorted(out, key=lambda x: -x["updated"])


def delete(pid: str) -> None:
    with _lock:
        d = project_dir(pid)
        if d.exists():
            shutil.rmtree(d)


def update_from_client(pid: str, data: dict) -> dict:
    """Arayüzden gelen düzenlemeleri uygular.

    Görsel/klip yolları yalnızca sunucu tarafından yazılır; istemcinin eski
    kopyası, arka planda üretilmiş yeni kareleri ezmesin diye korunur.
    """
    with _lock:
        p = load(pid)
        for key in ("title", "idea", "style", "negative", "image_model"):
            if key in data and isinstance(data[key], str):
                p[key] = data[key]
        if data.get("aspect") in ASPECTS and data["aspect"] != p["aspect"]:
            p["aspect"] = data["aspect"]
        if "translate" in data:
            p["translate"] = bool(data["translate"])
        if isinstance(data.get("video"), dict):
            for k, v in data["video"].items():
                if k in DEFAULT_VIDEO:
                    p["video"][k] = v
        if isinstance(data.get("scenes"), list):
            old = {s["id"]: s for s in p["scenes"]}
            scenes = []
            for s in data["scenes"]:
                base = old.get(s.get("id")) or new_scene()
                for k in ("prompt", "caption", "effect", "motion"):
                    if isinstance(s.get(k), str):
                        base[k] = s[k]
                if "seed" in s and (s["seed"] is None or isinstance(s["seed"], int)):
                    base["seed"] = s["seed"]
                scenes.append(base)
            # silinen sahnelerin dosyalarını temizle
            keep = {s["id"] for s in scenes}
            for sid, s in old.items():
                if sid not in keep:
                    _remove_file(pid, s.get("image"))
                    _remove_file(pid, s.get("clip"))
            p["scenes"] = scenes
        return save(p)


def set_scene_fields(pid: str, sid: str, **fields) -> dict:
    with _lock:
        p = load(pid)
        for s in p["scenes"]:
            if s["id"] == sid:
                for k, v in fields.items():
                    if k in ("image", "clip") and s.get(k) and s.get(k) != v:
                        _remove_file(pid, s[k])
                    s[k] = v
                break
        else:
            raise KeyError(sid)
        return save(p)


def set_fields(pid: str, **fields) -> dict:
    with _lock:
        p = load(pid)
        p.update(fields)
        return save(p)


def get_scene(p: dict, sid: str) -> dict:
    for s in p["scenes"]:
        if s["id"] == sid:
            return s
    raise KeyError(sid)


def file_path(pid: str, rel: str | None) -> Path | None:
    if not rel:
        return None
    path = (project_dir(pid) / rel).resolve()
    if project_dir(pid).resolve() not in path.parents:
        return None
    return path


def _remove_file(pid: str, rel: str | None) -> None:
    path = file_path(pid, rel)
    if path and path.exists():
        path.unlink()
