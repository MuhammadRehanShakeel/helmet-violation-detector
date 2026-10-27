"""
events.py - Live notifications ("a new violation was just detected").

How it works (Server-Sent Events, SSE):
  * every logged-in browser keeps ONE open request to GET /events
  * when something happens (new violation, a job finishes, a camera goes offline ...)
    the backend calls event_bus.publish({...}) and every open browser receives it at once
  * no extra server or library is needed - it is plain HTTP, so it also passes the Vite proxy

publish() can be called from any thread (the job worker, camera threads ...);
each browser has its own small queue inside the web server's event loop.

Used by: app/routes/event_routes.py and everything that publishes events.
"""
import asyncio
import logging
import threading

log = logging.getLogger("events")
QUEUE_SIZE = 100


class EventBus:
    def __init__(self):
        self._subscribers = {}           # id -> (loop, queue, role)
        self._lock = threading.Lock()
        self._next = 1

    def subscribe(self, role: str):
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        with self._lock:
            sub_id = self._next
            self._next += 1
            self._subscribers[sub_id] = (loop, queue, role)
        return sub_id, queue

    def unsubscribe(self, sub_id):
        with self._lock:
            self._subscribers.pop(sub_id, None)

    def count(self):
        return len(self._subscribers)

    def publish(self, event: dict, roles=("admin", "officer", "viewer")):
        """Send an event to every connected user whose role is in `roles`. Never raises."""
        with self._lock:
            targets = list(self._subscribers.values())
        for loop, queue, role in targets:
            if role not in roles:
                continue
            payload = dict(event)
            if role == "viewer" and payload.get("plate"):
                from app.core.auth import mask_plate
                payload["plate"] = mask_plate(payload["plate"], "viewer")
            try:
                loop.call_soon_threadsafe(_put, queue, payload)
            except RuntimeError:                     # that browser's loop is gone
                pass


def _put(queue, payload):
    if queue.full():                                 # a slow browser loses the oldest event, never blocks us
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    queue.put_nowait(payload)


event_bus = EventBus()
