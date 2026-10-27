"""
event_routes.py - GET /events : the live notification stream (Server-Sent Events).

The browser reads this with fetch() (so the login token is sent in the normal
Authorization header, never in the URL). A ": ping" line every 15 seconds keeps
the connection alive through proxies.
"""
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.auth import ANY_USER
from app.services.events import event_bus

router = APIRouter(tags=["Live notifications"])
PING_SECONDS = 15


@router.get("/events")
async def events(request: Request, current_user: dict = Depends(ANY_USER)):
    sub_id, queue = event_bus.subscribe(current_user["role"])

    async def stream():
        try:
            yield "event: hello\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=PING_SECONDS)
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            event_bus.unsubscribe(sub_id)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
