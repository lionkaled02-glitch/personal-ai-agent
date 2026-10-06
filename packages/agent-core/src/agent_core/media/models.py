from __future__ import annotations
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field

class MediaRequest(BaseModel):
    kind: Literal["image","video"]
    prompt: str = Field(min_length=1, max_length=4000)
    filename: str = Field(default="generated.bin", max_length=120)

class MediaArtifact(BaseModel):
    kind: Literal["image","video"]
    path: Path
    size_bytes: int
    sha256: str
