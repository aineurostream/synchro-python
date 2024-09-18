import logging
import time
from collections import defaultdict
from contextlib import suppress
from queue import Empty, Queue
from threading import Thread

from pydantic import BaseModel, ConfigDict

from synchro.config.commons import MIN_STEP_LENGTH_SECS, StreamConfig
from synchro.graph.graph_edge import GraphEdge
from synchro.graph.graph_frame_container import GraphFrameContainer
from synchro.graph.graph_node import (
    ContextualGraphNode,
    EmittingNodeMixin,
    GraphNode,
    ReceivingNodeMixin,
)

MS_IN_SEC = 1000.0

WAIT_PRECENT_OF_PREV_FRAME = 0.9

logger = logging.getLogger(__name__)


class EdgeQueue(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    edge: GraphEdge
    queue: Queue[GraphFrameContainer]

    def __repr__(self) -> str:
        return f"-[{self.edge}]-"


class NodeExecutor(Thread):
    def __init__(
        self,
        node: GraphNode,
        incoming: list[EdgeQueue],
        outgoing: list[EdgeQueue],
    ) -> None:
        super().__init__()
        self.node = node
        self._running = True
        self._incoming = incoming
        self._outgoing = outgoing
        logger.debug(
            "NodeExecutor created for %s\n(incoming: %s, outgoing: %s)",
            node,
            incoming,
            outgoing,
        )

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        if isinstance(self.node, ContextualGraphNode):
            with self.node:
                self.run_processing_loop()
        else:
            self.run_processing_loop()

    def run_processing_loop(self) -> None:
        while self._running:
            self.process_inputs()
            sleep_time = self.process_outputs()
            time.sleep(
                max(
                    MIN_STEP_LENGTH_SECS,
                    sleep_time,
                ),
            )

    def process_outputs(self) -> float:
        if isinstance(self.node, EmittingNodeMixin):
            outgoing_data = self.node.get_data()
            if len(outgoing_data) > 0:
                for out in self._outgoing:
                    logger.debug(
                        "Sending %s bytes %s",
                        len(outgoing_data.frame_data),
                        out.edge,
                    )
                    out.queue.put(outgoing_data)

                return (
                    outgoing_data.length_ms() / MS_IN_SEC * WAIT_PRECENT_OF_PREV_FRAME
                )

        return 0.0

    def process_inputs(self) -> None:
        if isinstance(self.node, ReceivingNodeMixin):
            incoming_data: list[GraphFrameContainer] = []
            for inc in self._incoming:
                with suppress(Empty):
                    incoming_data.append(inc.queue.get(block=False))

            if len(incoming_data) > 0 and sum(len(data) for data in incoming_data) > 0:
                logger.debug("Received %s packages for %s", incoming_data, self.node)
                self.node.put_data(incoming_data)


class GraphManager:
    def __init__(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        self._nodes = {node.name: node for node in nodes}
        self._edges = edges
        self._executing = False

    def execute(self) -> None:
        if self._executing:
            raise RuntimeError("Graph is already executing")
        self._executing = True
        logger.info("Synchro graph warm up")
        self._warmup_graph()

        logger.info("Starting Synchro graph execution")
        active_threads: list[NodeExecutor] = []

        def activate_thread(created_thread: NodeExecutor) -> None:
            created_thread.start()
            active_threads.append(created_thread)
            logger.info("Executing of node %s started", created_thread.node.name)

        queued_edges = {
            edge.id: EdgeQueue(
                edge=edge,
                queue=Queue(),
            )
            for edge in self._edges
        }

        for node in self._nodes.values():
            incoming = [
                queued_edges[edge.id]
                for edge in self._edges
                if edge.target == node.name
            ]
            outgoing = [
                queued_edges[edge.id]
                for edge in self._edges
                if edge.source == node.name
            ]
            activate_thread(NodeExecutor(node, incoming, outgoing))

        # Wait for interruption
        with suppress(KeyboardInterrupt):
            while self._executing:
                time.sleep(0.1)

        self.stop()
        for thread in active_threads:
            thread.stop()
        logger.info("Synchro instance stopping")

        logger.info("Waiting for threads to finish")
        for thread in active_threads:
            thread.join()
        logger.info("All threads completed - finishing instance execution")

    def stop(self) -> None:
        self._executing = False

    def _warmup_graph(self) -> None:
        starting_nodes: list[GraphNode] = []
        preferred_inputs: dict[str, list[StreamConfig]] = defaultdict(list)
        resulting_inputs: dict[str, StreamConfig] = {}
        visited_nodes: set[str] = set()
        logger.debug("Warming up graph")
        starting_nodes += [
            node
            for node in self._nodes.values()
            if not any(edge.target == node.name for edge in self._edges)
        ]

        while len(starting_nodes) > 0:
            node = starting_nodes.pop()
            visited_nodes.add(node.name)

            outgoing_config = node.predict_config(
                preferred_inputs[node.name],
            )
            resulting_inputs[node.name] = outgoing_config
            logger.debug("Warm up node %s resulted in %s", node, outgoing_config)
            for edge in self._edges:
                if edge.source == node.name:
                    target_node = self._nodes[edge.target]
                    preferred_inputs[edge.target].append(outgoing_config)
                    if target_node.name not in visited_nodes:
                        starting_nodes.append(target_node)

        for node in self._nodes.values():
            inputs = [edge for edge in self._edges if edge.target == node.name]
            outputs = [edge for edge in self._edges if edge.source == node.name]
            node.initialize_edges(
                inputs=[
                    resulting_inputs[edge.source]
                    for edge in inputs
                    if edge.source in resulting_inputs
                ],
                outputs=[
                    resulting_inputs[edge.target]
                    for edge in outputs
                    if edge.target in resulting_inputs
                ],
            )

        for init_node, results in resulting_inputs.items():
            logger.info("Node %s initialized with %s", init_node, results)
        logger.debug("Warming up graph finished")
