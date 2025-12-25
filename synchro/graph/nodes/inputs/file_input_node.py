import time
import wave
import logging
from types import TracebackType
from typing import Literal, Self

from synchro.audio.frame_container import FrameContainer
from synchro.config.audio_format import AudioFormat, AudioFormatType
from synchro.config.schemas import InputFileStreamerNodeSchema
from synchro.graph.nodes.inputs.abstract_input_node import AbstractInputNode
from synchro.graph.graph_exceptions import StopGraph

logger = logging.getLogger(__name__)


class FileInputNode(AbstractInputNode):
    """
    Узел чтения WAV-файла с безопасной выдачей чанков «под реальное время».
    Принимает 16/24/32-бит, 1..N каналов. В __enter__ переводит поток в МОНО (байтово),
    чтобы весь граф дальше видел консистентный монопоток и правильно считал байты.
    """

    def __init__(self, config: InputFileStreamerNodeSchema) -> None:
        super().__init__(config)
        self._config = config
        self._wavefile_data: FrameContainer | None = None

        self._wavefile_index = 0              # текущая позиция в bytes
        self._delay_left = self._config.delay # сек, «тишина» в начале
        self._last_query = time.monotonic()
        self._min_chunk_ms = 10               # минимум 10 мс
        self._bytes_per_frame = 0
        self._rate = 0

        self._debug1 = None

    def __enter__(self) -> Self:
        """
        sampwidth = 2 байта (16 бит на один сэмпл)
	    channels = 2 (левый + правый)
	    framerate = 44100 (фреймов в секунду)

        frame_size = sampwidth * channels = 2 * 2 = 4 байта
        bitrate = bytes_per_second = frame_size * framerate = 4 * 44100 = 176400 байт/сек
        """

        wf = wave.open(str(self._config.path), "rb")

        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        self._rate = wf.getframerate()
        nframes = wf.getnframes()

        # ── применяем start/duration из конфига (в секундах) ──
        start_s = float(self._config.start or 0.0)
        duration_s = self._config.duration
        # start → frames (с клампом в пределах файла)
        start_frame = max(0, min(int(round(start_s * self._rate)), nframes))
        # duration → frames
        if duration_s is None:
            frames_to_read = nframes - start_frame
        else:
            end_frame = int(round(float(duration_s) * self._rate))
            frames_to_read = max(0, min(end_frame, nframes - start_frame))

        # позиционируемся и читаем только нужный диапазон
        wf.setpos(start_frame)
        raw = wf.readframes(frames_to_read)
        wf.close()

        logger.info(
            "Open WAV file %s: %d x %d x %d = %d",
            self._config.path, 
            sampwidth, channels, self._rate, 
            sampwidth * channels * self._rate
        )

        out_fmt = AudioFormat.from_sample_width(sampwidth)
        self._wavefile_data = FrameContainer(
            audio_format=out_fmt,
            rate=self._rate,
            frame_data=raw,
            channels=channels,
        )

        self._bytes_per_frame = sampwidth * channels
        self._wavefile_index = 0
        self._last_query = time.monotonic()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        self._debug1.close()
        self._debug1 = None
        self._wavefile_data = None
        return False

    # ------------------------- главная логика выдачи --------------------------

    def _pull_raw_chunk(self) -> FrameContainer | None:
        if self._wavefile_data is None:
            logger.info("No data to send - all sent and loop is not enabled")
            return None

        now = time.monotonic()
        time_passed = now - self._last_query
        self._last_query = now

        frame_size = self._bytes_per_frame
        rate = self._rate

        # Минимальный размер блока в байтах (не отдаём «пылинки»)
        min_chunk_sec = max(self._min_chunk_ms / 1000.0, 0.01)
        min_chunk_bytes = int(rate * min_chunk_sec) * frame_size
        min_chunk_bytes -= (min_chunk_bytes % frame_size)

        # Обработка стартовой задержки — отдаём «тишину» достаточного размера
        if self._delay_left > 0:
            delay_dur = min(self._delay_left, time_passed)
            bytes_to_send = max(
                min_chunk_bytes,
                int(delay_dur * rate) * frame_size,
            )
            self._delay_left -= delay_dur
            logger.info("Delaying start by %.3f sec, sending %d bytes of silence", delay_dur, bytes_to_send)
            return self._wavefile_data.with_new_data(b"\x00" * bytes_to_send)

        # Сколько байт нужно отдать за прошедшее время (с учётом минимума)
        time_chunk_bytes = int(time_passed * rate) * frame_size
        need_bytes = max(min_chunk_bytes, time_chunk_bytes)

        # Нарежем
        start = self._wavefile_index
        end = min(start + need_bytes, len(self._wavefile_data.frame_data))
        logger.info("File reading bytes %d to %d, %s", start, end, len(self._wavefile_data.frame_data))
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
                raise StopGraph("End of file reached")

        # Гарантия: не отдаём пустые куски
        if len(data_to_send) == 0:
            return None

        data_frame = self._wavefile_data.with_new_data(data_to_send)

        logger.debug(
            "File sending %d bytes (~%.2f ms)",
            len(data_to_send),
            1000.0 * len(data_to_send) / (frame_size * rate + 1e-12),
        )

        logger.info(data_frame)
        return data_frame
