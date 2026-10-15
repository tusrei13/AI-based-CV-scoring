from pathlib import Path

import config
import extract
from main import load_or_extract
from models import Resume


def test_extraction_cache_avoids_second_call(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CACHE_DIR", str(tmp_path))
    calls = []

    def fake_extract(text, **kwargs):
        calls.append(text)
        return Resume()

    monkeypatch.setattr(extract, "extract_resume", fake_extract)
    load_or_extract("same cv", no_cache=False)
    load_or_extract("same cv", no_cache=False)
    assert len(calls) == 1
