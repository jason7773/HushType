"""麥克風錄音。音訊只留在記憶體，不寫入硬碟。"""

from __future__ import annotations

import io
import threading
import wave
from dataclasses import dataclass

import numpy as np


@dataclass
class Recording:
    wav: bytes
    seconds: float
    rms: float


def encode_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(samples.astype(np.int16).tobytes())
    return buf.getvalue()


def make_recording(chunks: list[np.ndarray], sample_rate: int) -> Recording:
    samples = np.concatenate(chunks).reshape(-1) if chunks else np.zeros(0, dtype=np.int16)
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2))) if samples.size else 0.0
    return Recording(encode_wav(samples, sample_rate), samples.size / sample_rate, rms)


def input_devices() -> list[str]:
    """列出可用的麥克風名稱。"""
    import sounddevice as sd

    names = []
    for d in sd.query_devices():
        if d["max_input_channels"] > 0 and d["name"] not in names:
            names.append(d["name"])
    return names


def default_input_device() -> str:
    import sounddevice as sd

    try:
        return sd.query_devices(kind="input")["name"]
    except Exception:
        return ""


class Recorder:
    def __init__(self, sample_rate: int = 16000, max_seconds: float = 300, device: str | None = None):
        self.device = device or None
        self.level = 0.0  # 最近一段音訊的音量（0–1），給介面顯示
        self.sample_rate = sample_rate
        self.max_frames = int(sample_rate * max_seconds)
        self._chunks: list[np.ndarray] = []
        self._frames = 0
        self._stream = None
        self._lock = threading.Lock()

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        import sounddevice as sd

        with self._lock:
            if self._stream is not None:
                return
            self._chunks, self._frames, self.level = [], 0, 0.0
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                device=self.device,
                callback=self._callback,
            )
            self._stream.start()

    def _callback(self, indata, frames, time_info, status) -> None:
        if self._frames < self.max_frames:
            self._chunks.append(indata.copy())
            self._frames += frames
        self.level = min(float(np.sqrt(np.mean(indata.astype(np.float32) ** 2))) / 6000, 1.0)

    def stop(self) -> Recording:
        with self._lock:
            stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        chunks, self._chunks = self._chunks, []
        return make_recording(chunks, self.sample_rate)
