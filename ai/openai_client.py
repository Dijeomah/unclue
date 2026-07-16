from __future__ import annotations

from openai import OpenAI

from .base import AIBackend

SYSTEM_PROMPT = """You are a real-time coding and conversation assistant.
You may receive a screenshot of the user's screen alongside a spoken transcript.

- If you see code or an error on screen, focus on that — explain the problem and give a fix.
- If a question is asked in the transcript, answer it directly and concisely.
- If both are present, prioritise the screen content.
- Keep responses to 2-4 sentences or a short code snippet. Be direct."""


class OpenAIBackend(AIBackend):
    def __init__(self, api_key: str):
        self._client = OpenAI(api_key=api_key)

    def get_response(
        self,
        transcript: str,
        screenshot_b64: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        content: list = []

        if screenshot_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"},
            })

        content.append({"type": "text", "text": transcript or "[No speech detected]"})

        response = self._client.chat.completions.create(
            model="gpt-4o",
            max_tokens=512,
            messages=[
                {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        )
        return response.choices[0].message.content
