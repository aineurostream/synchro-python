import logging

import numpy as np

from synchro.audio.frame_container import FrameContainer
from synchro.config.schemas import (
    DenoiserNodeSchema,
)
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

logger = logging.getLogger(__name__)


class DenoiserNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: DenoiserNodeSchema) -> None:
        super().__init__(config.name)
        self._config = config
        self._buffer: FrameContainer | None = None

    def put_data(self, _source: str, data: FrameContainer) -> None:
        self._buffer = (
            data.clone() if self._buffer is None else self._buffer.append(data)
        )

    def get_data(self) -> FrameContainer | None:
        if not self._buffer:
            return None
        denoised_audio = self._denoise_audio(self._buffer)
        self._buffer = self._buffer.to_empty()
        return denoised_audio

    def _denoise_audio(self, audio: FrameContainer) -> FrameContainer:
        audio_np = np.frombuffer(
            audio.frame_data,
            dtype=audio.audio_format.numpy_format,
        )
        if len(audio_np) == 0:
            return audio.clone()

        frame_size, hop_size = 1024, 512
        if len(audio_np) < frame_size:
            return audio.clone()

        pad_size = (frame_size - len(audio_np) % frame_size) % frame_size
        padded_signal = np.pad(audio_np, (0, pad_size))
        output_signal = np.zeros_like(padded_signal)

        for i in range(0, len(padded_signal) - frame_size + 1, hop_size):
            frame = padded_signal[i : i + frame_size]
            windowed_frame = frame * np.hanning(frame_size)
            fft_frame = np.fft.rfft(windowed_frame)
            magnitude, phase = np.abs(fft_frame), np.angle(fft_frame)
            noise_estimate = np.mean(magnitude) * self._config.threshold
            magnitude = np.maximum(magnitude - noise_estimate, magnitude * 0.1)
            fft_frame = magnitude * np.exp(1j * phase)
            processed_frame = np.fft.irfft(fft_frame) * np.hanning(frame_size)
            output_signal[i : i + frame_size] += processed_frame

        output_signal = output_signal[: len(audio_np)]
        if np.max(np.abs(output_signal)) > 0:
            output_signal = (
                output_signal
                / np.max(np.abs(output_signal))
                * np.iinfo(audio.audio_format.numpy_format).max
                * 0.9
            )

        return audio.with_new_data(
            output_signal.astype(audio.audio_format.numpy_format).tobytes(),
        )
