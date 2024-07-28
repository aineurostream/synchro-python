from typing import cast

import numpy as np

from synchro.input_output.frame_container import FrameContainer


class AudioMixer:
    @staticmethod
    def mix_frames(frames: list[FrameContainer]) -> bytes:
        min_length_frames = 0
        for frame in frames:
            current_frame_length = len(frame)
            if min_length_frames > current_frame_length or min_length_frames == 0:
                min_length_frames = current_frame_length

        if min_length_frames == 0:
            return b""

        audio_matrix = np.zeros((len(frames), min_length_frames), dtype=np.int16)
        for i, frame in enumerate(frames):
            audio_matrix[i] = np.frombuffer(
                frame.frame_data,
                dtype=np.int16,
            )[:min_length_frames]

        return cast(bytes, np.mean(audio_matrix, axis=0).astype(np.int16).tobytes())
