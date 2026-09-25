"""Embed the curated corpus. Hashing vectors are the offline default.

Set AQUAWATCH_EMBED=transformer to use a locally cached sentence-transformers model.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aquawatch.llm.retriever import Retriever  # noqa: E402
from aquawatch.settings import load_settings  # noqa: E402


def main() -> int:
    settings = load_settings(ROOT)
    count = Retriever(settings.corpus_dir, settings.cache_dir).build_index()
    print(f"indexed {count} passages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
