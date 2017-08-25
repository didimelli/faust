"""Async I/O Future utilities."""
import asyncio
from functools import singledispatch
from typing import Any, Awaitable, Optional

__all__ = [
    'FlowControlEvent', 'FlowControlQueue',
    'done_future', 'maybe_async', 'notify',
]


def done_future(result: Any = None, *,
                loop: asyncio.AbstractEventLoop = None) -> asyncio.Future:
    """Returns :class:`asyncio.Future` that is already evaluated."""
    f = (loop or asyncio.get_event_loop()).create_future()
    f.set_result(result)
    return f


def notify(fut: Optional[asyncio.Future], result: Any = None) -> None:
    # can be used to turn a Future into a lockless, single-consumer condition,
    # for multi-consumer use asyncio.Condition
    if fut is not None and not fut.done():
        fut.set_result(result)


@singledispatch
async def maybe_async(res: Any) -> Any:
    """Await future if argument is awaitable.

    Examples:
        >>> await maybe_async(regular_function(arg))
        >>> await maybe_async(async_function(arg))
    """
    return res


@maybe_async.register(Awaitable)
async def _(res: Awaitable) -> Any:
    return await res


class FlowControlEvent:

    def __init__(self, *, loop: asyncio.AbstractEventLoop = None) -> None:
        self.loop = loop or asyncio.get_event_loop()
        self._resume = asyncio.Event(loop=self.loop)
        self._suspend = asyncio.Event(loop=self.loop)

    def suspend(self) -> None:
        self._resume.clear()
        self._suspend.set()

    def is_active(self) -> bool:
        return not self._suspend.is_set()

    def resume(self) -> None:
        self._suspend.clear()
        self._resume.set()

    async def acquire(self) -> None:
        if self._suspend.is_set():
            await self._resume.wait()


class FlowControlQueue(asyncio.Queue):

    def __init__(self, maxsize: int = 0,
                 *,
                 flow_control: FlowControlEvent = None,
                 **kwargs: Any) -> None:
        self._flow_control = flow_control
        super().__init__(maxsize, **kwargs)

    async def get(self) -> Any:  # type: ignore
        await self._flow_control.acquire()
        return await super().get()
