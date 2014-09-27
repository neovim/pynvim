"""Msgpack handling in the event loop pipeline."""
import logging
from collections import deque

from msgpack import Packer, Unpacker


logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warn,)


class MsgpackStream(object):

    """Two-way msgpack stream that wraps a event loop byte stream.

    This wraps the event loop interface for reading/writing bytes and
    exposes an interface for reading/writing msgpack documents.
    """

    def __init__(self, event_loop):
        """Wrap `event_loop` on a msgpack-aware interface."""
        self._event_loop = event_loop
        self._posted = deque()
        self._packer = Packer(use_bin_type=True)
        self._unpacker = Unpacker()
        self._message_cb = None
        self._stopped = False

    def post(self, msg):
        """Post `msg` to the read queue of the `MsgpackStream` instance.

        Use the event loop `interrupt()` method to push msgpack objects from
        other threads.
        """
        self._posted.append(msg)
        self._event_loop.interrupt()

    def send(self, msg):
        """Queue `msg` for sending to Nvim."""
        debug('sent %s', msg)
        self._event_loop.send(self._packer.pack(msg))

    def run(self, message_cb):
        """Run the event loop to receive messages from Nvim.

        While the event loop is running, `message_cb` will be called whenever
        a message has been successfully parsed from the input stream.
        """
        self._message_cb = message_cb
        self._run()
        self._message_cb = None

    def stop(self):
        """Stop the event loop."""
        self._stopped = True
        self._event_loop.stop()

    def _run(self):
        self._stopped = False
        while not self._stopped:
            if self._posted:
                self._message_cb(self._posted.popleft())
                continue
            self._event_loop.run(self._on_data)

    def _on_data(self, data):
        self._unpacker.feed(data)
        while True:
            try:
                debug('waiting for message...')
                msg = next(self._unpacker)
                debug('received message: %s', msg)
                self._message_cb(msg)
            except StopIteration:
                debug('unpacker needs more data...')
                break
