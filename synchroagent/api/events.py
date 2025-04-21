import asyncio
from collections.abc import AsyncGenerator
from contextlib import suppress

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from synchroagent.logic.event_bus import event_bus
from synchroagent.schemas import BaseEventSchema, LogEventSchema
import logging

router = APIRouter(tags=["events"])
logger = logging.getLogger(__name__)


@router.get("/stream")
async def stream_events(request: Request) -> EventSourceResponse:
    async def event_generator() -> (
        AsyncGenerator[dict[str, str | int | BaseEventSchema], None]
    ):
        yield {"event": "connected", "data": "connected"}
        queue: asyncio.Queue[BaseEventSchema] = asyncio.Queue()

        def on_event(data: BaseEventSchema) -> None:
            logger.debug(f"Event received in API: {data.event_type}")
            queue.put_nowait(data)

        event_bus.subscribe("*", on_event)
        logger.info("Subscribed to events for streaming")

        try:
            while True:
                if await request.is_disconnected():
                    logger.info("Client disconnected, stopping event stream")
                    break
                with suppress(asyncio.QueueEmpty):
                    logger.debug(f"Waiting for event from queue")                    
                    event: BaseEventSchema = queue.get_nowait()
                    logger.debug(f"Sending event to client: {event.event_type}")
                    yield {
                        "event": event.event_type,
                        "data": event.model_dump(mode="json"),
                    }
        finally:
            event_bus.unsubscribe("*", on_event)
            logger.info("Unsubscribed from events")

    logger.info("Starting event stream: %s", request.url)
    return EventSourceResponse(event_generator())
