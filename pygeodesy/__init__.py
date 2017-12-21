
# -*- coding: utf-8 -*-

u'''A pure Python implementation of geodesy tools for various ellipsoidal
and spherical earth models using precision trigonometric and vector-based
methods for geodetic (lat-/longitude) and geocentric cartesian (x/y/z)
coordinates.

Transcribed from U{JavaScript originals<https://github.com/chrisveness/geodesy>}
by I{Chris Veness (C) 2005-2016} and published under the same U{MIT License
<http://opensource.org/licenses/MIT>}**.

There are two modules for ellipsoidal earth models, I{ellipsoidalVincenty}
and I{-Nvector} and two for spherical ones, I{sphericalTrigonometry} and
I{-Nvector}.  Each module provides a I{attributes-LatLon-html} class with methods
to compute distance, initial and final bearing, intermediate points and
conversions, among other things.  For more information and further details
see the U{documentation<https://mrjean1.github.io/PyGeodesy/>}, the descriptions
of U{Latitude/Longitude<http://www.movable-type.co.uk/scripts/latlong.html>},
U{Vincenty<http://www.movable-type.co.uk/scripts/latlong-vincenty.html>} and
U{Vector-based<http://www.movable-type.co.uk/scripts/latlong-vectors.html>} geodesy
and the original U{JavaScript source<https://github.com/chrisveness/geodesy>} or
U{docs<http://www.movable-type.co.uk/scripts/geodesy/docs/>}.

Also included are modules for conversions to and from
U{UTM<http://www.movable-type.co.uk/scripts/latlong-utm-mgrs.html>}
(Universal Transverse Mercator) and U{Web Mercator
<http://wikipedia.org/wiki/Web_Mercator>} (Pseudo-Mercator) coordinates,
U{MGRS<http://www.movable-type.co.uk/scripts/latlong-utm-mgrs.html>}
(NATO Military Grid Reference System) and
U{OSGR<http://www.movable-type.co.uk/scripts/latlong-os-gridref.html>}
(British Ordinance Survery Grid Reference) grid references and a module for
encoding and decoding U{Geohashes<http://www.movable-type.co.uk/scripts/geohash.html>}.

Two other modules provide Lambert conformal conic projections and positions
(from U{John P. Snyder, "Map Projections -- A Working Manual", 1987, pp 107-109
<http://pubs.er.USGS.gov/djvu/PP/PP_1395.pdf>}) and several functions to
U{simplify<http://bost.ocks.org/mike/simplify/>} or linearize a path of
I{LatLon} points (or a U{NumPy array
<https://docs.scipy.org/doc/numpy/reference/generated/numpy.array.html>}),
including implementations of the U{Ramer-Douglas-Peucker
<http://wikipedia.org/wiki/Ramer-Douglas-Peucker_algorithm>}, the
U{Visvalingam-Whyatt<http://hydra.hull.ac.uk/resources/hull:8338>} and the
U{Reumann-Witkam<http://psimpl.sourceforge.net/reumann-witkam.html>}
algorithms and modified versions of the former.

All Python source code has been statically
U{checked<http://code.activestate.com/recipes/546532>} with
U{PyChecker<http://pypi.python.org/pypi/pychecker>},
U{PyFlakes<http://pypi.python.org/pypi/pyflakes>},
U{PyCodeStyle<http://pypi.python.org/pypi/pycodestyle>} (formerly Pep8) and
U{McCabe<http://pypi.python.org/pypi/mccabe>} using 64-bit Python 2.7.14 and with
U{Flake8<http://pypi.python.org/pypi/flake8>} on 64-bit Python 3.6.3.

The tests have been run with 64-bit Python 2.6.9 (and numpy 1.6.2), 2.7.14
(and numpy 1.13.1), 3.5.3, 3.6.4 and with 64-bit Intel-Python 3.5.3 (and
numpy 1.11.3), all on macOS 10.12.6 Sierra and with Pythonista 3.1 using
64-bit Python 2.7.12 and 3.5.1 (both with numpy 1.8.0) on iOS 11.2.1.

Previously, the tests were run with 64-bit Python 2.7.13 and 3.6.2 on MacOS
X 10.10 Yosemite and MacOS X 10.11 El Capitan, with 64-bit Python 2.7.10
(and numpy 1.8.0rc1) and 64-bit Python 3.6.3 and 3.6.4 on macOS 10.13.2 High
Sierra, with Pythonista 3.1 on iOS 10.3.3, 11.0.3 and 11.1.2, with 32-bit
Python 2.6.6 on Windows XP SP3 and with 32-bit Python 2.7.14 on Window 10 Pro.

In addition to the U{PyGeodesy<http://pypi.python.org/pypi/PyGeodesy>} package,
the distribution files contain the tests, the test results and the complete
documentation (generated by U{Epydoc<http://pypi.python.org/pypi/epydoc>} using
command line:
C{epydoc --html --no-private --no-source --name=PyGeodesy --url=... -v pygeodesy}).

Some function and method names differ from the JavaScript version. In such
cases documentation tag B{JS name:} shows the original JavaScript name.

__

**) U{Copyright (C) 2016-2018 -- mrJean1 at Gmail dot com
<http://opensource.org/licenses/MIT>}

C{Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:}

C{The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.}

C{THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.}

@newfield example: Example, Examples
@newfield JSname: JS name, JS names

@var EPS:  System's M{epsilon} (float)
@var EPS1: M{1 - EPS} (float), about 0.9999999999999998
@var EPS2: M{sqrt(EPS)} (float)

@var F_D:   Format degrees as deg° (string).
@var F_DM:  Format degrees as deg°min′ (string).
@var F_DMS: Format degrees as deg°min′sec″ (string).
@var F_DEG: Format degrees as [D]DD without symbol (string).
@var F_MIN: Format degrees as [D]DDMM without symbols (string).
@var F_SEC: Format degrees as [D]DDMMSS without symbols (string).
@var F_RAD: Convert degrees to radians and format as RR (string).

@var PI:   Constant M{math.pi} (float)
@var PI2:  Two PI, M{math.pi * 2} (float)
@var PI_2: Half PI, M{math.pi / 2} (float)

@var R_EQ: Spherical earth radius at equator (meter).
@var R_KM: Mean, spherical earth radius (kilo meter).
@var R_M:  Mean, spherical earth radius (meter).
@var R_NM: Mean, spherical earth radius (nautical miles).
@var R_SM: Mean, spherical earth radius (statute miles).

@var S_DEG: Degrees symbol ° (string).
@var S_MIN: Minutes symbol ′ (string).
@var S_SEC: Seconds symbol ″ (string).
@var S_RAD: Radians symbol  (string).
@var S_SEP: Separator between deg°, min′ and sec″  (string).

@var Conics:     Registered conics (enum).
@var Datums:     Registered datums (enum).
@var Ellipsoids: Registered ellipsoids (enum).
@var Transforms: Registered transforms (enum).

@var version: Normalized PyGeodesy version (string).

'''

try:
    import bases  # PYCHOK expected
except ImportError:
    # extend sys.path to include this very directory
    # such that all public and private sub-modules can
    # be imported (and checked by PyChecker, etc.)
    import os, sys  # PYCHOK expected
    sys.path.insert(0, os.path.dirname(__file__))  # XXX __path__[0]
    del os, sys

# keep ellipsoidal, spherical and vector modules as sub-modules
import ellipsoidalNvector  # PYCHOK false
import ellipsoidalVincenty  # PYCHOK false
import geohash
import nvector  # PYCHOK false
import sphericalNvector  # PYCHOK false
import sphericalTrigonometry  # PYCHOK false
import vector3d  # PYCHOK false

Geohash       = geohash.Geohash
nearestOn2    = sphericalTrigonometry.nearestOn2  # not -Nvector
VincentyError = ellipsoidalVincenty.VincentyError

# all public sub-modules, contants, classes and functions
__all__ = ('ellipsoidalNvector', 'ellipsoidalVincenty',  # modules
           'sphericalNvector', 'sphericalTrigonometry',
           'datum', 'dms', 'geohash', 'lcc', 'mgrs', 'nvector',
           'osgr', 'points', 'simplify', 'utils', 'utm',
           'vector3d', 'webmercator',
           'Geohash', 'VincentyError',  # classes
           'nearestOn2',  # functions
           'version')  # extended below
__version__ = '17.12.20'

# see setup.py for similar logic
version = '.'.join(map(str, map(int, __version__.split('.'))))

# lift all public classes, constants, functions, etc. but
# only from the following sub-modules ... (see also David
# Beazley's <http://dabeaz.com/modulepackage/index.html>)
from datum       import *  # PYCHOK __all__
from dms         import *  # PYCHOK __all__
from lcc         import *  # PYCHOK __all__
from mgrs        import *  # PYCHOK __all__
from osgr        import *  # PYCHOK __all__
from points      import *  # PYCHOK __all__
from simplify    import *  # PYCHOK __all__
from utils       import *  # PYCHOK __all__
from utm         import *  # PYCHOK __all__
from webmercator import *  # PYCHOK __all__

import datum        # PYCHOK expected
import dms          # PYCHOK expected
import lcc          # PYCHOK expected
import mgrs         # PYCHOK expected
import osgr         # PYCHOK expected
import points       # PYCHOK expected
import simplify     # PYCHOK expected
import utils        # PYCHOK expected
import utm          # PYCHOK expected
import webmercator  # PYCHOK expected

# concat __all__ with the public classes, constants,
# functions, etc. from the sub-modules mentioned above
for m in (datum, dms, lcc, mgrs, osgr, points,
          simplify, utils, utm, webmercator):
    __all__ += tuple(_ for _ in m.__all__ if _ not in ('nearestOn2',))
del m

# try:  # remove private, INTERNAL modules
#     del bases, ellipsoidalBase, sphericalBase  # PYCHOK expected
# except NameError:
#     pass

if __name__ == '__main__':

    d = locals()
    for i, n in enumerate(sorted(__all__)):
        print('%s %s %r' % (i + 1, n, d[n]))
    print('--- PyGeodesy %s' % (__version__,))

# **) MIT License
#
# Copyright (C) 2016-2018 -- mrJean1 at Gmail dot com
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
