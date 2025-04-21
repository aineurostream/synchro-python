import logging
import threading
from collections import defaultdict
from collections.abc import Callable

from synchroagent.schemas import BaseEventSchema

logger = logging.getLogger(__name__)

EventHandler = Callable[[BaseEventSchema], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            self._subscribers[event_type].append(handler)
            logger.debug(f"Subscribed to event type: {event_type}")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            if (
                event_type in self._subscribers
                and handler in self._subscribers[event_type]
            ):
                self._subscribers[event_type].remove(handler)
                logger.debug(f"Unsubscribed from event type: {event_type}")

    def emit(self, data: BaseEventSchema) -> None:
        handlers = []
        with self._lock:
            handlers.extend(self._subscribers.get(data.event_type, []))
            handlers.extend(self._subscribers.get("*", []))

        for handler in handlers:
            try:
                logger.debug(f"Emitting event {data.event_type} to handler: {handler}")
                handler(data)
            except Exception:
                logger.exception(f"Error in event handler for {data.event_type}")


event_bus = EventBus()
