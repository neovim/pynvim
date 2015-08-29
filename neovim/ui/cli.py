"""CLI for accessing the gtk/tickit UIs implemented by this package."""
import os
import resource
import sys
import shlex

import click

from .ui_bridge import UIBridge
from .. import attach


# http://code.activestate.com/recipes/278731-creating-a-daemon-the-python-way/
def detach_proc():
    """Detach a process from the controlling terminal and run it in the
    background as a daemon.
    """

    # Default daemon parameters.
    # File mode creation mask of the daemon.
    UMASK = 0

    # Default working directory for the daemon.
    WORKDIR = "/"

    # Default maximum for the number of available file descriptors.
    MAXFD = 1024

    # The standard I/O file descriptors are redirected to /dev/null by default.
    if (hasattr(os, "devnull")):
        REDIRECT_TO = os.devnull
    else:
        REDIRECT_TO = "/dev/null"

    try:
        pid = os.fork()
    except OSError, e:
        raise Exception, "%s [%d]" % (e.strerror, e.errno)

    if (pid == 0):
        os.setsid()

        try:
            pid = os.fork()

        except OSError, e:
            raise Exception, "%s [%d]" % (e.strerror, e.errno)

        if (pid == 0):
            os.chdir(WORKDIR)
            os.umask(UMASK)
        else:
            os._exit(0)
    else:
        os._exit(0)

        maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
        if (maxfd == resource.RLIM_INFINITY):
            maxfd = MAXFD

            # Iterate through and close all file descriptors.
            for fd in range(0, maxfd):
                try:
                    os.close(fd)
                except OSError:
                    pass

    os.open(REDIRECT_TO, os.O_RDWR)

    os.dup2(0, 1)
    os.dup2(0, 2)

    return(0)


@click.command(context_settings=dict(allow_extra_args=True))
@click.option('--prog')
@click.option('--notify', '-n', default=False, is_flag=True)
@click.option('--listen', '-l')
@click.option('--connect', '-c')
@click.option('--profile',
              default='disable',
              type=click.Choice(['ncalls', 'tottime', 'percall', 'cumtime',
                                 'name', 'disable']))
@click.option('--detach/--no-detach', default=True, is_flag=True)
@click.pass_context
def main(ctx, prog, notify, listen, connect, profile, detach):
    """Entry point."""

    if detach:
        exit_code = detach_proc()

    address = connect or listen

    if address:
        import re
        p = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:\:\d{1,5})?$')

        if p.match(address):
            args = ('tcp',)
            kwargs = {'address': address}
        else:
            args = ('socket',)
            kwargs = {'path': address}

    if connect:
        # connect to existing instance listening on address
        nvim = attach(*args, **kwargs)
    elif listen:
        # spawn detached instance listening on address and connect to it
        import os
        import time
        from subprocess import Popen
        os.environ['NVIM_LISTEN_ADDRESS'] = address
        nvim_argv = shlex.split(prog or 'nvim --headless') + ctx.args
        # spawn the nvim with stdio redirected to /dev/null.
        dnull = open(os.devnull)
        p = Popen(nvim_argv, stdin=dnull, stdout=dnull, stderr=dnull)
        dnull.close()
        while p.poll() or p.returncode is None:
            try:
                nvim = attach(*args, **kwargs)
                break
            except IOError:
                # socket not ready yet
                time.sleep(0.050)
    else:
        # spawn embedded instance
        nvim_argv = shlex.split(prog or 'nvim --embed') + ctx.args
        nvim = attach('child', argv=nvim_argv)

    from .gtk_ui import GtkUI
    ui = GtkUI()
    bridge = UIBridge()
    bridge.connect(nvim, ui, profile if profile != 'disable' else None, notify)

    if detach:
        sys.exit(exit_code)


if __name__ == '__main__':
    main()
