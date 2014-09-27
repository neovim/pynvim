"""Synchronous msgpack-rpc session layer."""
import logging
from collections import deque

import greenlet


logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warn,)


class Session(object):

    """Msgpack-rpc session layer that uses coroutines for a synchronous API.

    This class provides the public msgpack-rpc API required by this library.
    It uses the greenlet module to handle requests and notifications coming
    from Nvim with a synchronous API.
    """

    def __init__(self, async_session):
        """Wrap `async_session` on a synchronous msgpack-rpc interface."""
        self._async_session = async_session
        self._greenlets = set()
        self._request_cb = self._notification_cb = None
        self._pending_messages = deque()
        self._is_running = False

    def post(self, name, *args):
        """Simple wrapper around `AsyncSession.post`."""
        self._async_session.post(name, args)

    def next_message(self):
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
        return self._pending_messages.popleft()

    def request(self, method, *args):
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
        """
        if self._is_running:
            err, rv = self._yielding_request(method, args)
        else:
            err, rv = self._blocking_request(method, args)
        if err:
            info("'Received error: %s", err)
            raise self.error_wrapper(err)
        return rv

    def run(self, request_cb, notification_cb):
        """Run the event loop to receive requests and notifications from Nvim.

        Like `AsyncSession.run()`, but `request_cb` and `notification_cb` are
        inside greenlets.
        """
        self._request_cb = request_cb
        self._notification_cb = notification_cb
        self._is_running = True
        # Process all pending requests and notifications
        while self._pending_messages:
            msg = self._pending_messages.popleft()
            getattr(self, '_on_{0}'.format(msg[0]))(*msg[1:])
        self._async_session.run(self._on_request, self._on_notification)
        self._is_running = False
        self._request_cb = None
        self._notification_cb = None

    def stop(self):
        """Stop the event loop."""
        self._async_session.stop()

    def _yielding_request(self, method, args):
        gr = greenlet.getcurrent()
        parent = gr.parent

        def response_cb(err, rv):
            debug('response is available for greenlet %s, switching back', gr)
            gr.switch(err, rv)

        self._async_session.request(method, args, response_cb)
        debug('yielding from greenlet %s to wait for response', gr)
        return parent.switch()

    def _blocking_request(self, method, args):
        result = []

        def response_cb(err, rv):
            result.extend([err, rv])
            self.stop()

        self._async_session.request(method, args, response_cb)
        self._async_session.run(self._enqueue_request,
                                self._enqueue_notification)
        return result

    def _enqueue_request_and_stop(self, name, args, response):
        self._enqueue_request(name, args, response)
        self.stop()

    def _enqueue_notification_and_stop(self, name, args):
        self._enqueue_notification(name, args)
        self.stop()

    def _enqueue_request(self, name, args, response):
        self._pending_messages.append(('request', name, args, response,))

    def _enqueue_notification(self, name, args):
        self._pending_messages.append(('notification', name, args,))

    def _on_request(self, name, args, response):
        def handler():
            try:
                rv = self._request_cb(name, args)
                debug('greenlet %s finished executing, ' +
                      'sending %s as response', gr, rv)
                response.send(rv)
            except Exception as err:
                warn("error caught while processing request '%s %s': %s", name,
                     args, err)
                response.send(repr(err), error=True)
            debug('greenlet %s is now dying...', gr)
            self._greenlets.remove(gr)

        # Create a new greenlet to handle the request
        gr = greenlet.greenlet(handler)
        debug('received rpc request, greenlet %s will handle it', gr)
        self._greenlets.add(gr)
        gr.switch()

    def _on_notification(self, name, args):
        def handler():
            try:
                self._notification_cb(name, args)
                debug('greenlet %s finished executing', gr)
            except Exception as e:
                warn("error caught while processing notification '%s %s': %s",
                     name, args, e)
            debug('greenlet %s is now dying...', gr)
            self._greenlets.remove(gr)

        gr = greenlet.greenlet(handler)
        debug('received rpc notification, greenlet %s will handle it', gr)
        self._greenlets.add(gr)
        gr.switch()
