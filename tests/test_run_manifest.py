"""Tests for provenance hashing and atomic run manifests."""

import json

from src.pipeline import _sha256_file, _write_run_manifest


def test_input_hash_changes_when_content_changes(tmp_path):
    source = tmp_path / "input.bin"
    source.write_bytes(b"first")
    first = _sha256_file(source)
    source.write_bytes(b"second")
    assert _sha256_file(source) != first


def test_manifest_writer_persists_json_atomically(tmp_path):
    path = tmp_path / "results" / "run_manifest.json"
    payload = {"run_id": "run-1", "data_mode": "demo", "status": "success"}
    _write_run_manifest(path, payload)
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert list(path.parent.iterdir()) == [path]
