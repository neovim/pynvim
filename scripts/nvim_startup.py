""" Startup script for IPython that will connect to a running NeoVim instance
automatically or ask the user which NeoVim instance to connect to.
After connection there is a variable called "nvim" that gives acccess to the
endpoint.
"""
import atexit
from glob import glob
import pynvim


class NVimAutoAttachException(Exception):
    '''Exception class that will be raised by this script'''


def __let_user_choose_instance(nvim_instances):
    for idx, inst in enumerate(nvim_instances):
        with pynvim.attach('socket', path=inst) as nvim_endpoint:
            nvim_endpoint.command(
                f'echon "I am Instance Nr {idx}: " $NVIM_LISTEN_ADDRESS'
            )

    for idx, inst in enumerate(nvim_instances):
        print(f'Instance Nr {idx}: {inst}')

    while True:
        try:
            print(
                'Which Nvim instance should I connect to? '
                '(Look at the bottom of the vim instance you want to connect '
                'to)'
            )
            inst_nr = int(input('Connect to Instance Nr: '))
            chosen_inst = nvim_instances[inst_nr]
            break
        except (ValueError, IndexError):
            continue

    return chosen_inst


def tell_nvim_that_python_exited():
    'will inform Nvim about Python exit'
    nvim.command('echo "IPython disconnected."')


def autoattach_to_nvim(glob_expr='/tmp/nvim*/0'):
    '''Returns a nvim endpoint if there is only one instance.
    If there are more instances, asks the user which one to pick.
    Raises NVimAutoAttachException if there are no NVim instances.
    '''
    nvim_instances = glob(glob_expr)
    if not nvim_instances:
        raise NVimAutoAttachException(
            'Could not find any running NVim instances.'
        )
    if len(nvim_instances) > 1:
        chosen_inst = __let_user_choose_instance(nvim_instances)
    else:
        chosen_inst = nvim_instances[0]
    return pynvim.attach('socket', path=chosen_inst)


nvim = autoattach_to_nvim()
nvim.command('echo "Connected to IPython."')
atexit.register(tell_nvim_that_python_exited)
