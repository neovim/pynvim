"""Msgpack handling in the event loop pipeline."""
import logging

from msgpack import Packer, Unpacker

from pynvim.compat import unicode_errors_default
from pynvim.msgpack_rpc.event_loop.base import BaseEventLoop

logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warning,)


class MsgpackStream:
    """Two-way msgpack stream that wraps a event loop byte stream.

    This wraps the event loop interface for reading/writing bytes and
    exposes an interface for reading/writing msgpack documents.
    """

    def __init__(self, event_loop: BaseEventLoop) -> None:
        """Wrap `event_loop` on a msgpack-aware interface."""
        self.loop = event_loop
        self._packer = Packer(unicode_errors=unicode_errors_default)
        self._unpacker = Unpacker(unicode_errors=unicode_errors_default)
        self._message_cb = None

    def threadsafe_call(self, fn):
        """Wrapper around `BaseEventLoop.threadsafe_call`."""
        self.loop.threadsafe_call(fn)

    def send(self, msg):
        """Queue `msg` for sending to Nvim."""
        debug('sending %s', msg)
        self.loop.send(self._packer.pack(msg))

    def run(self, message_cb):
        """Run the event loop to receive messages from Nvim.

        While the event loop is running, `message_cb` will be called whenever
        a message has been successfully parsed from the input stream.
        """
        self._message_cb = message_cb
        self.loop.run(self._on_data)
        self._message_cb = None

    def stop(self):
        """Stop the event loop."""
        self.loop.stop()

    def close(self):
        """Close the event loop."""
        self.loop.close()

    def _on_data(self, data: bytes) -> None:
        self._unpacker.feed(data)
        while True:
            try:
                debug('waiting for message...')
                msg = next(self._unpacker)
                debug('received message: %s', msg)
                assert self._message_cb is not None
                self._message_cb(msg)  # type: ignore[unreachable]
            except StopIteration:
                debug('unpacker needs more data...')
                break
