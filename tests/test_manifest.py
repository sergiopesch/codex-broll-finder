import json

import pytest

from kino.manifest import ManifestError, load_manifest


def write_manifest(tmp_path, beats):
    path = tmp_path / "KINO-MANIFEST.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "base": "input.mp4",
                "output": "out.mp4",
                "beats": beats,
            }
        )
    )
    return path


def beat(id_, start, end):
    return {
        "id": id_,
        "start": start,
        "end": end,
        "line": "line",
        "interpretation": "meaning",
        "route": "entity",
        "asset": f"assets/{id_}.mp4",
        "kind": "video",
    }


def test_loads_valid_manifest(tmp_path):
    manifest = load_manifest(write_manifest(tmp_path, [beat("b001", 1.0, 3.0)]))

    assert manifest.base == tmp_path / "input.mp4"
    assert manifest.beats[0].duration == 2.0


def test_rejects_overlapping_beats(tmp_path):
    path = write_manifest(tmp_path, [beat("b001", 1.0, 3.0), beat("b002", 2.5, 4.0)])

    with pytest.raises(ManifestError, match="non-overlapping"):
        load_manifest(path)


def test_rejects_duplicate_ids(tmp_path):
    path = write_manifest(tmp_path, [beat("b001", 1.0, 3.0), beat("b001", 3.0, 4.0)])

    with pytest.raises(ManifestError, match="duplicate"):
        load_manifest(path)
