"""Genel ayarlar ve donanım tespiti."""
from __future__ import annotations

import gc
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
PROJECTS_DIR = Path(os.environ.get("STUDIO_PROJECTS_DIR", ROOT / "projects"))
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

# STUDIO_MOCK=1 -> AI modelleri yüklenmez, sahte (renkli) kareler üretilir.
# Arayüzü denemek ya da AI paketleri kurulu olmayan makinede çalıştırmak için.
_force_mock = os.environ.get("STUDIO_MOCK") == "1"

try:
    if _force_mock:
        raise ImportError
    import torch  # noqa: F401
    import diffusers  # noqa: F401

    AI_AVAILABLE = True
except Exception:  # paket yok veya mock zorlandı
    AI_AVAILABLE = False

MOCK = not AI_AVAILABLE


def device() -> str:
    if MOCK:
        return "mock"
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


# ---------------------------------------------------------------------------
# Model yöneticisi: 16 GB RAM'de aynı anda tek büyük model bellekte dursun.
# ---------------------------------------------------------------------------
_model_lock = threading.Lock()
_current: dict = {"name": None, "obj": None}


def get_model(name: str, loader):
    with _model_lock:
        if _current["name"] != name:
            _release_locked()
            _current["obj"] = loader()
            _current["name"] = name
        return _current["obj"]


def release_models() -> None:
    with _model_lock:
        _release_locked()


def _release_locked() -> None:
    _current["obj"] = None
    _current["name"] = None
    free_memory()


def free_memory() -> None:
    gc.collect()
    if MOCK:
        return
    try:
        import torch

        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        elif torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
