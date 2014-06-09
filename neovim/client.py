import msgpack
import traceback
from collections import deque
from threading import Condition, Lock
from time import time
from mixins import mixins
from util import VimError


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


class BorrowedStreamMutex(object):
    """
    Helper class used to safely acquire or "borrow" the stream mutex from a
    thread that is blocking on a `next_event` call
    """
    def __init__(self, stream, stream_mutex, switcher):
        self.stream = stream
        self.stream_mutex = stream_mutex
        self.switcher = switcher
        self.inner_mutex = Lock()

    def __enter__(self):
        self.inner_mutex.acquire()
        if not self.stream_mutex.acquire(False):
            # Another thread is currently blocking on a 'next_event' call,
            # we need to interrupt it and try to acquire `stream_mutex`
            # ourselves, or else we would have to wait until an event is
            # received
            with self.switcher:
                # Send the interrupt
                self.stream.interrupt()
                # Assert that the other thread was interrupted in time before
                # waiting on the switcher condition
                if not self.stream_mutex.acquire(False):
                    self.switcher.wait()
                    self.stream_mutex.acquire()
                    self.switcher.notify()

    def __exit__(self, type, value, traceback):
        self.stream_mutex.release()
        self.inner_mutex.release()


class Client(object):
    """
    Neovim client. It depends on a stream, an object that implements two
    methods:
        - read(): Returns any amount of data as soon as it's available
        - write(chunk): Writes data

    Both methods should be fully blocking.
    """


    def __init__(self, stream):
        self._request_id = 0
        self.stream = stream
        self.unpacker = msgpack.Unpacker()
        self.pending_events = deque()
        self.vim = None
        # These are the constructs used to synchronize access:
        #
        # - request_mutex: mutual exclusion on the `msgpack_rpc_request` method
        # - stream_mutex: mutual exlusion on the stream. It must be acquired
        #   by both `msgpack_rpc_request` and `next_event`.
        # - switcher: Helper mutex/condition used to pass `stream_mutex` from a
        # thread blocking on `next_event` to another thread calling
        # `msgpack_rpc_request`
        self.stream_mutex = Lock()
        self.switcher = Condition(Lock())
        self.borrowed_stream_mutex = BorrowedStreamMutex(self.stream,
                                                     self.stream_mutex,
                                                     self.switcher)

    def pop_events(self, max_index=None):
        if max_index is None:
            rv = list(self.pending_events)
            self.pending_events.clear()
        else:
            rv = []
            i = 0
            while i <= max_index:
                rv.append(self.pending_events.popleft())
                i += 1
        return rv

    def next_message(self, timeout=None):
        """
        Returns the next msgpack object from the input stream. This blocks
        until `timeout` or forever if timeout=None
        """
        while True:
            try:
                return self.unpacker.next()
            except StopIteration:
                chunk = self.stream.read(timeout)
                if not chunk:
                    return
                self.unpacker.feed(chunk)

    def msgpack_rpc_request(self, method_id, params):
        """
        Sends a msgpack-rpc request to Neovim and returns the response
        """
        with self.borrowed_stream_mutex:
            request_id = self._request_id + 1
            # Send the request
            self.stream.write(
                msgpack.packb([0, request_id, method_id, params]))
            # Enter a loop feeding the unpacker with data until we parse the
            # response
            message = None
            while not message:
                message = self.next_message()
                if message and message[0] == 2:
                    # event, add to the pending queue
                    self.pending_events.append(message[1:])
                    message = None
            # Update request id
            self._request_id = request_id
            return message

    def next_event(self, timeout=None):
        """
        Returns the next server event
        """
        with self.stream_mutex:
            while True:
                if len(self.pending_events):
                    return self.pending_events.popleft()
                message = self.next_message(timeout)
                with self.switcher:
                    if not message:
                        # If interrupted by a `msgpack_rpc_request` call from
                        # another thread, wait for a signal and try again
                        self.stream_mutex.release()
                        self.switcher.notify()
                        self.switcher.wait()
                        self.stream_mutex.acquire()
                        continue
                    # The message type must be 2, which is the msgpack-rpc
                    # notification type
                    # (http://wiki.msgpack.org/display/MSGPACK/RPC+specification).
                    # The only other possible message type the server will send
                    # is a response(1), but those must be received from
                    # `msgpack_rpc_request`
                    assert not message or message[0] == 2
                    if message:
                        return message[1:]

    def push_event(self, event_name, event_data):
        """
        Pushes a "virtual event" that will be returned by `next_event`.  This
        method can called from other threads for integration with event loops,
        such as those provided by GUI libraries.
        """
        with self.borrowed_stream_mutex:
            self.pending_events.append([event_name, event_data])

    def expect(self, event_type, timeout=None, predicate=lambda e: True):
        """
        Blocks until an expected event happens. By default, only the event type
        will be used to determine if a received event is being expected. An
        optional predicate(function that receives the event and returns a
        boolean) can be passed, and in this case it must return true for the
        event to be considered as expected.

        It returns a list containing all events up to and including the
        expected event. If a timeout is given and no expected event happens
        until then, an Exception will be raised. 

        This function is inspired by the 'expect' program, and was designed to
        make it simple to test asynchronous editor responses. For example:

        ```python
        def test_insert_mode():
            vim.current.window.cursor = [1, 0]
            vim.command('normal dditest')
            # block until the first line redraws with the string 'test'
            vim.expect('redraw', timeout=2, lambda e: e['lines'][0] == 'test')
        ```

        Warning: This function probably should not be called in multithreaded
        programs
        """
        for i, event in enumerate(self.pending_events):
            if event[0] == event_type and predicate(event):
                return self.pop_events(i)

        while timeout is None or timeout > 0:
            start = time()
            event = self.next_message(timeout)
            if not event:
                break
            event = event[1:]
            self.pending_events.append(event)
            if event[0] == event_type and predicate(event):
                return self.pop_events()
            timeout -= time() - start

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
        channel_id, api = self.msgpack_rpc_request(0, [])[3]
        api = msgpack.unpackb(api)
        # The 'Vim' class is the main entry point of the api
        classes = {'vim': type('Vim', (), {})}
        setattr(classes['vim'], 'next_event',
                lambda s, *args, **kwargs: self.next_event(*args, **kwargs))
        setattr(classes['vim'], 'push_event',
                lambda s, *args, **kwargs: self.push_event(*args, **kwargs))
        setattr(classes['vim'], 'expect',
                lambda s, *args, **kwargs: self.expect(*args, **kwargs))
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
        classes['vim'].initialize(self.vim, classes, channel_id)
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
    # This is the actual function
    @fname(name)
    def rv(*args, **kwargs):
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
        result = client.msgpack_rpc_request(fid, argv)
        if result[2]:
            # error
            raise VimError(result[2])
        if hasattr(client.vim, return_type):
            # result should be a handle, wrap in it's specialized class
            klass = getattr(client.vim, return_type)
            rv = klass(client.vim, result[3])
            klass.initialize(rv)
            return rv

        return result[3]
    setattr(klass, name, rv)


def fname(name):
    """
    Helper for renaming generated functions
    """
    def dec(f):
        f.__name__ = name
        return f
    return dec


