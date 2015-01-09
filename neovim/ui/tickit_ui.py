"""Neovim tickit UI."""
import os
import re
import signal
import sys

import cffi
import cffi.verifier

from .screen import Screen
from ..compat import IS_PYTHON3

try:
    # For python 3.4+, use the standard library module
    import asyncio
except ImportError:
    # Fallback to trollius
    import trollius as asyncio


loop_cls = asyncio.SelectorEventLoop
if os.name == 'nt':
    # On windows use ProactorEventLoop which support pipes and is backed by
    # the more powerful IOCP facility
    loop_cls = asyncio.ProactorEventLoop


__all__ = ('TickitUI',)


if not IS_PYTHON3:
    range = xrange  # NOQA


# Translation table for the key name strings passed by libtickit that don't
# match
KEY_TABLE = {
    'Backspace': 'BS',
    'Enter': 'CR',
    'Escape': 'Esc',
    'Delete': 'Del'
}

EMPTY_ATTRS = {}

API = '''
enum {
  TICKIT_MOD_SHIFT = 0x01,
  TICKIT_MOD_ALT   = 0x02,
  TICKIT_MOD_CTRL  = 0x04,
};

enum {
  TICKIT_MOUSEWHEEL_UP = 1,
  TICKIT_MOUSEWHEEL_DOWN,
};

typedef enum {
  TICKIT_PEN_FG,
  TICKIT_PEN_BG,
  TICKIT_PEN_BOLD,
  TICKIT_PEN_UNDER,
  TICKIT_PEN_ITALIC,
  TICKIT_PEN_REVERSE,
  TICKIT_PEN_STRIKE,
  TICKIT_PEN_ALTFONT,
  TICKIT_PEN_BLINK,
  TICKIT_N_PEN_ATTRS
} TickitPenAttr;

typedef enum {
  TICKIT_TERM_MOUSEMODE_OFF,
  TICKIT_TERM_MOUSEMODE_CLICK,
  TICKIT_TERM_MOUSEMODE_DRAG,
  TICKIT_TERM_MOUSEMODE_MOVE,
} TickitTermMouseMode;

typedef enum {
  TICKIT_TERMCTL_ALTSCREEN = 1,
  TICKIT_TERMCTL_CURSORVIS,
  TICKIT_TERMCTL_MOUSE,
  TICKIT_TERMCTL_CURSORBLINK,
  TICKIT_TERMCTL_CURSORSHAPE,
  TICKIT_TERMCTL_ICON_TEXT,
  TICKIT_TERMCTL_TITLE_TEXT,
  TICKIT_TERMCTL_ICONTITLE_TEXT,
  TICKIT_TERMCTL_KEYPAD_APP,
  TICKIT_TERMCTL_COLORS,
} TickitTermCtl;

typedef enum {
  TICKIT_TERM_CURSORSHAPE_BLOCK = 1,
  TICKIT_TERM_CURSORSHAPE_UNDER,
  TICKIT_TERM_CURSORSHAPE_LEFT_BAR,
} TickitTermCursorShape;

typedef enum {
  TICKIT_EV_RESIZE = 0x01,
  TICKIT_EV_KEY    = 0x02,
  TICKIT_EV_MOUSE  = 0x04,
  TICKIT_EV_CHANGE = 0x08,
  TICKIT_EV_UNBIND = 0x80000000,
} TickitEventType;

typedef enum {
  TICKIT_KEYEV_KEY = 1,
  TICKIT_KEYEV_TEXT,
} TickitKeyEventType;

typedef enum {
  TICKIT_MOUSEEV_PRESS = 1,
  TICKIT_MOUSEEV_DRAG,
  TICKIT_MOUSEEV_RELEASE,
  TICKIT_MOUSEEV_WHEEL,
} TickitMouseEventType;

typedef struct {
  int         lines, cols;
  int         type;
  const char *str;
  int         button;
  int         line, col;
  int         mod;
} TickitEvent;

struct timeval {
    long tv_sec;
    long tv_usec;
};

typedef struct TickitTerm_ TickitTerm;
typedef struct TickitPen_ TickitPen;

typedef void TickitTermEventFn(TickitTerm *tt, TickitEventType ev,
                               TickitEvent *args, void *data);

TickitTerm *tickit_term_new(void);
void tickit_term_destroy(TickitTerm *tt);
void tickit_term_await_started(TickitTerm *tt, const struct timeval *timeout);
TickitPen *tickit_pen_new(void);
void tickit_term_setpen(TickitTerm *tt, TickitPen *pen);
void tickit_term_set_input_fd(TickitTerm *tt, int fd);
void tickit_term_set_output_fd(TickitTerm *tt, int fd);
int tickit_term_setctl_int(TickitTerm *tt, TickitTermCtl ctl, int value);
int tickit_term_setctl_str(TickitTerm *tt, TickitTermCtl ctl,
                           const char *value);
void tickit_term_input_readable(TickitTerm *tt);
int tickit_term_input_check_timeout(TickitTerm *tt);
void tickit_term_set_output_buffer(TickitTerm *tt, size_t len);
void tickit_term_flush(TickitTerm *tt);
void tickit_pen_set_colour_attr(TickitPen *pen, TickitPenAttr attr, int val);
void tickit_pen_set_bool_attr(TickitPen *pen, TickitPenAttr attr, bool val);
void tickit_term_printn(TickitTerm *tt, const char *str, size_t len);
int  tickit_term_goto(TickitTerm *tt, int line, int col);
void tickit_term_get_size(TickitTerm *tt, int *lines, int *cols);
void tickit_term_set_size(TickitTerm *tt, int lines, int cols);
void tickit_term_refresh_size(TickitTerm *tt);
void tickit_term_clear(TickitTerm *tt);
int tickit_term_bind_event(TickitTerm *tt, TickitEventType ev,
                           TickitTermEventFn *fn, void *user);
'''


class TickitVerifier(cffi.verifier.Verifier):
    def get_extension(self, *args, **kwargs):
        # Executed only the first time the native extension needs to be built
        from subprocess import check_output
        try:
            inc_dir = check_output(['pkg-config', '--cflags',
                                    'tickit']).strip()[2:]
            lib_dir = check_output(['pkg-config', '--libs', '--libs-only-L',
                                    'tickit']).strip()[2:]
            if os.path.isdir(inc_dir):
                self.kwds['include_dirs'] = [inc_dir]
            if os.path.isdir(lib_dir):
                link_flags = '-Wl,-rpath={0}'.format(lib_dir)
                self.kwds['library_dirs'] = [lib_dir]
                self.kwds['extra_link_args'] = [link_flags]
        except OSError as e:
            if e.errno != os.errno.ENOENT:
                raise
        return super(TickitVerifier, self).get_extension(*args, **kwargs)


ffi = cffi.FFI()
ffi.cdef(API)
lib = TickitVerifier(ffi, '''
#include <sys/time.h>
#include <tickit.h>
''', libraries=['tickit']).load_library()


class TickitUI(object):

    """Tickit UI class."""

    def start(self, bridge):
        """Start the UI event loop."""
        while True:
            self._suspended = False
            self._foreground = -1
            self._background = -1
            self._screen = None
            self._attrs = None
            self._printattrs = 0
            self._cursor_enabled = False
            self._invalid_rects = []  # regions that will be repainted on flush
            self._tickit_event_loop(bridge)
            if self._suspended:
                os.kill(0, signal.SIGTSTP)
            else:
                break

    def quit(self):
        """Exit the UI event loop."""
        def cb():
            self._loop.remove_reader(sys.stdin.fileno())
            self._loop.remove_signal_handler(signal.SIGINT)
            self._loop.remove_signal_handler(signal.SIGWINCH)
            self._loop.stop()
        self._loop.call_soon_threadsafe(cb)

    def schedule_screen_update(self, apply_updates):
        """Schedule screen updates to run in the UI event loop."""
        def cb():
            lib.tickit_term_setctl_int(self._tt,
                                       lib.TICKIT_TERMCTL_CURSORVIS, False)
            apply_updates()
            for top, bot, left, right in self._invalid_rects:
                self._repaint_rect(top, bot, left, right)
            del self._invalid_rects[:]
            if self._cursor_enabled:
                lib.tickit_term_setctl_int(self._tt,
                                           lib.TICKIT_TERMCTL_CURSORVIS, True)
            lib.tickit_term_flush(self._tt)

        self._loop.call_soon_threadsafe(cb)

    def _tickit_event(self, tt, ev_type, ev_args, *args):
        if ev_type == lib.TICKIT_EV_KEY:
            self._tickit_key(ev_args.str, ev_args.mod)

    def _tickit_key(self, type, str, mod):
        key_str = ffi.string(str)
        if type == lib.TICKIT_KEYEV_KEY:
            input_str = _stringify_key(KEY_TABLE.get(key_str, key_str), mod)
        else:
            input_str = key_str.replace('<', '<lt>')
        self._bridge.input(input_str)

    def _tickit_mouse(self, type, button, row, col, mod):
        if button == 1:
            key = 'Left'
        elif button == 2:
            key = 'Middle'
        elif button == 3:
            key = 'Right'
        else:
            return
        if type == lib.TICKIT_MOUSEEV_PRESS:
            key += 'Mouse'
        elif type == lib.TICKIT_MOUSEEV_DRAG:
            key += 'Drag'
        elif type == lib.TICKIT_MOUSEEV_WHEEL:
            if button == lib.TICKIT_MOUSEWHEEL_UP:
                key = 'ScrollWheelUp'
            else:
                key = 'ScrollWheelDown'
        input_str = _stringify_key(key, mod)
        input_str += '<{0},{1}>'.format(col, row)
        self._bridge.input(input_str)

    def _nvim_resize(self, columns, rows):
        lib.tickit_term_set_size(self._tt, rows, columns)
        self._screen = Screen(columns, rows)

    def _nvim_clear(self):
        self._screen.clear()
        self._repaint_rect(self._screen.top, self._screen.bot,
                           self._screen.left, self._screen.right)

    def _nvim_eol_clear(self):
        self._screen.eol_clear()
        self._repaint_rect(self._screen.row, self._screen.row,
                           self._screen.col, self._screen.right)

    def _nvim_cursor_goto(self, row, col):
        self._screen.cursor_goto(row, col)
        lib.tickit_term_goto(self._tt, row, col)

    def _nvim_cursor_on(self):
        self._cursor_enabled = True

    def _nvim_cursor_off(self):
        self._cursor_enabled = False

    def _nvim_mouse_on(self):
        lib.tickit_term_setctl_int(self._tt, lib.TICKIT_TERMCTL_MOUSE,
                                   lib.TICKIT_TERM_MOUSEMODE_DRAG)

    def _nvim_mouse_off(self):
        lib.tickit_term_setctl_int(self._tt, lib.TICKIT_TERMCTL_MOUSE,
                                   lib.TICKIT_TERM_MOUSEMODE_OFF)

    def _nvim_insert_mode(self):
        if lib.tickit_term_setctl_int(self._tt,
                                      lib.TICKIT_TERMCTL_CURSORSHAPE,
                                      lib.TICKIT_TERM_CURSORSHAPE_LEFT_BAR):
            return
        lib.tickit_term_setctl_int(self._tt, lib.TICKIT_TERMCTL_CURSORSHAPE,
                                   lib.TICKIT_TERM_CURSORSHAPE_UNDER)

    def _nvim_normal_mode(self):
        lib.tickit_term_setctl_int(self._tt, lib.TICKIT_TERMCTL_CURSORSHAPE,
                                   lib.TICKIT_TERM_CURSORSHAPE_BLOCK)

    def _nvim_set_scroll_region(self, top, bot, left, right):
        self._screen.set_scroll_region(top, bot, left, right)

    def _nvim_scroll(self, count):
        self._screen.scroll(count)
        self._invalidate(self._screen.top, self._screen.bot,
                         self._screen.left, self._screen.right)

    def _nvim_highlight_set(self, attrs):
        self._attrs = attrs

    def _nvim_put(self, text):
        self._screen.put(text, self._attrs)
        self._print(text, self._attrs)

    def _nvim_bell(self):
        lib.tickit_term_printn(self._tt, bytes('\x07'), 1)

    def _nvim_visual_bell(self):
        pass

    def _nvim_update_fg(self, fg):
        self._foreground = fg

    def _nvim_update_bg(self, bg):
        self._background = bg

    def _nvim_suspend(self):
        if not self._suspended:
            self.quit()
            self._suspended = True

    def _nvim_set_title(self, title):
        lib.tickit_term_setctl_str(self._tt, lib.TICKIT_TERMCTL_TITLE_TEXT,
                                   bytes(title))

    def _nvim_set_icon(self, icon):
        lib.tickit_term_setctl_str(self._tt, lib.TICKIT_TERMCTL_ICON_TEXT,
                                   bytes(icon))

    def _tickit_event_loop(self, bridge):
        width_ptr = ffi.new('int *')
        height_ptr = ffi.new('int *')
        tv = ffi.new('struct timeval *')
        tv.tv_usec = 50000
        tt = lib.tickit_term_new()
        lib.tickit_term_set_input_fd(tt, sys.stdin.fileno())
        lib.tickit_term_set_output_fd(tt, sys.stdout.fileno())
        lib.tickit_term_await_started(tt, tv)
        lib.tickit_term_setctl_int(tt, lib.TICKIT_TERMCTL_ALTSCREEN, 1)
        lib.tickit_term_refresh_size(tt)
        lib.tickit_term_get_size(tt, height_ptr, width_ptr)
        lib.tickit_term_clear(tt)

        def winch():
            lib.tickit_term_refresh_size(tt)
            lib.tickit_term_get_size(tt, height_ptr, width_ptr)
            bridge.resize(width_ptr[0], height_ptr[0])

        def interrupt():
            bridge.input('<C-c>')

        def input_check():
            check_timeout = lambda: lib.tickit_term_input_check_timeout(tt)
            lib.tickit_term_input_readable(tt)
            sleep = check_timeout()
            if sleep != -1:
                self._loop.call_later(sleep / 1000.0, check_timeout)

        @ffi.callback('TickitTermEventFn')
        def event(tt, ev_type, ev_args, *args):
            if ev_type == lib.TICKIT_EV_KEY:
                self._tickit_key(ev_args.type, ev_args.str, ev_args.mod)
            elif ev_type == lib.TICKIT_EV_MOUSE:
                self._tickit_mouse(ev_args.type, ev_args.button, ev_args.line,
                                   ev_args.col, ev_args.mod)

        pen = lib.tickit_pen_new()
        lib.tickit_term_setpen(tt, pen)
        lib.tickit_term_bind_event(tt, lib.TICKIT_EV_KEY | lib.TICKIT_EV_MOUSE,
                                   event, ffi.NULL)
        lib.tickit_term_set_output_buffer(tt, 0xffff)
        bridge.attach(width_ptr[0], height_ptr[0], False)
        self._bridge = bridge
        self._tt = tt
        self._pen = pen
        self._loop = loop_cls()
        self._loop.add_reader(sys.stdin.fileno(), input_check)
        self._loop.add_signal_handler(signal.SIGINT, interrupt)
        self._loop.add_signal_handler(signal.SIGWINCH, winch)
        self._loop.run_forever()
        lib.tickit_term_destroy(tt)
        bridge.detach()

    def _repaint_rect(self, top, bot, left, right):
        save_row, save_col = self._screen.row, self._screen.col
        for row, col, text, attrs in self._screen.iter(top, bot, left, right):
            lib.tickit_term_goto(self._tt, row, col)
            self._print(text, attrs)
        # restore cursor
        lib.tickit_term_goto(self._tt, save_row, save_col)

    def _print(self, text, attrs):
        if attrs != self._printattrs:
            if not attrs:
                attrs = EMPTY_ATTRS
            fg = attrs.get('foreground', self._foreground)
            bg = attrs.get('background', self._background)
            lib.tickit_pen_set_colour_attr(self._pen, lib.TICKIT_PEN_FG, fg)
            lib.tickit_pen_set_colour_attr(self._pen, lib.TICKIT_PEN_BG, bg)
            lib.tickit_pen_set_bool_attr(self._pen, lib.TICKIT_PEN_BOLD,
                                         'bold' in attrs)
            lib.tickit_pen_set_bool_attr(self._pen, lib.TICKIT_PEN_ITALIC,
                                         'italic' in attrs)
            lib.tickit_pen_set_bool_attr(self._pen, lib.TICKIT_PEN_UNDER,
                                         'underline' in attrs)
            lib.tickit_pen_set_bool_attr(self._pen, lib.TICKIT_PEN_REVERSE,
                                         'reverse' in attrs)
            lib.tickit_term_setpen(self._tt, self._pen)
            self._printattrs = attrs
        text = bytes(text)
        lib.tickit_term_printn(self._tt, text, len(text))

    def _invalidate(self, top, bot, left, right):
        # search the invalid rects for one that intersects the newly
        # invalidated rect
        intersects = None
        for i in range(len(self._invalid_rects)):
            t, b, l, r = self._invalid_rects[i]
            if top > b or bot < t or left > r or right < l:
                continue
            intersects = (t, b, l, r, i,)
            break
        if intersects:
            # replace the intersecting rect by the union with the newly
            # invalidated rect
            t, b, l, r, i = intersects
            top = min(top, t)
            bot = max(bot, b)
            left = min(left, l)
            right = max(right, r)
            self._invalid_rects[i] = (top, bot, left, right,)
        else:
            # add new entry
            self._invalid_rects.append((top, bot, left, right,))


MODIFIERS_AND_KEY = re.compile(r'^(?:(?:S|C|A|M)-)*(.+)$')


def _stringify_key(key, mod):
    key = MODIFIERS_AND_KEY.findall(key)[0]
    send = []
    if mod & lib.TICKIT_MOD_SHIFT:
        send.append('S')
    if mod & lib.TICKIT_MOD_CTRL:
        send.append('C')
    if mod & lib.TICKIT_MOD_ALT:
        send.append('A')
    send.append(key)
    return '<' + '-'.join(send) + '>'
