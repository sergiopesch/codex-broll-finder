from pathlib import Path

from PIL import Image

from kino.qc import (
    FrameExpectation,
    expected_frame_paths,
    frame_expectations_from_dir,
    generate_contact_sheet,
    verify_frames,
    write_frame_qc_json,
    write_frame_qc_markdown,
)


def write_image(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (32, 18)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def test_expected_frame_paths_builds_labeled_jpegs(tmp_path):
    frames = expected_frame_paths(tmp_path, ["b001-start", "b001-mid"])

    assert frames == (
        FrameExpectation("b001-start", tmp_path / "b001-start.jpg"),
        FrameExpectation("b001-mid", tmp_path / "b001-mid.jpg"),
    )


def test_frame_expectations_from_dir_sorts_supported_images(tmp_path):
    (tmp_path / "notes.txt").write_text("ignore me\n")
    second = write_image(tmp_path / "b-mid.png", (20, 200, 20))
    first = write_image(tmp_path / "a-start.jpg", (200, 20, 20))

    assert frame_expectations_from_dir(tmp_path) == (
        FrameExpectation("a-start", first),
        FrameExpectation("b-mid", second),
    )


def test_verify_frames_reports_missing_and_tiny_files(tmp_path):
    tiny = tmp_path / "tiny.jpg"
    tiny.write_bytes(b"")

    report = verify_frames(
        [
            ("missing", tmp_path / "missing.jpg"),
            ("tiny", tiny),
        ],
        min_bytes=10,
    )

    assert report.overall == "fail"
    assert any(check.name == "missing_frame" and check.status == "fail" for check in report.checks)
    assert any(check.name == "tiny_frame_file" and check.status == "fail" for check in report.checks)


def test_verify_frames_warns_on_near_black_frame(tmp_path):
    black = write_image(tmp_path / "black.jpg", (1, 1, 1))

    report = verify_frames([black], min_bytes=1, black_luma_threshold=8.0)

    assert report.overall == "warning"
    assert any(check.name == "near_black_frame" and check.status == "warning" for check in report.checks)


def test_verify_frames_warns_on_near_identical_adjacent_frames(tmp_path):
    first = write_image(tmp_path / "first.jpg", (200, 20, 20))
    second = write_image(tmp_path / "second.jpg", (200, 20, 20))
    third = write_image(tmp_path / "third.jpg", (20, 200, 20))

    report = verify_frames([first, second, third], min_bytes=1)

    assert report.overall == "warning"
    identical = [check for check in report.checks if check.name == "near_identical_adjacent_frames"]
    assert len(identical) == 1
    assert identical[0].label == "first,second"


def test_verify_frames_can_write_contact_sheet(tmp_path):
    first = write_image(tmp_path / "first.jpg", (200, 20, 20), size=(40, 30))
    missing = tmp_path / "missing.jpg"
    sheet = tmp_path / "qc" / "sheet.jpg"

    report = verify_frames([first, missing], min_bytes=1, contact_sheet_path=sheet)

    assert report.contact_sheet == sheet
    assert sheet.exists()
    with Image.open(sheet) as image:
        assert image.size == (1340, 228)


def test_generate_contact_sheet_accepts_empty_frame_list(tmp_path):
    sheet = generate_contact_sheet([], tmp_path / "empty.jpg", columns=3, thumb_size=(80, 45), padding=4)

    with Image.open(sheet) as image:
        assert image.size == (256, 77)


def test_frame_qc_report_to_dict_serializes_paths(tmp_path):
    frame = write_image(tmp_path / "frame.jpg", (20, 200, 20))
    report = verify_frames([("frame", frame)], min_bytes=1)

    data = report.to_dict()

    assert data["overall"] == "pass"
    assert data["frames"] == [{"label": "frame", "path": str(frame)}]


def test_frame_qc_writers_emit_json_and_markdown(tmp_path):
    frame = write_image(tmp_path / "frame.jpg", (20, 200, 20))
    report = verify_frames([("frame", frame)], min_bytes=1)

    json_out = write_frame_qc_json(report, tmp_path / "KINO-FRAME-QC.json")
    md_out = write_frame_qc_markdown(report, tmp_path / "KINO-FRAME-QC.md")

    assert '"overall": "pass"' in json_out.read_text()
    assert "# Kino Frame QC Report" in md_out.read_text()
