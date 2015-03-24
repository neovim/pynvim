import platform
import sys

from setuptools import setup

install_requires = [
    'click>=3.0',
    'msgpack-python>=0.4.0',
]

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

setup(name='neovim',
      version='0.0.31',
      description='Python client to neovim',
      url='http://github.com/neovim/python-client',
      download_url='https://github.com/neovim/python-client/archive/0.0.31.tar.gz',
      author='Thiago de Arruda',
      author_email='tpadilha84@gmail.com',
      license='MIT',
      packages=['neovim', 'neovim.api', 'neovim.msgpack_rpc', 'neovim.ui',
                'neovim.msgpack_rpc.event_loop', 'neovim.plugin'],
      install_requires=install_requires,
      ext_modules=cythonize('neovim/ui/screen.py') if has_cython else None,
      entry_points='''
      [console_scripts]
      pynvim=neovim.ui.cli:main
      ''',
      zip_safe=False)
