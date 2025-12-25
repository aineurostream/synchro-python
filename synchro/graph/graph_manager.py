import logging
import time
from contextlib import suppress
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread, Event
from typing import Callable

from pydantic import BaseModel, ConfigDict

from synchro.audio.frame_container import FrameContainer
from synchro.config.settings import SettingsSchema
from synchro.graph.graph_edge import GraphEdge
from synchro.graph.graph_exceptions import StopGraph
from synchro.graph.graph_node import (
    EmittingNodeMixin,
    GraphNode,
    ReceivingNodeMixin,
)

MS_IN_SEC = 1000.0

logger = logging.getLogger(__name__)


class EdgeQueue(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    edge: GraphEdge
    queue: Queue[FrameContainer]

    def __repr__(self) -> str:
        return f"-[{self.edge}]-"


class NodeExecutor(Thread):
    def __init__(
        self,
        settings: SettingsSchema,
        node: GraphNode,
        incoming: list[EdgeQueue],
        outgoing: list[EdgeQueue],
        on_fatal: Callable | None = None,
    ) -> None:
        super().__init__(name=node.name)
        self.node = node
        self._settings = settings
        self._running = True
        self._incoming = incoming
        self._outgoing = outgoing
        self._stop_evt = Event()
        self._on_fatal = on_fatal
        self.local_exception: Exception | None = None
        logger.debug(
            "NodeExecutor created for %s\n(incoming: %s, outgoing: %s)",
            node,
            incoming,
            outgoing,
        )

    def stop(self) -> None:
        self._running = False
        self._stop_evt.set()

    def run(self) -> None:
        try:
            emitting_only_node = not isinstance(self.node, ReceivingNodeMixin)
            with self.node:
                while self._running:
                    self.process_inputs()
                    self.process_outputs()

                    interval = (
                        self._settings.input_interval_secs 
                        if emitting_only_node else 
                        self._settings.processor_interval_secs
                    )
                    
                    if self._stop_evt.wait(timeout=interval):
                        break
        except StopGraph as exc:
            logger.info("Node %s requested graceful shutdown: %s", self.node.name, exc)
            self._running = False
            self.local_exception = None
            if self._on_fatal:
                self._on_fatal(None)
        except Exception as exc:
            logger.exception("Exception in NodeExecutor for %s:", self.node.name)
            self._running = False
            self.local_exception = exc
            if self._on_fatal:
                self._on_fatal(exc)  # ← попросить остановку всей системы

    def process_outputs(self) -> None:
        if isinstance(self.node, EmittingNodeMixin):
            outgoing_data = self.node.get_data()
            if outgoing_data:
                for out in self._outgoing:
                    logger.debug(
                        "Sending %s bytes %s",
                        len(outgoing_data.frame_data),
                        out.edge,
                    )
                    out.queue.put(outgoing_data)

    def process_inputs(self) -> None:
        if isinstance(self.node, ReceivingNodeMixin):
            for inc in self._incoming:
                with suppress(Empty):
                    incoming_data = inc.queue.get(block=False)
                    if incoming_data:
                        self.node.put_data(
                            inc.edge.source,
                            incoming_data,
                        )


class GraphManager:
    def __init__(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        settings: SettingsSchema,
        working_dir: str | None = None,
    ) -> None:
        self._nodes: dict[str, GraphNode] = {node.name: node for node in nodes}
        self._edges: list[GraphEdge] = edges
        self._settings: SettingsSchema = settings
        self._executing: bool = False
        self._lock: Lock = Lock()
        self._active_threads: list[NodeExecutor] = []
        self._exception_check_thread: Thread | None = None
        self._shutdown_evt = Event()
        self._first_exception: Exception | None = None
        self._working_dir: str | None = working_dir

    def _check_for_exceptions(self) -> None:
        while self._executing:
            for thread in self._active_threads:
                if thread.local_exception is not None:
                    logger.error(
                        "Exception detected in thread %s, stopping all execution",
                        thread.name,
                    )
                    # сохраняем и останавливаемся; НЕ raise здесь
                    self._first_exception = thread.local_exception
                    self.request_shutdown(None)
                    return
                
            time.sleep(0.1)

    def _reraise_worker_exception_if_any(self) -> None:
        if self._first_exception is not None:
            exc = self._first_exception
            self._first_exception = None
            raise exc
        
    def request_shutdown(self, exc: Exception | None = None) -> None:
        if exc and self._first_exception is None:
            self._first_exception = exc
        self._shutdown_evt.set()

    def execute(self) -> None:
        with self._lock:
            if self._executing:
                raise RuntimeError("Graph is already executing")
            self._executing = True

        logger.info("Starting Synchro graph execution")

        def activate_thread(created_thread: NodeExecutor) -> None:
            created_thread.start()
            self._active_threads.append(created_thread)
            logger.info("Executing of node %s started", created_thread.node.name)

        def _on_node_fatal(exc: Exception | None) -> None:
            self.request_shutdown(exc)

        queued_edges = {
            edge.id: EdgeQueue(
                edge=edge,
                queue=Queue(),
            )
            for edge in self._edges
        }

        self._exception_check_thread = Thread(
            target=self._check_for_exceptions,
            name="ExceptionChecker",
        )
        self._exception_check_thread.daemon = True
        self._exception_check_thread.start()

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

            thread = NodeExecutor(
                self._settings, 
                node, 
                incoming, 
                outgoing,
                on_fatal=_on_node_fatal,
            )
            activate_thread(thread)

        run_time_limit = self._settings.limits.run_time_seconds
        if run_time_limit > 0:
            logger.info(
                "Synchro instance will run for %d seconds",
                run_time_limit,
            )

            def stop_execution() -> None:
                time.sleep(float(run_time_limit))
                logger.info("Stopping Synchro instance due to time limit")
                self.stop()

            Thread(target=stop_execution, name="RunTimeLimiter", daemon=True).start()

        try:
            while self._executing and not self._shutdown_evt.wait(timeout=0.5):
                logger.info("Synchro instance wait for stop...")
        except KeyboardInterrupt:
            logger.info("Stopping Synchro instance due to KeyboardInterrupt")
            self.request_shutdown(None)
        finally:
            # ensure all workers are stopped when we leave the loop for any reason
            self.stop()
            logger.info("Synchro instance stopped")
            # критично: после выхода проверим, не было ли исключений в воркерах
            self._reraise_worker_exception_if_any()

    def stop(self) -> None:
        if not self._executing:
            return

        with self._lock:
            logger.info("Synchro instance stopping")
            self._executing = False
            for thread in self._active_threads:
                thread.stop()
            for thread in self._active_threads:
                if thread.is_alive():
                    thread.join()  # без таймаута

            self._active_threads = []

            logger.info("All threads completed - finishing instance execution")
