from collections import deque
import logging

logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warn,)

class RPCStream(object):
    def __init__(self, stream):
        self.stream = stream
        self.pending_requests = {}
        self.next_request_id = 1
        self.interrupted = False
        self.posted_notifications = deque()


    def post(self, name, args):
        self.posted_notifications.append((name, args,))
        self.stream.interrupt()


    def send(self, method, args, response_cb):
        request_id = self.next_request_id
        # Update request id
        self.next_request_id = request_id + 1
        # Send the request
        self.stream.send([0, request_id, method, args])
        # set the callback
        self.pending_requests[request_id] = response_cb


    def loop_start(self, request_cb, notification_cb, error_cb):
        def msg_cb(msg):
            msg_type = msg[0]
            if msg_type == 0:
                # request
                #   - msg[1]: id
                #   - msg[2]: method name
                #   - msg[3]: arguments
                debug('received request: %s, %s', msg[2], msg[3])
                request_cb(msg[2], msg[3], reply_fn(self.stream, msg[1]))
            elif msg_type == 1:
                # response to a previous request:
                #   - msg[1]: the id
                #   - msg[2]: error(if any)
                #   - msg[3]: result(if not errored)
                debug('received response: %s, %s', msg[2], msg[3])
                self.pending_requests.pop(msg[1])(msg[2], msg[3])
            elif msg_type == 2:
                # notification/event
                #   - msg[1]: event name
                #   - msg[2]: arguments
                debug('received notification: %s, %s', msg[1], msg[2])
                notification_cb(msg[1], msg[2])
            else:
                error = 'Received invalid message %s' % msg
                warn(error)
                raise Exception(error)

        self.stream.loop_start(msg_cb, error_cb)

        while self.posted_notifications:
            notification_cb(*self.posted_notifications.popleft())
            self.stream.loop_start(msg_cb, error_cb)


    def loop_stop(self):
        self.stream.loop_stop()


def reply_fn(stream, request_id):
    def reply(value, error=False):
        if error:
            resp = [1, request_id, value, None]
        else:
            resp = [1, request_id, None, value]
        stream.send(resp)

    return reply
