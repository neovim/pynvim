"""CLI for accessing the gtk/tickit UIs implemented by this package."""
import shlex

import click

from .ui_bridge import UIBridge
from .. import attach
from ..api import DecodeHook
from ..compat import IS_PYTHON3


@click.command(context_settings=dict(allow_extra_args=True))
@click.option('--prog')
@click.option('--notify', '-n', default=False, is_flag=True)
@click.option('--listen', '-l')
@click.option('--connect', '-c')
@click.option('--profile',
              default='disable',
              type=click.Choice(['ncalls', 'tottime', 'percall', 'cumtime',
                                 'name', 'disable']))
@click.pass_context
def main(ctx, prog, notify, listen, connect, profile):
    """Entry point."""
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

    if IS_PYTHON3:
        nvim = nvim.with_hook(DecodeHook())

    from .gtk_ui import GtkUI
    ui = GtkUI()
    bridge = UIBridge()
    bridge.connect(nvim, ui, profile if profile != 'disable' else None, notify)


if __name__ == '__main__':
    main()
