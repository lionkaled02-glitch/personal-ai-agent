from __future__ import annotations

from typing import Protocol

from .models import MediaRequest


class ImageGenerator(Protocol):
    def generate_image(self, request: MediaRequest) -> bytes: ...


class VideoGenerator(Protocol):
    def generate_video(self, request: MediaRequest) -> bytes: ...


class MockMediaGenerator:
    def generate_image(self, request: MediaRequest) -> bytes:
        return ("PERSONAL_AI_AGENT_IMAGE\n" + request.prompt).encode()

    def generate_video(self, request: MediaRequest) -> bytes:
        return ("PERSONAL_AI_AGENT_VIDEO\n" + request.prompt).encode()
