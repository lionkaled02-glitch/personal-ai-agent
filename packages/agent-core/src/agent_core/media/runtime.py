from __future__ import annotations
import hashlib
import re
from pathlib import Path
from .models import MediaArtifact, MediaRequest
from .providers import ImageGenerator, VideoGenerator

class MediaRuntime:
    def __init__(self, output_root: Path, image: ImageGenerator, video: VideoGenerator, max_bytes: int = 20_000_000):
        self.output_root = output_root.resolve()
        self.image, self.video, self.max_bytes = image, video, max_bytes

    def generate(self, request: MediaRequest) -> MediaArtifact:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", request.filename).strip(".") or "generated.bin"
        target = (self.output_root / safe).resolve()
        if self.output_root not in target.parents:
            raise ValueError("output path escapes generated-artifact boundary")
        data = (self.image.generate_image(request) if request.kind == "image" else self.video.generate_video(request))
        if len(data) > self.max_bytes:
            raise ValueError("generated artifact exceeds size limit")
        self.output_root.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return MediaArtifact(kind=request.kind, path=target, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
