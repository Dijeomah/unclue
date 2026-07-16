from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile

from .base import AIBackend

# Sanity-check at import time so the error is obvious
if not shutil.which("claude"):
    raise EnvironmentError(
        "Claude Code CLI not found in PATH. "
        "Install it with: npm install -g @anthropic-ai/claude-code"
    )


class ClaudeCodeBackend(AIBackend):
    """
    Sends queries to Claude Code CLI running inside the project directory.

    Advantage over direct API calls: Claude Code has full file-system access,
    can read source files, run bash commands, and understand the codebase —
    not just the screenshot + transcript.
    """

    def __init__(self, project_dir: str):
        self._project_dir = project_dir
        self._tmp_dir = os.path.join(project_dir, ".cluely_tmp")
        os.makedirs(self._tmp_dir, exist_ok=True)

    def get_response(
        self,
        transcript: str,
        screenshot_b64: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        tmp_path: str | None = None

        try:
            prompt = self._build_prompt(transcript, screenshot_b64, system_prompt)

            if screenshot_b64:
                # Claude Code is sandboxed to project_dir, so the screenshot must
                # live inside it (the OS temp dir is outside its read access).
                tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, dir=self._tmp_dir)
                tmp.write(base64.b64decode(screenshot_b64))
                tmp.close()
                tmp_path = tmp.name
                prompt += f"\n\nScreenshot saved at: {tmp_path}"

            result = subprocess.run(
                [
                    "claude", "-p", prompt,
                    "--output-format", "json",
                    "--allowedTools", "WebSearch,WebFetch,Read,Glob,Grep",
                ],
                capture_output=True,
                text=True,
                cwd=self._project_dir,
                timeout=60,
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                return f"[Claude Code error] {stderr or 'non-zero exit'}"

            return self._parse(result.stdout)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _build_prompt(self, transcript: str, has_screenshot: bool, system_prompt: str | None = None) -> str:
        parts = [
            system_prompt
            or "You are acting as a real-time assistant. "
               "Respond in 2-4 sentences or a short code snippet. Be direct and concise."
        ]
        if transcript:
            parts.append(f"Transcript: {transcript}")
        if has_screenshot:
            parts.append("A screenshot of the user's screen is also attached (path below).")
        if not transcript and not has_screenshot:
            parts.append("Analyse the current state of the project and suggest next steps.")
        return "\n".join(parts)

    def _parse(self, stdout: str) -> str:
        stdout = stdout.strip()
        if not stdout:
            return "[No response]"
        try:
            data = json.loads(stdout)
            # Claude Code JSON output: {"result": "...", "subtype": "success", ...}
            return data.get("result", stdout)
        except json.JSONDecodeError:
            # Streaming JSON lines — take the last non-empty line
            lines = [l.strip() for l in stdout.splitlines() if l.strip()]
            for line in reversed(lines):
                try:
                    return json.loads(line).get("result", line)
                except json.JSONDecodeError:
                    return line
            return stdout