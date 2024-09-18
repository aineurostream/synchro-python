import numpy as np
import soxr

from synchro.config.commons import StreamConfig
from synchro.config.schemas import ResamplerNodeSchema
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.graph_node import EmittingNodeMixin, GraphNode, ReceivingNodeMixin

INT16_MAX = 32767


class ResampleNode(GraphNode, ReceivingNodeMixin, EmittingNodeMixin):
    def __init__(self, config: ResamplerNodeSchema) -> None:
        super().__init__(config.name)
        self._buffer: list[GraphFrameContainer] = []
        self.output_config: StreamConfig | None = None
        self._to_rate = config.to_rate

    def initialize_edges(
        self,
        inputs: list[StreamConfig],
        outputs: list[StreamConfig],
    ) -> None:
        self.check_inputs_count(inputs, 1)
        self.check_outputs_count(inputs, 1)
        if self._to_rate != outputs[0].rate:
            raise ValueError(
                f"Expected output rate to be {self._to_rate} but got {outputs[0].rate}",
            )

        if inputs[0].rate == self._to_rate:
            raise ValueError(
                f"Resampling is not needed from {inputs[0].rate} in {self.name}",
            )

    def predict_config(
        self,
        inputs: list[StreamConfig],
    ) -> StreamConfig:
        self.check_inputs_count(inputs, 1)
        first_input = inputs[0]
        self.output_config = StreamConfig(
            audio_format=first_input.audio_format,
            language=first_input.language,
            rate=self._to_rate,
        )

        return self.output_config

    def put_data(self, data: list[GraphFrameContainer]) -> None:
        if len(data) != 1:
            raise ValueError(f"Expected one frame container, got {len(data)}")

        self._buffer.append(data[0])

    def get_data(self) -> GraphFrameContainer:
        if self.output_config is None:
            raise ValueError("Output config is not set")

        if not self._buffer:
            return GraphFrameContainer.from_config(
                self.name,
                self.output_config,
                b"",
            )

        initial_payload = b"".join([frame.frame_data for frame in self._buffer])
        from_rate = self._buffer[0].rate
        self._buffer.clear()

        if len(initial_payload) == 0:
            return GraphFrameContainer.from_config(
                self.name,
                self.output_config,
                b"",
            )

        converted_payload_np = np.frombuffer(
            initial_payload,
            dtype=self.output_config.audio_format.numpy_format,
        )
        float_payload_np = converted_payload_np.astype(np.float32) / INT16_MAX
        raw_float_payload = soxr.resample(
            float_payload_np,
            from_rate,
            self._to_rate,
        )
        converted_payload_np = (raw_float_payload * INT16_MAX).astype(
            self.output_config.audio_format.numpy_format,
        )
        converted_payload = converted_payload_np.tobytes()
        self._logger.debug(
            "Resampled %d bytes from %d to %d in %s",
            len(converted_payload),
            from_rate,
            self._to_rate,
            self,
        )

        return GraphFrameContainer.from_config(
            self.name,
            self.output_config,
            converted_payload,
        )
