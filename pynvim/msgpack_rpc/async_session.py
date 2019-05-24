"""Asynchronous msgpack-rpc handling in the event loop pipeline."""
import logging
from traceback import format_exc


logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warning,)


class AsyncSession(object):

    """Asynchronous msgpack-rpc layer that wraps a msgpack stream.

    This wraps the msgpack stream interface for reading/writing msgpack
    documents and exposes an interface for sending and receiving msgpack-rpc
    requests and notifications.
    """

    def __init__(self, msgpack_stream):
        """Wrap `msgpack_stream` on a msgpack-rpc interface."""
        self._msgpack_stream = msgpack_stream
        self._next_request_id = 1
        self._pending_requests = {}
        self._request_cb = self._notification_cb = None
        self._handlers = {
            0: self._on_request,
            1: self._on_response,
            2: self._on_notification
        }
        self.loop = msgpack_stream.loop

    def threadsafe_call(self, fn):
        """Wrapper around `MsgpackStream.threadsafe_call`."""
        self._msgpack_stream.threadsafe_call(fn)

    def request(self, method, args, response_cb):
        """Send a msgpack-rpc request to Nvim.

        A msgpack-rpc with method `method` and argument `args` is sent to
        Nvim. The `response_cb` function is called with when the response
        is available.
        """
        request_id = self._next_request_id
        self._next_request_id = request_id + 1
        self._msgpack_stream.send([0, request_id, method, args])
        self._pending_requests[request_id] = response_cb

    def notify(self, method, args):
        """Send a msgpack-rpc notification to Nvim.

        A msgpack-rpc with method `method` and argument `args` is sent to
        Nvim. This will have the same effect as a request, but no response
        will be recieved
        """
        self._msgpack_stream.send([2, method, args])

    def run(self, request_cb, notification_cb):
        """Run the event loop to receive requests and notifications from Nvim.

        While the event loop is running, `request_cb` and `notification_cb`
        will be called whenever requests or notifications are respectively
        available.
        """
        self._request_cb = request_cb
        self._notification_cb = notification_cb
        self._msgpack_stream.run(self._on_message)
        self._request_cb = None
        self._notification_cb = None

    def stop(self):
        """Stop the event loop."""
        self._msgpack_stream.stop()

    def close(self):
        """Close the event loop."""
        self._msgpack_stream.close()

    def _on_message(self, msg):
        try:
            self._handlers.get(msg[0], self._on_invalid_message)(msg)
        except Exception:
            err_str = format_exc(5)
            warn(err_str)
            self._msgpack_stream.send([1, 0, err_str, None])

    def _on_request(self, msg):
        # request
        #   - msg[1]: id
        #   - msg[2]: method name
        #   - msg[3]: arguments
        debug('received request: %s, %s', msg[2], msg[3])
        self._request_cb(msg[2], msg[3], Response(self._msgpack_stream,
                                                  msg[1]))

    def _on_response(self, msg):
        # response to a previous request:
        #   - msg[1]: the id
        #   - msg[2]: error(if any)
        #   - msg[3]: result(if not errored)
        debug('received response: %s, %s', msg[2], msg[3])
        self._pending_requests.pop(msg[1])(msg[2], msg[3])

    def _on_notification(self, msg):
        # notification/event
        #   - msg[1]: event name
        #   - msg[2]: arguments
        debug('received notification: %s, %s', msg[1], msg[2])
        self._notification_cb(msg[1], msg[2])

    def _on_invalid_message(self, msg):
        error = 'Received invalid message %s' % msg
        warn(error)
        self._msgpack_stream.send([1, 0, error, None])


class Response(object):

    """Response to a msgpack-rpc request that came from Nvim.

    When Nvim sends a msgpack-rpc request, an instance of this class is
    created for remembering state required to send a response.
    """

    def __init__(self, msgpack_stream, request_id):
        """Initialize the Response instance."""
        self._msgpack_stream = msgpack_stream
        self._request_id = request_id

    def send(self, value, error=False):
        """Send the response.

        If `error` is True, it will be sent as an error.
        """
        if error:
            resp = [1, self._request_id, value, None]
        else:
            resp = [1, self._request_id, None, value]
        debug('sending response to request %d: %s', self._request_id, resp)
        self._msgpack_stream.send(resp)
