import logging
import time
import wave
from types import TracebackType
from typing import Literal, Self

import numpy as np

from synchro.audio.frame_container import FrameContainer
from synchro.config.audio_format import AudioFormat, AudioFormatType
from synchro.config.schemas import InputFileStreamerNodeSchema
from synchro.graph.nodes.inputs.abstract_input_node import AbstractInputNode

logger = logging.getLogger(__name__)
_

class FileInputNode(AbstractInputNode):
    """
    Узел чтения WAV-файла с безопасной выдачей чанков «под реальное время».
    Принимает 16/24/32-бит, 1..N каналов. В __enter__ переводит поток в МОНО (байтово),
    чтобы весь граф дальше видел консистентный монопоток и правильно считал байты.
    """

    def __init__(self, config: InputFileStreamerNodeSchema) -> None:
        super().__init__(config.name)
        self._config = config
        self._wavefile_data: FrameContainer | None = None

        self._wavefile_index = 0              # текущая позиция в bytes
        self._delay_left = self._config.delay # сек, «тишина» в начале
        self._last_query = time.monotonic()
        self._min_chunk_ms = 10               # минимум 10 мс
        self._bytes_per_sample_mono = 0       # для уже-моно потока
        self._rate = 0

    def __enter__(self) -> Self:
        wf = wave.open(str(self._config.path), "rb")
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()  # bytes per sample
        if sampwidth not in (2, 3, 4):
            raise ValueError("Supported sample sizes: 16/24/32-bit WAV")
        self._rate = wf.getframerate()
        nframes = wf.getnframes()
        raw = wf.readframes(nframes)
        wf.close()

        # bytes -> float32 per channel → моно → обратно в исходную разрядность (байтово)
        mono_bytes = self._downmix_to_mono_bytes(
            raw=raw,
            sample_size=sampwidth,
            channels=channels,
        )

        # Выходной формат остаётся в исходной разрядности, но уже МОНО
        if sampwidth == 2:
            out_fmt = AudioFormat(format_type=AudioFormatType.INT_16)
        elif sampwidth == 3:
            out_fmt = AudioFormat(format_type=AudioFormatType.INT_24)
        else:
            # 32-битный WAV может быть int32 или float32; wave не различает.
            # Для простоты считаем, что это int32. Если нужен float32 — конвертируйте валидатором до или после.
            out_fmt = AudioFormat(format_type=AudioFormatType.INT_32)

        self._wavefile_data = FrameContainer(
            audio_format=out_fmt,
            rate=self._rate,
            frame_data=mono_bytes,  # уже моно interleaved (по сути 1 канал)
        )

        self._bytes_per_sample_mono = sampwidth  # теперь 1 сэмпл = sampwidth байт (моно)
        self._wavefile_index = 0
        self._last_query = time.monotonic()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        self._wavefile_data = None
        return False

    # ------------------------- главная логика выдачи --------------------------

    def get_data(self) -> FrameContainer | None:
        if self._wavefile_data is None:
            logger.info("No data to send - all sent and loop is not enabled")
            return None

        now = time.monotonic()
        time_passed = now - self._last_query
        self._last_query = now

        # Минимальный размер блока в байтах (не отдаём «пылинки»)
        min_chunk_sec = max(self._min_chunk_ms / 1000.0, 0.01)
        min_chunk_bytes = int(self._rate * min_chunk_sec) * self._bytes_per_sample_mono
        if min_chunk_bytes <= 0:
            # защита, но такого быть не должно
            min_chunk_bytes = self._bytes_per_sample_mono

        # Обработка стартовой задержки — отдаём «тишину» достаточного размера
        if self._delay_left > 0:
            delay_dur = min(self._delay_left, time_passed)
            bytes_to_send = max(
                min_chunk_bytes,
                int(delay_dur * self._rate) * self._bytes_per_sample_mono,
            )
            self._delay_left -= delay_dur
            return self._wavefile_data.with_new_data(b"\x00" * bytes_to_send)

        # Сколько байт нужно отдать за прошедшее время (с учётом минимума)
        time_bytes = int(time_passed * self._rate) * self._bytes_per_sample_mono
        need_bytes = max(min_chunk_bytes, time_bytes)

        # Нарежем из «моно файла»
        start = self._wavefile_index
        end = min(start + need_bytes, len(self._wavefile_data.frame_data))
        data_to_send = self._wavefile_data.frame_data[start:end]
        self._wavefile_index = end

        # Если не хватило данных — либо лупим, либо отдаём хвост и остановимся
        if len(data_to_send) < need_bytes:
            if self._config.looping and len(self._wavefile_data.frame_data) > 0:
                logger.info("Looping the file")
                bytes_left = need_bytes - len(data_to_send)
                loop_take = min(bytes_left, len(self._wavefile_data.frame_data))
                data_to_send += self._wavefile_data.frame_data[:loop_take]
                self._wavefile_index = loop_take
            else:
                if len(data_to_send) == 0:
                    logger.info("End of file, no more data to send")
                    return None
                logger.info("Reached end of file, sending remaining %d bytes", len(data_to_send))

        # Гарантия: не отдаём пустые куски
        if len(data_to_send) == 0:
            return None

        data_frame = self._wavefile_data.with_new_data(data_to_send)
        logger.debug(
            "File sending %d bytes (~%.2f ms)",
            len(data_to_send),
            1000.0 * len(data_to_send) / (self._bytes_per_sample_mono * self._rate + 1e-12),
        )
        return data_frame

    # --------------------------- утилиты downmix ------------------------------

    @staticmethod
    def _downmix_to_mono_bytes(raw: bytes, sample_size: int, channels: int) -> bytes:
        """
        Переводим interleaved PCM (1..N каналов) → МОНО (байтово) в исходной разрядности.
        Если channels == 1, возвращаем как есть.
        """
        if channels <= 1:
            return raw

        if sample_size == 2:
            arr = np.frombuffer(raw, dtype="<i2")
            arr = arr.reshape(-1, channels).astype(np.int32)
            mono = np.mean(arr, axis=1).astype(np.int32)
            mono = np.clip(mono, -32768, 32767).astype("<i2")
            return mono.tobytes()

        if sample_size == 3:
            a = np.frombuffer(raw, dtype=np.uint8)
            if len(a) % 3 != 0:
                a = a[: (len(a) // 3) * 3]
            a = a.reshape(-1, 3)
            b = (a[:, 0].astype(np.uint32)
                 | (a[:, 1].astype(np.uint32) << 8)
                 | (a[:, 2].astype(np.uint32) << 16)).astype(np.int32)
            neg = (b & 0x800000) != 0
            b[neg] -= 1 << 24
            b = b.reshape(-1, channels).astype(np.int64)  # запас по динамике для усреднения
            mono = np.mean(b, axis=1).astype(np.int64)
            mono = np.clip(mono, -(1 << 23), (1 << 23) - 1).astype(np.int32)
            out = np.empty((mono.size, 3), dtype=np.uint8)
            mi = mono.copy()
            mi[mi < 0] += 1 << 24
            out[:, 0] = (mi & 0xFF).astype(np.uint8)
            out[:, 1] = ((mi >> 8) & 0xFF).astype(np.uint8)
            out[:, 2] = ((mi >> 16) & 0xFF).astype(np.uint8)
            return out.tobytes()

        if sample_size == 4:
            # Пытаемся сначала как int32; если похоже на float32 — можно переписать обработчик/валидатор выше.
            arr_i = np.frombuffer(raw, dtype="<i4")
            looks_int = np.mean(np.abs(arr_i) < (1 << 30)) > 0.5  # грубая эвристика
            if looks_int:
                arr = arr_i.reshape(-1, channels).astype(np.int64)
                mono = np.mean(arr, axis=1).astype(np.int64)
                mono = np.clip(mono, -2147483648, 2147483647).astype("<i4")
                return mono.tobytes()
            else:
                arr = np.frombuffer(raw, dtype="<f4").reshape(-1, channels).astype(np.float32)
                mono = np.mean(arr, axis=1)
                return mono.astype("<f4").tobytes()

        raise ValueError(f"Unsupported sample_size={sample_size}")
