from __future__ import annotations

from abc import ABC, abstractmethod


class AIBackend(ABC):
    @abstractmethod
    def get_response(
        self,
        transcript: str,
        screenshot_b64: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        pass
