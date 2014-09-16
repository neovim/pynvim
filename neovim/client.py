import greenlet, logging, os, os.path
from collections import deque
from .mixins import mixins
from .util import VimError, VimExit, decode_obj
from traceback import format_exc
import cProfile, pstats, sys
from io import StringIO

logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warn,)


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


class Client(object):
    """
    Neovim client. It depends on a rpc stream, an object that implements four
    methods:
        - configure_types(vim, types): Configure the stream's
            serializer/deserializer with custom type information
        - loop_start(request_cb, notification_cb error_cb): Start the event
            loop to receive rpc requests and notifications
        - loop_stop(): Stop the event loop
        - send(method, args, response_cb): Send a method call with args, and
            invoke response_cb when the response is available
        - post(name, args): Post a notification from another thread
    """
    def __init__(self, stream, vim_compatible=False):
        self.stream = stream
        self.vim_compatible = vim_compatible
        self.greenlets = set()
        self.vim = None
        self.loop_running = False
        self.pending = deque()
        self._discover_api()
        if sys.version_info[0] > 2:
            self.stream.encoding = self.vim.get_option('encoding').decode('ascii')
        else:
            self.stream.encoding = self.vim.get_option('encoding')

    def rpc_yielding_request(self, method, args, decode_str=None):
        gr = greenlet.getcurrent()
        parent = gr.parent

        def response_cb(err, result):
            debug('response is available for greenlet %s, switching back', gr)
            gr.switch(err, result)

        self.stream.send(method, args, response_cb, decode_str=decode_str)
        debug('yielding from greenlet %s to wait for response', gr)
        return parent.switch()


    def rpc_blocking_request(self, method, args, decode_str=None):
        response = {}

        def response_cb(err, result):
            response['err'] = err
            response['result'] = result
            self.stream.loop_stop()

        debug('will now perform a blocking rpc request: %s, %s', method, args)
        self.stream.send(method, args, response_cb, decode_str=decode_str)
        queue = []

        while not response:
            msg = self.next_message()
            if msg:
                debug('message received while waiting for response: %s', msg)
                queue.append(msg)

        self.pending.extend(queue)

        return response.get('err', None), response.get('result', None)


    def rpc_request(self, method, args, expected_type=None, decode_str=None):
        """
        Sends a rpc request to Neovim.
        """
        if self.loop_running:
            err, result = self.rpc_yielding_request(method, args, decode_str=decode_str)
        else:
            err, result = self.rpc_blocking_request(method, args, decode_str=decode_str)

        if err:
            raise VimError(err)

        return result


    def next_pending_message(self):
        if self.pending:
            msg = self.pending.popleft()
            if msg[0] == 'eof':
                # never leave this state
                self.pending.appendleft(msg)
                raise msg[1]
            debug('returning message: %s', msg)
            return msg


    def next_message(self):
        """
        Blocks until a message is received. This is mostly for testing and
        interactive usage.
        """
        msg = self.next_pending_message()
        if msg:
            return msg

        error = {}

        def request_cb(name, args, reply_fn):
            self.pending.append(('request', name, args, reply_fn,))
            self.stream.loop_stop()

        def notification_cb(name, args):
            self.pending.append(('notification', name, args,))
            self.stream.loop_stop()

        def error_cb(err):
            error['err'] = err
            if isinstance(err, VimExit):
                self.pending.append(('eof', err,))
            self.stream.loop_stop()

        debug('will block until a message is available')
        self.stream.loop_start(request_cb, notification_cb, error_cb)

        if error:
            raise error['err']

        msg = self.next_pending_message()
        if msg:
            return msg


    def post(self, name, args=[]):
        self.stream.post(name, args)


    def on_request(self, name, args, reply_fn):
        def request_handler():
            try:
                rv = self.request_cb(name, args)
                debug('greenlet %s completed, sending %s as response', gr, rv)
                reply_fn(rv)
            except Exception as e:
                if self.loop_running:
                    err_str = format_exc(5)
                    warn("error caught while processing call '%s %s': %s",
                         name,
                         args,
                         err_str)
                    reply_fn(err_str, error=True)
                    debug('sent "%s" as response', err_str)
            debug('greenlet %s is now dying...', gr)
            self.greenlets.remove(gr)

        gr = greenlet.greenlet(request_handler)
        debug('received rpc request, greenlet %s will handle it', gr)
        self.greenlets.add(gr)
        gr.switch()


    def on_notification(self, name, args):
        def notification_handler():
            try:
                self.notification_cb(name, args)
                debug('greenlet %s completed', gr)
            except Exception as e:
                if self.loop_running:
                    err_str = format_exc(5)
                    warn("error caught while processing event '%s %s': %s",
                         name,
                         args,
                         err_str)
            debug('greenlet %s is now dying...', gr)
            self.greenlets.remove(gr)

        gr = greenlet.greenlet(notification_handler)
        debug('received rpc notification, greenlet %s will handle it', gr)
        self.greenlets.add(gr)
        gr.switch()


    def on_error(self, err):
        warn('caught error: %s', err)
        self.error_cb(err)


    def loop_start(self, request_cb, notification_cb, error_cb):
        profiling = 'NVIM_PYTHON_PROFILE' in os.environ

        try:
            assert not self.loop_running
            info('starting message loop')
            self.request_cb = request_cb
            self.notification_cb = notification_cb
            self.error_cb = error_cb
            self.loop_running = True

            if profiling:
                info('starting profiler')
                pr = cProfile.Profile()
                pr.enable()

            while self.pending:
                msg = self.pending.popleft()
                if msg[0] == 'request':
                    self.on_request(msg[1], msg[2], msg[3])
                else:
                    self.on_notification(msg[1], msg[2])

            self.stream.loop_start(self.on_request,
                                   self.on_notification,
                                   self.on_error)

        finally:
            if profiling:
                pr.disable()
                report = os.path.abspath('.nvim-python-client.profile')
                info('stopped profiler, writing report to %s', report)
                s = StringIO()
                ps = pstats.Stats(pr, stream=s)
                ps.strip_dirs().sort_stats('tottime').print_stats(30)

                with open(report, 'w') as f:
                    f.write(s.getvalue())

            info('exiting message loop')
            self.loop_running = False
            self.request_cb = None
            self.notification_cb = None
            self.error_cb = None


    def loop_stop(self):
        self.loop_running = False
        self.stream.loop_stop()


    def _discover_api(self):
        """
        Discovers the remote API using the special method '0'. After this
        the client will have a `vim` attribute containing an object
        that implements an interface similar to the one found in the
        python-vim module(legacy python->vim bridge)
        """
        if self.vim:
            # Only need to do this once
            return
        # When calling this method, &encoding was not defined yet so we will get
        # binary strings for all content. For Python3 decode api binary strings
        # as utf8
        channel_id, api = self.rpc_request("vim_get_api_info", [])
        if sys.version_info[0] > 2:
            api = decode_obj(api, 'utf8')
        # The 'Vim' class is the main entry point of the api
        types = {'vim': type('Vim', (), {})}
        setattr(types['vim'], 'loop_start',
                lambda s, *args, **kwargs: self.loop_start(*args, **kwargs))
        setattr(types['vim'], 'loop_stop',
                lambda s, *args, **kwargs: self.loop_stop(*args, **kwargs))
        setattr(types['vim'], 'next_message',
                lambda s, *args, **kwargs: self.next_message(*args, **kwargs))
        setattr(types['vim'], 'post',
                lambda s, *args, **kwargs: self.post(*args, **kwargs))
        # Build types for manipulating the remote structures, assigning to a
        # dict using lower case names as keys, so we can easily match methods
        # in the API.
        for cls in api['types']:
            klass = type(cls + 'Base', (Remote,), {})
            # Methods of this class will pass an integer representing the
            # remote object as first argument
            types[cls.lower()] = klass
        # now build function wrappers
        for function in api['functions']:
            # Split the name on underscores, the first part is the class name,
            # the remaining is the function name
            class_name, method_name = function['name'].split('_', 1)
            generate_wrapper(self,
                             types[class_name],
                             method_name,
                             function['name'],
                             function['return_type'],
                             function['parameters'])
        if self.vim_compatible:
            make_vim_compatible(types['vim'])
        # Now apply all available mixins to the generated types
        for name, mixin in mixins.items():
            types[name] = type(mixin.__name__, (types[name], mixin,), {})
        # Create the 'vim object', which is a singleton of the 'Vim' class
        self.vim = types['vim']()
        # Initialize with some useful attributes
        types['vim'].initialize(self.vim, types, channel_id, api)
        # Add attributes for each other class
        for name, klass in types.items():
            if name != 'vim':
                setattr(self.vim, klass.__name__, klass)
        # Configure the rpc stream with type information
        self.stream.configure(self.vim)
        self.vim


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
    # This is the actual generated function
    @fname(name)
    def func(*args, **kwargs):
        if isinstance(args[0], client.vim.__class__):
            # functions of the vim object don't need 'self'
            args = args[1:]
        argv = []
        decode_str = kwargs.get('decode_str', None)
        # fill with positional arguments
        for i, arg in enumerate(args):
            # Add to the argument vector 
            argv.append(arg)
        return client.rpc_request(fid, argv, return_type, decode_str=decode_str)

    setattr(klass, name, func)


def fname(name):
    """
    Helper for renaming generated functions
    """
    def dec(f):
        f.__name__ = name
        return f
    return dec


def process_eval_result(obj):
    def process_dict(d):
        for k, v in d.items():
            d[k] = process_value(v)
        return d

    def process_list(l):
        for i, v in enumerate(l):
            l[i] = process_value(v)
        return l

    def process_value(v):
        if isinstance(v, (int, long, float)):
            return str(v)
        if isinstance(v, dict):
            return process_dict(v)
        if isinstance(v, list):
            return process_list(v)
        return v

    return process_value(obj)


def make_vim_compatible(vim_class):
    eval_orig = vim_class.eval
    vim_class.eval = lambda *a, **ka: process_eval_result(eval_orig(*a, **ka))
