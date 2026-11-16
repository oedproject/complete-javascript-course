"""Türkçe istemleri yerel bir modelle İngilizceye çevirir.

Görsel/video modelleri İngilizce istemlerde çok daha iyi sonuç verir.
Model (Helsinki-NLP/opus-mt-tr-en, ~300 MB) ilk kullanımda indirilir ve CPU'da çalışır.
"""
from __future__ import annotations

import re
import threading

from .config import MOCK

_MODEL_ID = "Helsinki-NLP/opus-mt-tr-en"
_lock = threading.Lock()
_model = None
_cache: dict[str, str] = {}

_TR_CHARS = set("çğıöşüÇĞİÖŞÜ")
_TR_WORDS = {
    "ve", "bir", "bu", "ile", "için", "da", "de", "çok", "gibi", "olan", "içinde",
    "üstünde", "altında", "yanında", "doğru", "gece", "gün", "adam", "kadın", "kız",
    "çocuk", "şehir", "deniz", "orman", "dağ", "yağmur", "kar", "güneş", "ay", "yıldız",
    "uçan", "koşan", "yürüyen", "eski", "yeni", "büyük", "küçük", "kırmızı", "mavi",
}


def looks_turkish(text: str) -> bool:
    if any(c in _TR_CHARS for c in text):
        return True
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    return len(words & _TR_WORDS) >= 1


def _load():
    global _model
    if _model is None:
        from transformers import MarianMTModel, MarianTokenizer

        tok = MarianTokenizer.from_pretrained(_MODEL_ID)
        mdl = MarianMTModel.from_pretrained(_MODEL_ID)
        mdl.eval()
        _model = (tok, mdl)
    return _model


def to_english(text: str) -> str:
    text = (text or "").strip()
    if not text or MOCK or not looks_turkish(text):
        return text
    if text in _cache:
        return _cache[text]
    with _lock:
        import torch

        tok, mdl = _load()
        # cümle cümle çevir: uzun girdilerde model daha tutarlı
        parts = [p for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]
        batch = tok(parts, return_tensors="pt", padding=True, truncation=True, max_length=256)
        with torch.no_grad():
            out = mdl.generate(**batch, max_new_tokens=256, num_beams=4)
        result = " ".join(tok.batch_decode(out, skip_special_tokens=True))
    _cache[text] = result
    return result
