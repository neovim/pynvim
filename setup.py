import platform
import sys

from setuptools import setup

install_requires = [
    'msgpack-python>=0.4.0',
]
extras_require = {}
entry_points = {}
ext_modules = None

if sys.version_info < (3, 4):
    # trollius is just a backport of 3.4 asyncio module
    install_requires.append('trollius')

if platform.python_implementation() != 'PyPy':
    # pypy already includes an implementation of the greenlet module
    install_requires.append('greenlet')

    # Experimental GUI only supported for Python 2.
    if sys.version_info < (3, 0):
        # Cythonizing screen.py to improve scrolling/clearing speed. Maybe the
        # performance can be improved even further by writing a screen.pxd with
        # static type information
        try:
            from Cython.Build import cythonize
            ext_modules = cythonize('neovim/ui/screen.py')
        except ImportError:
            pass

if sys.version_info < (3, 0):
    # Experimental GUI only supported for Python 2.
    extras_require['GUI'] = ['click>=3.0', 'pygobject']
    entry_points['console_scripts'] = ['pynvim=neovim.ui.cli:main [GUI]']

setup(name='neovim',
      version='0.1.0',
      description='Python client to neovim',
      url='http://github.com/neovim/python-client',
      download_url='https://github.com/neovim/python-client/archive/0.1.0.tar.gz',
      author='Thiago de Arruda',
      author_email='tpadilha84@gmail.com',
      license='Apache',
      packages=['neovim', 'neovim.api', 'neovim.msgpack_rpc', 'neovim.ui',
                'neovim.msgpack_rpc.event_loop', 'neovim.plugin'],
      install_requires=install_requires,
      ext_modules=ext_modules,
      extras_require=extras_require,
      entry_points=entry_points,
      zip_safe=False)
