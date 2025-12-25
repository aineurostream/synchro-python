import logging

import wave
from pydub import AudioSegment
import numpy as np
import soxr

from synchro.audio.frame_container import FrameContainer
from synchro.config.commons import StreamConfig
from synchro.config.schemas import ResamplerNodeSchema
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

INT16_MAX = 32767

logger = logging.getLogger(__name__)


class ResampleNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: ResamplerNodeSchema) -> None:
        super().__init__(config.name)
        self._buffer: FrameContainer | None = None
        self._to_rate = config.to_rate
        self._debug1 = None
        self._debug2 = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._debug1:
            self._debug1.close()
        self._debug1 = None
        
        if self._debug2:
            self._debug2.close()
        self._debug2 = None

    def put_data(self, _source: str, data: FrameContainer) -> None:
        self._buffer = (
            data.clone() 
            if self._buffer is None else 
            self._buffer.append(data)
        )

    def get_data(self) -> FrameContainer | None:
        if not self._buffer:
            return None

        converted_payload_np = self._buffer.as_np()

        resulting_payload = soxr.resample(
            converted_payload_np,
            self._buffer.rate,
            self._to_rate,
        )

        converted_payload = resulting_payload.tobytes()
        
        y = np.clip(resulting_payload, -1.0, 1.0)
        y_i16 = (y * 32767.0).astype('<i2')  # little-endian int16
        debug_payload = y_i16.tobytes()

        if not self._debug1:
            self._debug1 = wave.open("debug_resample1.wav", 'wb')
            self._debug1.setframerate(self._buffer.rate)
            self._debug1.setnchannels(1)
            self._debug1.setsampwidth(2)
        
        self._debug1.writeframes(self._buffer.to_pcm16_bytes())

        if not self._debug2:
            self._debug2 = wave.open("debug_resample2.wav", 'wb')
            self._debug2.setframerate(self._to_rate)
            self._debug2.setnchannels(1)
            self._debug2.setsampwidth(2)
        
        self._debug2.writeframes(debug_payload)

        self._logger.debug(
            "Resampled %d bytes from %d to %d in %s",
            len(converted_payload),
            self._buffer.rate,
            self._to_rate,
            self,
        )

        self._buffer = self._buffer.to_empty()

        return FrameContainer.from_config(
            StreamConfig(
                rate=self._to_rate, 
                audio_format=self._buffer.audio_format,
                channels=self._buffer.channels,
            ),
            converted_payload,
        )
