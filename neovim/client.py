import msgpack
import traceback
from collections import deque
from threading import Condition, Lock
from time import time
from mixins import mixins
from util import VimError


class Promise(object):
    def __init__(self, client, request_id, expected_type=None):
        def process_response(message):
            if message.error:
                # error
                raise VimError(message.error)
            if expected_type and hasattr(client.vim, expected_type):
                # result should be a handle, wrap in it's specialized class
                klass = getattr(client.vim, expected_type)
                rv = klass(client.vim, message.result)
                klass.initialize(rv)
                return rv
            return message.result

        def wait(timeout=None):
            interrupted = False
            while True:
                if interrupted:
                    with client.interrupt_lock:
                        pass
                with client.stream_lock:
                    if self.message:
                        return process_response(self.message)
                    interrupted = client.queue_message(timeout)

        self.message = None
        self.wait = wait

class Message(object):
    def __init__(self, client, name=None, arg=None, result=None, error=None,
                 request_id=None, response_id=None, ):
        def reply(value, is_error=False):
            if is_error:
                resp = msgpack.packb([1, request_id, value, None])
            else:
                resp = msgpack.packb([1, request_id, None, value])
            client.stream.write(resp)
        self.name = name
        self.arg = arg
        self.result = result
        self.error = error
        self.type = 'event'
        if request_id:
            self.type = 'request'
            self.reply = reply
        elif response_id:
            self.type = 'response'
            self.response_id = response_id

class Remote(object):
    """
    Base class for all remote objects(Buffer, Window...).i
    """
    def __init__(self, vim, handle):
        """
        This is the only initializer remote objects need
        """
        self._vim = vim
        self._handle = handle

    def __eq__(self, other):
        return hasattr(other, '_handle') and self._handle == other._handle


# FIFO Mutex algorithm to ensure there's no lock starvation. Adapted from
# this SO answer: http://stackoverflow.com/a/12703543/304141
class FifoLock(object):
    def __init__(self):
        self.inner = Condition(Lock())
        self.head = self.tail = 0

    def acquire(self, steal=False):
        with self.inner:
            position = self.tail
            self.tail += 1
            while position != self.head:
                self.inner.wait()

    def release(self):
        with self.inner:
            self.head += 1
            self.inner.notify_all()

    def __enter__(self):
        self.acquire()

    def __exit__(self, type, value, traceback):
        self.release()

class Client(object):
    """
    Neovim client. It depends on a stream, an object that implements two
    methods:
        - read(): Returns any amount of data as soon as it's available
        - write(chunk): Writes data

    Both methods should be fully blocking.
    """
    def __init__(self, stream):
        self.next_request_id = 1
        self.stream = stream
        self.unpacker = msgpack.Unpacker()
        self.pending_messages = deque()
        self.pending_requests = {}
        self.vim = None
        self.stream_lock = FifoLock()
        self.interrupt_lock = Lock()

    def unpack_message(self, timeout=None):
        """
        Unpacks the next message from the input stream. This blocks until
        `timeout` or forever if timeout=None
        """
        while True:
            try:
                msg = self.unpacker.next()
                name = arg = error = result = request_id = response_id = None
                msg_type = msg[0]
                if msg_type == 0:
                    request_id = msg[1]
                    name = msg[2]
                    arg = msg[3]
                elif msg_type == 1:
                    response_id = msg[1]
                    error = msg[2]
                    result = msg[3]
                elif msg_type == 2:
                    name = msg[1]
                    arg = msg[2]
                else:
                    raise Exception('Received invalid message type')
                return Message(self, name=name, arg=arg, result=result,
                               error=error, request_id=request_id,
                               response_id=response_id)
            except StopIteration:
                chunk = self.stream.read(timeout)
                if not chunk:
                    if chunk == False:
                        raise TimeoutError()
                    return
                self.unpacker.feed(chunk)

    def queue_message(self, timeout=None):
        message = self.unpack_message(timeout)
        if not message:
            # interrupted
            return True
        if message.type is 'response':
            promise = self.pending_requests.pop(message.response_id)
            promise.message = message
        else:
            self.pending_messages.append(message)
        return False

    def msgpack_rpc_request(self, method_id, args, expected_type=None):
        """
        Sends a msgpack-rpc request to Neovim and return a Promise for the
        response
        """
        with self.interrupt_lock:
            self.stream.interrupt() # interrupt ongoing reads 
            with self.stream_lock:
                request_id = self.next_request_id
                # Update request id
                self.next_request_id = request_id + 1
                # Send the request
                data = msgpack.packb([0, request_id, method_id, args])
                self.stream.write(data)
                rv = Promise(self, request_id, expected_type)
                self.pending_requests[request_id] = rv
                return rv

    def next_message(self, timeout=None):
        """
        Returns the next server message
        """
        interrupted = False
        while True:
            if interrupted:
                with self.interrupt_lock:
                    pass
            with self.stream_lock:
                if self.pending_messages:
                    return self.pending_messages.popleft()
                interrupted = self.queue_message(timeout)

    def push_message(self, name, arg):
        """
        Pushes a "virtual message" that will be returned by `next_message`.
        This method can called from other threads for integration with event
        loops, such as those provided by GUI libraries.
        """
        with self.interrupt_lock:
            self.stream.interrupt()
            self.pending_messages.append(Message(self, name, arg))

    def discover_api(self):
        """
        Discovers the remote API using the special method '0'. After this
        the client will have a `vim` attribute containing an object
        that implements an interface similar to the one found in the
        python-vim module(legacy python->vim bridge)
        """
        if self.vim:
            # Only need to do this once
            return
        channel_id, api = self.msgpack_rpc_request(0, []).wait()
        api = msgpack.unpackb(api)
        # The 'Vim' class is the main entry point of the api
        classes = {'vim': type('Vim', (), {})}
        setattr(classes['vim'], 'next_message',
                lambda s, *args, **kwargs: self.next_message(*args, **kwargs))
        setattr(classes['vim'], 'push_message',
                lambda s, *args, **kwargs: self.push_message(*args, **kwargs))
        # Build classes for manipulating the remote structures, assigning to a
        # dict using lower case names as keys, so we can easily match methods
        # in the API.
        for cls in api['classes']:
            klass = type(cls + 'Base', (Remote,), {})
            # Methods of this class will pass an integer representing the
            # remote object as first argument
            classes[cls.lower()] = klass
        # now build function wrappers
        for function in api['functions']:
            # Split the name on underscores, the first part is the class name,
            # the remaining is the function name
            class_name, method_name = function['name'].split('_', 1)
            generate_wrapper(self,
                             classes[class_name],
                             method_name,
                             function['id'],
                             function['return_type'],
                             function['parameters'])
        # Now apply all available mixins to the generated classes
        for name, mixin in mixins.items():
            classes[name] = type(mixin.__name__, (classes[name], mixin,), {})
        # Create the 'vim object', which is a singleton of the 'Vim' class
        self.vim = classes['vim']()
        # Initialize with some useful attributes
        classes['vim'].initialize(self.vim, classes, channel_id, VimError)
        # Add attributes for each other class
        for name, klass in classes.items():
            if name != 'vim':
                setattr(self.vim, klass.__name__, klass)

def generate_wrapper(client, klass, name, fid, return_type, parameters):
    """
    Generate an API call wrapper
    """
    # Build a name->pos map for the parameters 
    parameter_names = {}
    parameter_count = 0
    for param in parameters:
        parameter_names[param[1]] = parameter_count
        parameter_count += 1
    async_name = 'send_' + name
    # These are the actual functions
    @fname(async_name)
    def async_func(*args, **kwargs):
        if isinstance(args[0], client.vim.__class__):
            # functions of the vim object don't need 'self'
            args = args[1:]
        argv = []
        # fill with positional arguments
        for i, arg in enumerate(args):
            if hasattr(client.vim, parameters[i][0]):
                # If the type is a remote object class, we use it's remote
                # handle instead
                arg = arg._handle
            # Add to the argument vector 
            argv.append(arg)
        return client.msgpack_rpc_request(fid, argv, return_type)
    @fname(name)
    def func(*args, **kwargs):
        return async_func(*args, **kwargs).wait()

    setattr(klass, async_name, async_func)
    setattr(klass, name, func)

def fname(name):
    """
    Helper for renaming generated functions
    """
    def dec(f):
        f.__name__ = name
        return f
    return dec


