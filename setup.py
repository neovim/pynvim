import platform
import sys

from setuptools import setup

install_requires = [
    'msgpack-python>=0.4.0',
]
extras_require = {}
entry_points = {}

if sys.version_info < (3, 4):
    # trollius is just a backport of 3.4 asyncio module
    install_requires.append('trollius')

has_cython = False
if not platform.python_implementation() == 'PyPy':
    # pypy already includes an implementation of the greenlet module
    install_requires.append('greenlet')
    try:
        # Cythonizing screen.py to improve scrolling/clearing speed. Maybe the
        # performance can be improved even further by writing a screen.pxd with
        # static type information
        from Cython.Build import cythonize
        has_cython = True
    except ImportError:
        pass

if sys.version_info < (3, 0):
    # Experimental GUI only supported for Python 2.
    extras_require['GUI'] = ['click>=3.0', 'pygobject']
    entry_points['console_scripts'] = ['pynvim=neovim.ui.cli:main [GUI]']

setup(name='neovim',
      version='0.0.35',
      description='Python client to neovim',
      url='http://github.com/neovim/python-client',
      download_url='https://github.com/neovim/python-client/archive/0.0.35.tar.gz',
      author='Thiago de Arruda',
      author_email='tpadilha84@gmail.com',
      license='Apache',
      packages=['neovim', 'neovim.api', 'neovim.msgpack_rpc', 'neovim.ui',
                'neovim.msgpack_rpc.event_loop', 'neovim.plugin'],
      install_requires=install_requires,
      ext_modules=cythonize('neovim/ui/screen.py') if has_cython else None,
      extras_require=extras_require,
      entry_points=entry_points,
      zip_safe=False)
