"""Synchronous msgpack-rpc session layer."""
import logging
import sys
import threading
from collections import deque
from traceback import format_exc
from typing import (Any, AnyStr, Callable, Deque, List, NamedTuple, Optional, Sequence,
                    Tuple, Union, cast)

import greenlet

from pynvim.compat import check_async
from pynvim.msgpack_rpc.async_session import AsyncSession

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal

logger = logging.getLogger(__name__)
error, debug, info, warn = (logger.error, logger.debug, logger.info,
                            logger.warning,)


class Request(NamedTuple):
    """A request from Nvim."""

    type: Literal['request']
    name: str
    args: List[Any]
    response: Any


class Notification(NamedTuple):
    """A notification from Nvim."""

    type: Literal['notification']
    name: str
    args: List[Any]


Message = Union[Request, Notification]


class Session(object):

    """Msgpack-rpc session layer that uses coroutines for a synchronous API.

    This class provides the public msgpack-rpc API required by this library.
    It uses the greenlet module to handle requests and notifications coming
    from Nvim with a synchronous API.
    """

    def __init__(self, async_session: AsyncSession):
        """Wrap `async_session` on a synchronous msgpack-rpc interface."""
        self._async_session = async_session
        self._request_cb: Optional[Callable[[str, List[Any]], None]] = None
        self._notification_cb: Optional[Callable[[str, List[Any]], None]] = None
        self._pending_messages: Deque[Message] = deque()
        self._is_running = False
        self._setup_exception: Optional[Exception] = None
        self.loop = async_session.loop
        self._loop_thread: Optional[threading.Thread] = None
        self.error_wrapper: Callable[[Tuple[int, str]], Exception] = \
            lambda e: Exception(e[1])

    def threadsafe_call(
        self, fn: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> None:
        """Wrapper around `AsyncSession.threadsafe_call`."""
        def handler():
            try:
                fn(*args, **kwargs)
            except Exception:
                warn("error caught while executing async callback\n%s\n",
                     format_exc())

        def greenlet_wrapper():
            gr = greenlet.greenlet(handler)
            gr.switch()

        self._async_session.threadsafe_call(greenlet_wrapper)

    def next_message(self) -> Optional[Message]:
        """Block until a message(request or notification) is available.

        If any messages were previously enqueued, return the first in queue.
        If not, run the event loop until one is received.
        """
        if self._is_running:
            raise Exception('Event loop already running')
        if self._pending_messages:
            return self._pending_messages.popleft()
        self._async_session.run(self._enqueue_request_and_stop,
                                self._enqueue_notification_and_stop)
        if self._pending_messages:
            return self._pending_messages.popleft()
        return None

    def request(self, method: AnyStr, *args: Any, **kwargs: Any) -> Any:
        """Send a msgpack-rpc request and block until as response is received.

        If the event loop is running, this method must have been called by a
        request or notification handler running on a greenlet. In that case,
        send the quest and yield to the parent greenlet until a response is
        available.

        When the event loop is not running, it will perform a blocking request
        like this:
        - Send the request
        - Run the loop until the response is available
        - Put requests/notifications received while waiting into a queue

        If the `async_` flag is present and True, a asynchronous notification
        is sent instead. This will never block, and the return value or error
        is ignored.
        """
        async_ = check_async(kwargs.pop('async_', None), kwargs, False)
        if async_:
            self._async_session.notify(method, args)
            return

        if kwargs:
            raise ValueError("request got unsupported keyword argument(s): {}"
                             .format(', '.join(kwargs.keys())))

        if self._is_running:
            v = self._yielding_request(method, args)
        else:
            v = self._blocking_request(method, args)
        if not v:
            # EOF
            raise OSError('EOF')
        err, rv = v
        if err:
            info("'Received error: %s", err)
            raise self.error_wrapper(err)
        return rv

    def run(self,
            request_cb: Callable[[str, List[Any]], None],
            notification_cb: Callable[[str, List[Any]], None],
            setup_cb: Optional[Callable[[], None]] = None) -> None:
        """Run the event loop to receive requests and notifications from Nvim.

        Like `AsyncSession.run()`, but `request_cb` and `notification_cb` are
        inside greenlets.
        """
        self._request_cb = request_cb
        self._notification_cb = notification_cb
        self._is_running = True
        self._setup_exception = None
        self._loop_thread = threading.current_thread()

        def on_setup() -> None:
            try:
                setup_cb()  # type: ignore[misc]
            except Exception as e:
                self._setup_exception = e
                self.stop()

        if setup_cb:
            # Create a new greenlet to handle the setup function
            gr = greenlet.greenlet(on_setup)
            gr.switch()

        if self._setup_exception:
            error(  # type: ignore[unreachable]
                'Setup error: {}'.format(self._setup_exception)
            )
            raise self._setup_exception

        # Process all pending requests and notifications
        while self._pending_messages:
            msg = self._pending_messages.popleft()
            getattr(self, '_on_{}'.format(msg[0]))(*msg[1:])
        self._async_session.run(self._on_request, self._on_notification)
        self._is_running = False
        self._request_cb = None
        self._notification_cb = None
        self._loop_thread = None

        if self._setup_exception:
            raise self._setup_exception

    def stop(self) -> None:
        """Stop the event loop."""
        self._async_session.stop()

    def close(self) -> None:
        """Close the event loop."""
        self._async_session.close()

    def _yielding_request(
        self, method: AnyStr, args: Sequence[Any]
    ) -> Tuple[Tuple[int, str], Any]:
        gr = greenlet.getcurrent()
        parent = gr.parent

        def response_cb(err, rv):
            debug('response is available for greenlet %s, switching back', gr)
            gr.switch(err, rv)

        self._async_session.request(method, args, response_cb)
        debug('yielding from greenlet %s to wait for response', gr)
        return parent.switch()

    def _blocking_request(
            self, method: AnyStr, args: Sequence[Any]
    ) -> Tuple[Tuple[int, str], Any]:
        result = []

        def response_cb(err, rv):
            result.extend([err, rv])
            self.stop()

        self._async_session.request(method, args, response_cb)
        self._async_session.run(self._enqueue_request,
                                self._enqueue_notification)
        return cast(Tuple[Tuple[int, str], Any], tuple(result))

    def _enqueue_request_and_stop(
        self, name: str, args: List[Any], response: Any
    ) -> None:
        self._enqueue_request(name, args, response)
        self.stop()

    def _enqueue_notification_and_stop(self, name: str, args: List[Any]) -> None:
        self._enqueue_notification(name, args)
        self.stop()

    def _enqueue_request(self, name: str, args: List[Any], response: Any) -> None:
        self._pending_messages.append(Request('request', name, args, response,))

    def _enqueue_notification(self, name: str, args: List[Any]) -> None:
        self._pending_messages.append(Notification('notification', name, args,))

    def _on_request(self, name, args, response):
        def handler():
            try:
                rv = self._request_cb(name, args)
                debug('greenlet %s finished executing, '
                      + 'sending %s as response', gr, rv)
                response.send(rv)
            except ErrorResponse as err:
                debug("error response from request '%s %s': %s",
                      name, args, format_exc())
                response.send(err.args[0], error=True)
            except Exception as err:
                warn("error caught while processing request '%s %s': %s",
                     name, args, format_exc())
                response.send(repr(err) + "\n" + format_exc(5), error=True)
            debug('greenlet %s is now dying...', gr)

        # Create a new greenlet to handle the request
        gr = greenlet.greenlet(handler)
        debug('received rpc request, greenlet %s will handle it', gr)
        gr.switch()

    def _on_notification(self, name, args):
        def handler():
            try:
                self._notification_cb(name, args)
                debug('greenlet %s finished executing', gr)
            except Exception:
                warn("error caught while processing notification '%s %s': %s",
                     name, args, format_exc())

            debug('greenlet %s is now dying...', gr)

        gr = greenlet.greenlet(handler)
        debug('received rpc notification, greenlet %s will handle it', gr)
        gr.switch()


class ErrorResponse(BaseException):

    """Raise this in a request handler to respond with a given error message.

    Unlike when other exceptions are caught, this gives full control off the
    error response sent. When "ErrorResponse(msg)" is caught "msg" will be
    sent verbatim as the error response.No traceback will be appended.
    """

    pass
