import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.whisper_model = os.environ.get("WHISPER_MODEL", "base.en")
        self.audio_device_name = os.environ.get("AUDIO_DEVICE_NAME", "Cluely Aggregate")
        self.silence_rms_threshold = float(os.environ.get("SILENCE_RMS_THRESHOLD", "0.0008"))
        self.project_dir = os.environ.get("PROJECT_DIR", os.getcwd())
