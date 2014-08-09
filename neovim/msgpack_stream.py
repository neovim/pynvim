import msgpack, logging

logger = logging.getLogger(__name__)
debug, warn = (logger.debug, logger.warn,)

class MsgpackStream(object):
    def __init__(self, stream):
        self.stream = stream
        self.unpacker = msgpack.Unpacker()


    def interrupt(self):
        self.stream.interrupt()


    def send(self, msg):
        self.stream.send(msgpack.packb(msg))


    def loop_start(self, msg_cb, error_cb):
        def data_cb(data):
            self.unpacker.feed(data)

            while True:
                try:
                    debug('waiting for message...')
                    msg = self.unpacker.next()
                    debug('received message: %s', msg)
                    msg_cb(msg)
                except StopIteration:
                    debug('unpacker needs more data...')
                    break

        self.stream.loop_start(data_cb, error_cb)


    def loop_stop(self):
        self.stream.loop_stop()
