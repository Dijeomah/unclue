from __future__ import annotations

import queue
import threading

import numpy as np
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
SILENCE_HANG_SECONDS = 0.8
MIN_SEGMENT_SECONDS = 0.6
MAX_SEGMENT_SECONDS = 20.0


class Transcriber:
    """Buffers audio chunks into speech segments (via simple silence detection)
    and transcribes each segment with faster-whisper, pushing text onto a queue."""

    def __init__(
        self,
        audio_queue: queue.Queue,
        transcript_queue: queue.Queue,
        model_name: str = "base.en",
        silence_rms_threshold: float = 0.0008,
    ):
        self._audio_queue = audio_queue
        self._transcript_queue = transcript_queue
        self._model = WhisperModel(model_name, device="cpu", compute_type="int8")
        self._silence_rms_threshold = silence_rms_threshold
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        buffer: list[np.ndarray] = []
        buffered_seconds = 0.0
        silence_seconds = 0.0

        while self._running:
            try:
                chunk = self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            buffer.append(chunk)
            chunk_seconds = len(chunk) / SAMPLE_RATE
            buffered_seconds += chunk_seconds

            rms = float(np.sqrt(np.mean(np.square(chunk)))) if len(chunk) else 0.0
            silence_seconds = silence_seconds + chunk_seconds if rms < self._silence_rms_threshold else 0.0

            should_flush = buffered_seconds >= MIN_SEGMENT_SECONDS and (
                silence_seconds >= SILENCE_HANG_SECONDS or buffered_seconds >= MAX_SEGMENT_SECONDS
            )
            if should_flush:
                self._flush(buffer)
                buffer = []
                buffered_seconds = 0.0
                silence_seconds = 0.0

    def _flush(self, buffer: list[np.ndarray]):
        audio = np.concatenate(buffer).astype(np.float32)
        if float(np.sqrt(np.mean(np.square(audio)))) < self._silence_rms_threshold:
            return
        segments, _ = self._model.transcribe(audio, language="en", vad_filter=True)
        text = " ".join(s.text.strip() for s in segments).strip()
        if text:
            self._transcript_queue.put(text)
