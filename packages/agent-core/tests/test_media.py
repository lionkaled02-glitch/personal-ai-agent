from pathlib import Path

import pytest

from agent_core.media import MediaRuntime, MediaRequest, MockMediaGenerator


def test_media_runtime_writes_bounded_artifact(tmp_path: Path) -> None:
    runtime = MediaRuntime(
        tmp_path / "generated",
        MockMediaGenerator(),
        MockMediaGenerator(),
        max_bytes=1024,
    )
    result = runtime.generate(MediaRequest(kind="image", prompt="a test", filename="image.bin"))
    assert result.path.read_bytes().startswith(b"PERSONAL_AI_AGENT_IMAGE")
    assert result.size_bytes == result.path.stat().st_size
    assert len(result.sha256) == 64


def test_media_runtime_rejects_path_escape(tmp_path: Path) -> None:
    runtime = MediaRuntime(tmp_path / "generated", MockMediaGenerator(), MockMediaGenerator())
    with pytest.raises(ValueError, match="escapes"):
        runtime.generate(MediaRequest(kind="image", prompt="x", filename="../escape.bin"))
    with pytest.raises(ValueError, match="escapes"):
        runtime.generate(MediaRequest(kind="image", prompt="x", filename="/tmp/escape.bin"))
    with pytest.raises(ValueError, match="escapes"):
        runtime.generate(MediaRequest(kind="image", prompt="x", filename=r"nested\\escape.bin"))


def test_media_runtime_enforces_output_limit(tmp_path: Path) -> None:
    runtime = MediaRuntime(tmp_path / "generated", MockMediaGenerator(), MockMediaGenerator(), max_bytes=4)
    with pytest.raises(ValueError, match="exceeds"):
        runtime.generate(MediaRequest(kind="video", prompt="x", filename="video.bin"))
