"""Tek işçili iş kuyruğu: GPU'yu aynı anda tek iş kullanır."""
from __future__ import annotations

import queue
import threading
import time
import traceback
import uuid


class Cancelled(Exception):
    pass


class Job:
    def __init__(self, kind: str, project: str, label: str, fn):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.project = project
        self.label = label
        self.fn = fn
        self.status = "queued"  # queued | running | done | error | cancelled
        self.progress = 0.0
        self.message = "Sırada bekliyor"
        self.error: str | None = None
        self.result = None
        self.created = time.time()
        self.finished: float | None = None
        self._cancel = threading.Event()

    # İş fonksiyonu bu metodu çağırarak ilerleme bildirir ve iptali kontrol eder.
    def update(self, progress: float | None = None, message: str | None = None) -> None:
        if self._cancel.is_set():
            raise Cancelled()
        if progress is not None:
            self.progress = max(0.0, min(1.0, float(progress)))
        if message is not None:
            self.message = message

    def cancel(self) -> None:
        self._cancel.set()
        if self.status == "queued":
            self.status = "cancelled"
            self.message = "İptal edildi"
            self.finished = time.time()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "project": self.project,
            "label": self.label,
            "status": self.status,
            "progress": round(self.progress, 4),
            "message": self.message,
            "error": self.error,
            "result": self.result,
            "created": self.created,
            "finished": self.finished,
        }


_jobs: dict[str, Job] = {}
_queue: "queue.Queue[Job]" = queue.Queue()


def submit(kind: str, project: str, label: str, fn) -> Job:
    job = Job(kind, project, label, fn)
    _jobs[job.id] = job
    _queue.put(job)
    _prune()
    return job


def get(jid: str) -> Job | None:
    return _jobs.get(jid)


def recent(project: str | None = None) -> list[dict]:
    items = [j for j in _jobs.values() if project is None or j.project == project]
    items.sort(key=lambda j: j.created)
    return [j.to_dict() for j in items[-30:]]


def _prune() -> None:
    done = [j for j in _jobs.values() if j.finished and time.time() - j.finished > 3600]
    for j in done:
        _jobs.pop(j.id, None)


def _worker() -> None:
    while True:
        job = _queue.get()
        if job.status == "cancelled":
            continue
        job.status = "running"
        job.message = "Başladı"
        try:
            job.result = job.fn(job)
            job.status = "done"
            job.progress = 1.0
            job.message = "Tamamlandı"
        except Cancelled:
            job.status = "cancelled"
            job.message = "İptal edildi"
        except Exception as e:  # hata arayüzde gösterilir
            traceback.print_exc()
            job.status = "error"
            job.error = f"{type(e).__name__}: {e}"
            job.message = "Hata"
        finally:
            job.finished = time.time()


threading.Thread(target=_worker, daemon=True, name="studio-worker").start()
