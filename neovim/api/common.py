"""Code shared between the API classes."""


class Remote(object):

    """Base class for Nvim objects(buffer/window/tabpage).

    Each type of object has it's own specialized class with API wrappers around
    the msgpack-rpc session. This implements equality which takes the remote
    object handle into consideration.
    """

    def __eq__(self, other):
        """Return True if `self` and `other` are the same object."""
        return (hasattr(other, 'code_data') and
                other.code_data == self.code_data)


class RemoteMap(object):

    """Represents a string->object map stored in Nvim.

    This is the dict counterpart to the `RemoteSequence` class, but it is used
    as a generic way of retrieving values from the various map-like data
    structures present in Nvim.

    It is used to provide a dict-like API to vim variables and options.
    """

    def __init__(self, session, get_method, set_method, self_obj=None):
        """Initialize a RemoteMap with session, getter/setter and self_obj."""
        self._get = _wrap(session, get_method, self_obj)
        self._set = None
        if set_method:
            self._set = _wrap(session, set_method, self_obj)

    def __getitem__(self, key):
        """Return a map value by key."""
        return self._get(key)

    def __setitem__(self, key, value):
        """Set a map value by key(if the setter was provided)."""
        if not self._set:
            raise TypeError('This dict is read-only')
        self._set(key, value)

    def __delitem__(self, key):
        """Delete a map value by associating None with the key."""
        if not self._set:
            raise TypeError('This dict is read-only')
        return self._set(key, None)

    def __contains__(self, key):
        """Check if key is present in the map."""
        try:
            self._get(key)
            return True
        except:
            return False


class RemoteSequence(object):

    """Represents a sequence of objects stored in Nvim.

    This class is used to wrap msgapck-rpc functions that work on Nvim
    sequences(of lines, buffers, windows and tabpages) with an API that
    is similar to the one provided by the python-vim interface.

    For example, the 'buffers' property of the `Nvim class is a RemoteSequence
    sequence instance, and the expression `nvim.buffers[0]` is translated to
    session.request('vim_get_buffers')[0].

    It can also receive an optional self_obj that will be passed as first
    argument of the request. For example, `tabpage.windows[0]` is translated
    to: session.request('tabpage_get_windows', tabpage_instance)[0].

    One important detail about this class is that all methods will fetch the
    sequence into a list and perform the necessary manipulation
    locally(iteration, indexing, counting, etc).
    """

    def __init__(self, session, method, self_obj=None):
        """Initialize a RemoteSequence with session, method and self_obj."""
        self._fetch = _wrap(session, method, self_obj)

    def __len__(self):
        """Return the length of the remote sequence."""
        return len(self._fetch())

    def __getitem__(self, idx):
        """Return a sequence item by index."""
        if not isinstance(idx, slice):
            return self._fetch()[idx]
        return self._fetch()[idx.start:idx.stop]

    def __iter__(self):
        """Return an iterator for the sequence."""
        items = self._fetch()
        for item in items:
            yield item

    def __contains__(self, item):
        """Check if an item is present in the sequence."""
        for i in self._fetch():
            if i._handle == item._handle:
                return True
        return False


class SessionHook(object):

    """Pair of functions to filter objects coming/going from/to Nvim.

    Filter functions receive the following arguments:

    - obj: The object to process
    - session: The current session object
    - method: The method name
    - kind: Kind of filter, can be one of:
        - 'request' for requests coming from Nvim
        - 'notification' for notifications coming from Nvim
        - 'out-request' for requests going to Nvim

    Whatever is returned from the function is used as a replacement for `obj`.

    This class also provides a `compose` method for composing hooks.
    """

    identity = lambda obj, session, method, kind: obj

    def __init__(self, from_nvim=identity, to_nvim=identity):
        """Initialize a SessionHook with from/to filters."""
        self.from_nvim = from_nvim
        self.to_nvim = to_nvim

    def compose(self, other):
        """Compose two SessionHook instances.

        This works by composing the individual from/to filters and creating
        a new SessionHook instance with the composed filters.
        """
        def comp(f1, f2):
            if f1 is SessionHook.identity:
                return f2
            if f2 is SessionHook.identity:
                return f1
            return lambda o, s, m, k: f1(f2(o, s, m, k), s, m, k)

        return SessionHook(comp(other.from_nvim, self.from_nvim),
                           comp(other.to_nvim, self.to_nvim))


class DecodeHook(SessionHook):

    """SessionHook subclass that decodes utf-8 strings coming from Nvim.

    This class is useful for python3, where strings are now unicode by
    default(byte strings need to be prefixed with "b").
    """

    def __init__(self, encoding='utf-8', encoding_errors='strict'):
        """Initialize with encoding and encoding errors policy."""
        self.encoding = encoding
        self.encoding_errors = encoding_errors
        super(DecodeHook, self).__init__(from_nvim=self._decode_if_bytes)

    def _decode_if_bytes(self, obj, session, method, kind):
        if isinstance(obj, bytes):
            return obj.decode(self.encoding, errors=self.encoding_errors)
        return obj


class SessionFilter(object):

    """Wraps a session-like object with a SessionHook instance.

    This class can be used as a drop-in replacement for a sessions, the
    difference is that a hook is applied to all data passing through a
    SessionFilter instance.
    """

    def __init__(self, session, hook):
        """Initialize with a Session(or SessionFilter) and a hook.

        If `session` is already a SessionFilter, it's hook will be extracted
        and composed with `hook`.
        """
        if isinstance(session, SessionFilter):
            self._hook = session._hook.compose(hook)
            self._session = session._session
        else:
            self._hook = hook
            self._session = session
        # Both filters are applied to `walk` so objects are transformed
        # recursively
        self._in = self._hook.from_nvim
        self._out = self._hook.to_nvim

    def post(self, name, *args):
        """Wrapper for Session.post."""
        self._session.post(name, *args)

    def next_message(self):
        """Wrapper for Session.next_message."""
        msg = self._session.next_message()
        return walk(self._in, msg, self, msg[1], msg[0])

    def request(self, name, *args):
        """Wrapper for Session.request."""
        args = walk(self._out, args, self, name, 'out-request')
        return walk(self._in, self._session.request(name, *args), self, name,
                    'out-request')

    def run(self, request_cb, notification_cb):
        """Wrapper for Session.run."""
        def filter_request_cb(name, args):
            result = request_cb(self._in(name, self, name, 'request'),
                                walk(self._in, args, self, name, 'request'))
            return walk(self._out, result, self, name, 'request')

        def filter_notification_cb(name, args):
            notification_cb(self._in(name, self, name, 'notification'),
                            walk(self._in, args, self, name, 'notification'))

        self._session.run(filter_request_cb, filter_notification_cb)

    def stop(self):
        """Wrapper for Session.stop."""
        self._session.stop()


def walk(fn, obj, *args):
    """Recursively walk an object graph applying `fn`/`args` to objects."""
    if type(obj) in [list, tuple]:
        return list(walk(fn, o, *args) for o in obj)
    if type(obj) is dict:
        return dict((walk(fn, k, *args), walk(fn, v, *args)) for k, v in
                    obj.items())
    return fn(obj, *args)


def _wrap(session, method, self_obj):
    if self_obj is not None:
        return (lambda *args: session.request(method, self_obj, *args))
    else:
        return (lambda *args: session.request(method, *args))
