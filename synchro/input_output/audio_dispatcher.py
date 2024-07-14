from collections import defaultdict
from contextlib import suppress
from multiprocessing import Queue
from queue import Empty

from synchro.input_output.schemas import InputStreamEntity, OutputStreamEntity


class AudioDispatcher:
    def __init__(
        self,
        inputs: list[InputStreamEntity],
        outputs: list[OutputStreamEntity],
    ) -> None:
        self._inputs = inputs
        self._outputs = outputs
        self._lang_queues: dict[str, Queue] = defaultdict(Queue)

    def process_batch(self) -> None:
        self._process_inputs()
        self._process_outputs()

    def _process_inputs(self) -> None:
        for process in self._inputs:
            with suppress(Empty):
                frames = process.queue.get(block=False)
                self._lang_queues[process.config.language].put(frames)

    def _process_outputs(self) -> None:
        for process in self._outputs:
            with suppress(Empty):
                frames = self._lang_queues[process.config.language].get(block=False)
                process.queue.put(frames)
