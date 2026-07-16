from __future__ import annotations

import queue

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHUNK_SECONDS = 0.5


class AudioCapture:
    """Captures audio from an input device and pushes mono float32 chunks onto a queue.

    Point `device_name` at an Aggregate Device (built in Audio MIDI Setup) that
    combines the built-in mic with a BlackHole input to capture both mic and
    system audio in one stream. Falls back to the system default input if the
    named device isn't found.
    """

    def __init__(self, audio_queue: queue.Queue, device_name: str | None = None):
        self._queue = audio_queue
        self._device_name = device_name
        self._stream: sd.InputStream | None = None

    def _resolve_device(self):
        if self._device_name:
            for idx, dev in enumerate(sd.query_devices()):
                if dev["max_input_channels"] > 0 and self._device_name.lower() in dev["name"].lower():
                    return idx, dev["max_input_channels"]
            print(f"[audio] Device matching '{self._device_name}' not found, using default input.")
        default_idx = sd.default.device[0]
        default_dev = sd.query_devices(default_idx)
        return default_idx, default_dev["max_input_channels"]

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[audio] {status}")
        if indata.shape[1] > 1:
            # On an Aggregate Device (mic + BlackHole), averaging dilutes the
            # mic by ~1/N whenever the other channels are silent (no system
            # audio playing) — sum instead so a quiet/idle channel can't drag
            # down the voice signal, then clip to avoid overflow if both are loud.
            mono = np.clip(indata.sum(axis=1), -1.0, 1.0)
        else:
            mono = indata[:, 0]
        self._queue.put(mono.copy())

    def start(self):
        device_idx, channels = self._resolve_device()
        self._stream = sd.InputStream(
            device=device_idx,
            channels=channels,
            samplerate=SAMPLE_RATE,
            blocksize=int(SAMPLE_RATE * CHUNK_SECONDS),
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()
        print(f"[audio] Capture started on device #{device_idx} ({channels} ch)")

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
