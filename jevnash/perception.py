"""Perception via LlamaParse: anything visual or document-shaped becomes text the models can read.

Two uses, both off the per-tick hot path because a parse takes 10-20s:
  - pixel-only surfaces (canvas games, images): screenshot -> markdown/table, cached per frame
  - rulebooks and briefs (PDF, docx, images): parsed once and handed to the GameModeler
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
from pathlib import Path

from .events import bus

CACHE = Path("runs/.parse_cache")


def available() -> bool:
    return bool(os.environ.get("LLAMA_CLOUD_API_KEY"))


def parse_bytes(data: bytes, suffix: str, purpose: str, tier: str = "cost_effective") -> str:
    key = hashlib.sha1(data).hexdigest()
    hit = CACHE / f"{key}.md"
    if hit.exists():
        bus.emit("perception", purpose=purpose, cached=True, secs=0)
        return hit.read_text()
    from llama_cloud import LlamaCloud  # imported lazily: only needed when perception is used

    t0 = time.time()
    bus.emit("perception_start", purpose=purpose)
    client = LlamaCloud()
    with tempfile.NamedTemporaryFile(suffix=suffix) as f:
        f.write(data)
        f.flush()
        uploaded = client.files.create(file=f.name, purpose="parse")
    result = client.parsing.parse(file_id=uploaded.id, tier=tier, version="latest", expand=["markdown"])
    text = "\n\n".join(p.markdown for p in result.markdown.pages)
    CACHE.mkdir(parents=True, exist_ok=True)
    hit.write_text(text)
    bus.emit("perception", purpose=purpose, cached=False, secs=round(time.time() - t0, 1))
    return text


def parse_file(path: str, purpose: str = "rulebook") -> str:
    p = Path(path)
    if p.suffix.lower() in (".md", ".txt"):
        return p.read_text()
    return parse_bytes(p.read_bytes(), p.suffix, purpose)
