#Setup file for compiling pixelmath module using distutils
#With this setupA.py, and a file pixelmathA.c, running

#python setup.py build

#will compile pixelmath.c, and produce an extension module 
#named pixelmath in the build directory. Depending on the system, 
#the module file will end up in a subdirectory build/lib.system, 
#and may have a name like pixelmath.so or pixelmath.pyd.
#
# See https://docs.python.org/2/extending/building.html#building

from distutils.core import setup, Extension

module1 = Extension('pixelmathA',
                    sources = ['pixelmathA.c'])

setup (name = 'Pixelmath rev A',
       version = '1.1',
       description = 'Module for doing pixel compensation of Seek thermal images',
       ext_modules = [module1])
