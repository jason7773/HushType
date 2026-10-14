"""麥克風錄音。音訊只留在記憶體，不寫入硬碟。"""

from __future__ import annotations

import io
import math
import sys
import threading
import wave
from array import array
from dataclasses import dataclass


@dataclass
class Recording:
    wav: bytes
    seconds: float
    rms: float


def _samples(raw: bytes) -> array:
    a = array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def _energy(raw: bytes) -> tuple[float, int]:
    """(平方和, 樣本數)。"""
    a = _samples(raw)
    return float(sum(x * x for x in a)), len(a)


def encode_wav(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def trim_silence(chunks: list[bytes], energies: list[tuple[float, int]], sample_rate: int, *,
                 threshold: float = 200.0, pad_seconds: float = 0.5) -> list[bytes]:
    """去掉開頭和結尾的靜音（各留一點緩衝），上傳的音檔更小、辨識也比較快。"""
    loud = [i for i, (sq, n) in enumerate(energies) if n and math.sqrt(sq / n) >= threshold]
    if not loud:
        return chunks
    pad = int(pad_seconds * sample_rate)
    first, last = loud[0], loud[-1]
    kept = 0
    while first > 0 and kept < pad:
        first -= 1
        kept += energies[first][1]
    kept = 0
    while last < len(chunks) - 1 and kept < pad:
        last += 1
        kept += energies[last][1]
    return chunks[first : last + 1]


def make_recording(chunks: list[bytes], sample_rate: int, energies: list[tuple[float, int]] | None = None,
                   *, trim: bool = True) -> Recording:
    """把錄到的 16-bit PCM 片段組成 WAV。秒數是實際說話（含前後緩衝）的長度。"""
    if energies is None:
        energies = [_energy(c) for c in chunks]
    total_sq = sum(sq for sq, _ in energies)
    total_n = sum(n for _, n in energies)
    rms = math.sqrt(total_sq / total_n) if total_n else 0.0
    if trim:
        chunks = trim_silence(chunks, energies, sample_rate)
    pcm = b"".join(chunks)
    return Recording(encode_wav(pcm, sample_rate), len(pcm) / 2 / sample_rate, rms)


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
        self._chunks: list[bytes] = []
        self._energies: list[tuple[float, int]] = []
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
            self._chunks, self._energies, self._frames, self.level = [], [], 0, 0.0
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                device=self.device,
                callback=self._callback,
            )
            self._stream.start()

    def _callback(self, indata, frames, time_info, status) -> None:
        raw = bytes(indata)
        sq, n = _energy(raw)
        if self._frames < self.max_frames:
            self._chunks.append(raw)
            self._energies.append((sq, n))
            self._frames += frames
        self.level = min(math.sqrt(sq / n) / 6000, 1.0) if n else 0.0

    def stop(self) -> Recording:
        with self._lock:
            stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        chunks, self._chunks = self._chunks, []
        energies, self._energies = self._energies, []
        return make_recording(chunks, self.sample_rate, energies)
