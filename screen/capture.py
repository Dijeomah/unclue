import base64
import io

import mss
from PIL import Image

MAX_WIDTH = 1280  # keeps token cost reasonable for vision models


def capture_screen() -> str:
    """Capture the primary monitor and return a base64-encoded JPEG string."""
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary display
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        img = img.resize(
            (MAX_WIDTH, int(img.height * ratio)),
            Image.LANCZOS,
        )

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
