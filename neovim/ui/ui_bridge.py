"""Bridge for connecting a UI instance to nvim."""
import sys
from threading import Semaphore, Thread
from traceback import format_exc


class UIBridge(object):

    """UIBridge class. Connects a Nvim instance to a UI class."""

    def connect(self, nvim, ui, profile=None, notify=False):
        """Connect nvim and the ui.

        This will start loops for handling the UI and nvim events while
        also synchronizing both.
        """
        self._notify = notify
        self._error = None
        self._nvim = nvim
        self._ui = ui
        self._profile = profile
        self._sem = Semaphore(0)
        t = Thread(target=self._nvim_event_loop)
        t.daemon = True
        t.start()
        self._ui_event_loop()
        if self._error:
            print(self._error)
        if self._profile:
            print(self._profile)

    def exit(self):
        """Disconnect by exiting nvim."""
        self.detach()
        self._call(self._nvim.quit)

    def input(self, input_str):
        """Send input to nvim."""
        self._call(self._nvim.input, input_str)

    def resize(self, columns, rows):
        """Send a resize request to nvim."""
        self._call(self._nvim.ui_try_resize, columns, rows)

    def attach(self, columns, rows, rgb):
        """Attach the UI to nvim."""
        self._call(self._nvim.ui_attach, columns, rows, rgb)

    def detach(self):
        """Detach the UI from nvim."""
        self._call(self._nvim.ui_detach)

    def _call(self, fn, *args):
        self._nvim.session.threadsafe_call(fn, *args)

    def _ui_event_loop(self):
        self._sem.acquire()
        if self._profile:
            import StringIO
            import cProfile
            import pstats
            pr = cProfile.Profile()
            pr.enable()
        self._ui.start(self)
        if self._profile:
            pr.disable()
            s = StringIO.StringIO()
            ps = pstats.Stats(pr, stream=s)
            ps.strip_dirs().sort_stats(self._profile).print_stats(30)
            self._profile = s.getvalue()

    def _nvim_event_loop(self):
        def on_setup():
            self._sem.release()

        def on_request(method, args):
            raise Exception('Not implemented')

        def on_notification(method, updates):
            def apply_updates():
                if self._notify:
                    sys.stdout.write('attached\n')
                    sys.stdout.flush()
                    self._notify = False
                try:
                    for update in updates:
                        # import sys
                        # l = [','.join([str(a) for a in args])
                        #      for args in update[1:]]
                        # print >> sys.stderr, update[0], ' '.join(l)
                        handler = getattr(self._ui, '_nvim_' + update[0])
                        for args in update[1:]:
                            handler(*args)
                except:
                    self._error = format_exc()
                    self._call(self._nvim.quit)
            if method == 'redraw':
                self._ui.schedule_screen_update(apply_updates)

        self._nvim.session.run(on_request, on_notification, on_setup)
        self._ui.quit()
