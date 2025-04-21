import asyncio
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from synchroagent.logic.event_bus import event_bus
from synchroagent.schemas import BaseEventSchema

router = APIRouter(tags=["events"])


@router.get("/stream")
async def stream_events(request: Request) -> EventSourceResponse:
    async def event_generator() -> (
        AsyncGenerator[dict[str, str | int | BaseEventSchema], None]
    ):
        queue: asyncio.Queue[BaseEventSchema] = asyncio.Queue()

        def on_event(data: BaseEventSchema) -> None:
            queue.put_nowait(data)

        event_bus.subscribe("*", on_event)

        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    event: BaseEventSchema = await asyncio.wait_for(
                        queue.get(),
                        timeout=1.0,
                    )
                    yield {
                        "event": event.event_type,
                        "run_id": event.run_id,
                        "data": event.model_dump(mode="json"),
                    }
                except TimeoutError:
                    pass
        finally:
            event_bus.unsubscribe("*", on_event)

    return EventSourceResponse(event_generator())
