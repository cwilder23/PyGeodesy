
# -*- coding: utf-8 -*-

u'''(INTERNAL) Spherical base classes C{CartesianSphericalBase} and
C{LatLonSphericalBase}.

Pure Python implementation of geodetic (lat-/longitude) functions,
transcribed in part from JavaScript originals by I{(C) Chris Veness 2011-2016}
and published under the same MIT Licence**, see
U{Latitude/Longitude<https://www.Movable-Type.co.UK/scripts/latlong.html>}.

@newfield example: Example, Examples
'''

from pygeodesy.basics import EPS, NN, PI, PI2, PI_2, \
                             property_doc_, _xinstanceof
from pygeodesy.cartesianBase import CartesianBase
from pygeodesy.datum import R_M, R_MA, Datum, Datums
from pygeodesy.dms import parse3llh
from pygeodesy.ecef import EcefKarney
from pygeodesy.errors import IntersectionError, _IsnotError
from pygeodesy.fmath import acos1, favg, fsum_
from pygeodesy.latlonBase import LatLonBase
from pygeodesy.lazily import _ALL_DOCS
from pygeodesy.named import Bearing2Tuple
from pygeodesy.nvectorBase import NvectorBase
from pygeodesy.units import Bearing_, Distance, Height, Radius, Radius_
from pygeodesy.utily import degrees90, degrees180, degrees360, \
                            sincos2, tanPI_2_2, wrapPI

from math import atan2, cos, hypot, log, sin, sqrt

# XXX the following classes are listed only to get
# Epydoc to include class and method documentation
__all__ = _ALL_DOCS('CartesianSphericalBase', 'LatLonSphericalBase')
__version__ = '20.06.15'


def _angular(distance, radius):  # PYCHOK for export
    '''(INTERNAL) Return the angular distance in radians.

       @raise ValueError: Invalid B{C{distance}} or B{C{radius}}.
    '''
    return Distance(distance) / Radius_(radius)


def _rads3(rad1, rad2, radius):  # in .sphericalTrigonometry
    '''(INTERNAL) Convert radii to radians.
    '''
    r1 = Radius_(rad1, name='rad1')
    r2 = Radius_(rad2, name='rad2')
    r = radius
    if r is not None:  # convert radii to radians
        r = 1.0 / Radius_(r,  name='radius')
        r1 *= r
        r2 *= r

    if r1 < r2:
        r1, r2, r = r2, r1, True
    else:
        r = False
    if r1 > PI:
        raise IntersectionError(rad1=rad1, rad2=rad2,
                                txt='exceeds PI radians')
    return r1, r2, r


class CartesianSphericalBase(CartesianBase):
    '''(INTERNAL) Base class for spherical C{Cartesian}s.
    '''
    _datum = Datums.Sphere  #: (INTERNAL) L{Datum}.
    _Ecef  = EcefKarney     #: (INTERNAL) Preferred C{Ecef...} class.

    def intersections2(self, rad1, other, rad2, radius=R_M):
        '''Compute the intersection points of two circles each defined
           by a center point and a radius.

           @arg rad1: Radius of the this circle (C{meter} or C{radians},
                      see B{C{radius}}).
           @arg other: Center of the other circle (C{Cartesian}).
           @arg rad2: Radius of the other circle (C{meter} or C{radians},
                      see B{C{radius}}).
           @kwarg radius: Mean earth radius (C{meter} or C{None} if both
                          B{C{rad1}} and B{C{rad2}} are given in C{radians}).

           @return: 2-Tuple of the intersection points, each C{Cartesian}.
                    The intersection points are the same C{Cartesian}
                    instance for abutting circles.

           @raise IntersectionError: Concentric, antipodal, invalid or
                                     non-intersecting circles.

           @raise TypeError: If B{C{other}} is not C{Cartesian}.

           @raise ValueError: Invalid B{C{rad1}}, B{C{rad2}} or B{C{radius}}.

           @see: U{Java code<https://GIS.StackExchange.com/questions/48937/
                 calculating-intersection-of-two-circles>}.
        '''
        self.others(other)

        x1, x2 = self, other
        r1, r2, x = _rads3(rad1, rad2, radius)
        if x:
            x1, x2 = x2, x1

        n, q = x1.cross(x2), x1.dot(x2)
        n2, q21 = n.dot(n), 1 - q**2
        if min(abs(q21), n2) < EPS:
            raise IntersectionError(center=self, other=other,
                                    txt='near-concentric')
        try:
            cr1, cr2 = cos(r1), cos(r2)
            a = (cr1 - q * cr2) / q21
            b = (cr2 - q * cr1) / q21
            x0 = x1.times(a).plus(x2.times(b))
        except ValueError:
            raise IntersectionError(center=self, rad1=rad1,
                                    other=other, rad2=rad2)
        x = 1 - x0.dot(x0)
        if x < EPS:
            raise IntersectionError(center=self, rad1=rad1,
                                    other=other, rad2=rad2, txt='too distant')
        n = n.times(sqrt(x / n2))
        if n.length > EPS:
            x1, x2 = x0.plus(n), x0.minus(n)
            for x in (x1, x2):
                x.datum = self.datum
                x.name  = self.intersections2.__name__
            return x1, x2
        else:  # abutting circles
            x0.datum = self.datum
            x0.name  = self.intersections2.__name__
            return x0, x0


class LatLonSphericalBase(LatLonBase):
    '''(INTERNAL) Base class for spherical C{LatLon}s.
    '''
    _datum = Datums.Sphere  #: (INTERNAL) Spherical L{Datum}.
    _Ecef  = EcefKarney     #: (INTERNAL) Preferred C{Ecef...} class.

    def __init__(self, lat, lon, height=0, datum=None, name=NN):
        '''Create a spherical C{LatLon} point frome the given
           lat-, longitude and height on the given datum.

           @arg lat: Latitude (C{degrees} or DMS C{[N|S]}).
           @arg lon: Longitude (C{degrees} or DMS C{str[E|W]}).
           @kwarg height: Optional elevation (C{meter}, the same units
                          as the datum's half-axes).
           @kwarg datum: Optional, shperical datum to use (L{Datum}).
           @kwarg name: Optional name (string).

           @raise TypeError: B{C{datum}} is not a L{datum} or
                             not spherical.

           @example:

           >>> p = LatLon(51.4778, -0.0016)  # height=0, datum=Datums.WGS84
        '''
        LatLonBase.__init__(self, lat, lon, height=height, name=name)
        if datum:
            self.datum = datum

    def bearingTo2(self, other, wrap=False, raiser=False):
        '''Return the initial and final bearing (forward and reverse
           azimuth) from this to an other point.

           @arg other: The other point (C{LatLon}).
           @kwarg wrap: Wrap and unroll longitudes (C{bool}).
           @kwarg raiser: Optionally, raise L{CrossError} (C{bool}).

           @return: A L{Bearing2Tuple}C{(initial, final)}.

           @raise TypeError: The I{other} point is not spherical.

           @see: Methods C{initialBearingTo} and C{finalBearingTo}.
        '''
        # .initialBearingTo is inside .-Nvector and .-Trigonometry
        i = self.initialBearingTo(other, wrap=wrap, raiser=raiser)  # PYCHOK .initialBearingTo
        f = self.finalBearingTo(  other, wrap=wrap, raiser=raiser)
        return self._xnamed(Bearing2Tuple(i, f))

    @property_doc_(''' this point's datum (L{Datum}).''')
    def datum(self):
        '''Get this point's datum (L{Datum}).
        '''
        return self._datum

    @datum.setter  # PYCHOK setter!
    def datum(self, datum):
        '''Set this point's datum I{without conversion}.

           @arg datum: New datum (L{Datum}).

           @raise TypeError: If B{C{datum}} is not a L{Datum}
                             or not spherical.
        '''
        _xinstanceof(Datum, datum=datum)
        if not datum.isSpherical:
            raise _IsnotError('spherical', datum=datum)
        self._update(datum != self._datum)
        self._datum = datum

    def finalBearingTo(self, other, wrap=False, raiser=False):
        '''Return the final bearing (reverse azimuth) from this to
           an other point.

           @arg other: The other point (spherical C{LatLon}).
           @kwarg wrap: Wrap and unroll longitudes (C{bool}).
           @kwarg raiser: Optionally, raise L{CrossError} (C{bool}).

           @return: Final bearing (compass C{degrees360}).

           @raise TypeError: The I{other} point is not spherical.

           @example:

           >>> p = LatLon(52.205, 0.119)
           >>> q = LatLon(48.857, 2.351)
           >>> b = p.finalBearingTo(q)  # 157.9
        '''
        self.others(other)

        # final bearing is the reverse of the other, initial one;
        # .initialBearingTo is inside .-Nvector and .-Trigonometry
        b = other.initialBearingTo(self, wrap=wrap, raiser=raiser)
        return (b + 180) % 360  # == wrap360 since b >= 0

    def maxLat(self, bearing):
        '''Return the maximum latitude reached when travelling
           on a great circle on given bearing from this point
           based on Clairaut's formula.

           The maximum latitude is independent of longitude
           and the same for all points on a given latitude.

           Negate the result for the minimum latitude (on the
           Southern hemisphere).

           @arg bearing: Initial bearing (compass C{degrees360}).

           @return: Maximum latitude (C{degrees90}).

           @raise ValueError: Invalid B{C{bearing}}.

           @JSname: I{maxLatitude}.
        '''
        m = acos1(abs(sin(Bearing_(bearing)) * cos(self.phi)))
        return degrees90(m)

    def minLat(self, bearing):
        '''Return the minimum latitude reached when travelling
           on a great circle on given bearing from this point.

           @arg bearing: Initial bearing (compass C{degrees360}).

           @return: Minimum latitude (C{degrees90}).

           @see: Method L{maxLat} for more details.

           @raise ValueError: Invalid B{C{bearing}}.

           @JSname: I{minLatitude}.
        '''
        return -self.maxLat(bearing)

    def parse(self, strll, height=0, sep=','):
        '''Parse a string representing lat-/longitude point and
           return a C{LatLon}.

           The lat- and longitude must be separated by a sep[arator]
           character.  If height is present it must follow and be
           separated by another sep[arator].  Lat- and longitude
           may be swapped, provided at least one ends with the
           proper compass direction.

           For more details, see functions L{parse3llh} and L{parseDMS}
           in module L{dms}.

           @arg strll: Lat, lon [, height] (C{str}).
           @kwarg height: Optional, default height (C{meter}).
           @kwarg sep: Optional separator (C{str}).

           @return: The point (spherical C{LatLon}).

           @raise ValueError: Invalid B{C{strll}}.
        '''
        return self.classof(*parse3llh(strll, height=height, sep=sep))

    def _rhumb3(self, other):
        '''(INTERNAL) Rhumb_ helper function.

           @arg other: The other point (spherical C{LatLon}).
        '''
        self.others(other)

        a1, b1 = self.philam
        a2, b2 = other.philam
        # if |db| > 180 take shorter rhumb
        # line across the anti-meridian
        db = wrapPI(b2 - b1)
        dp = log(tanPI_2_2(a2) / tanPI_2_2(a1))
        return (a2 - a1), db, dp

    def rhumbBearingTo(self, other):
        '''Return the initial bearing (forward azimuth) from this to
           an other point along a rhumb (loxodrome) line.

           @arg other: The other point (spherical C{LatLon}).

           @return: Initial bearing (compass C{degrees360}).

           @raise TypeError: The I{other} point is not spherical.

           @example:

           >>> p = LatLon(51.127, 1.338)
           >>> q = LatLon(50.964, 1.853)
           >>> b = p.rhumbBearingTo(q)  # 116.7
        '''
        _, db, dp = self._rhumb3(other)
        return degrees360(atan2(db, dp))

    def rhumbDestination(self, distance, bearing, radius=R_M, height=None):
        '''Return the destination point having travelled along a rhumb
           (loxodrome) line from this point the given distance on the
           given bearing.

           @arg distance: Distance travelled (C{meter}, same units as
                          I{radius}).
           @arg bearing: Bearing from this point (compass C{degrees360}).
           @kwarg radius: Mean earth radius (C{meter}).
           @kwarg height: Optional height, overriding the default height
                          (C{meter}, same unit as I{radius}).

           @return: The destination point (spherical C{LatLon}).

           @raise ValueError: Invalid B{C{distance}}, B{C{bearing}},
                              B{C{radius}} or B{C{height}}.

           @example:

           >>> p = LatLon(51.127, 1.338)
           >>> q = p.rhumbDestination(40300, 116.7)  # 50.9642°N, 001.8530°E

           @JSname: I{rhumbDestinationPoint}
        '''
        r = _angular(distance, radius)

        a1, b1 = self.philam
        sb, cb = sincos2(Bearing_(bearing))

        da = r * cb
        a2 = a1 + da
        # normalize latitude if past pole
        if a2 > PI_2:
            a2 =  PI - a2
        elif a2 < -PI_2:
            a2 = -PI - a2

        dp = log(tanPI_2_2(a2) / tanPI_2_2(a1))
        # E-W course becomes ill-conditioned with 0/0
        q  = (da / dp) if abs(dp) > EPS else cos(a1)
        b2 = (b1 + r * sb / q) if abs(q) > EPS else b1

        h = self.height if height is None else Height(height)
        return self.classof(degrees90(a2), degrees180(b2), height=h)

    def rhumbDistanceTo(self, other, radius=R_M):
        '''Return the distance from this to an other point along a rhumb
           (loxodrome) line.

           @arg other: The other point (spherical C{LatLon}).
           @kwarg radius: Mean earth radius (C{meter}).

           @return: Distance (C{meter}, the same units as I{radius}).

           @raise TypeError: The B{C{other}} point is not spherical.

           @raise ValueError: Invalid B{C{radius}}.

           @example:

           >>> p = LatLon(51.127, 1.338)
           >>> q = LatLon(50.964, 1.853)
           >>> d = p.rhumbDistanceTo(q)  # 403100
        '''
        # see <https://www.EdWilliams.org/avform.htm#Rhumb>
        da, db, dp = self._rhumb3(other)

        # on Mercator projection, longitude distances shrink
        # by latitude; the 'stretch factor' q becomes ill-
        # conditioned along E-W line (0/0); use an empirical
        # tolerance to avoid it
        q = (da / dp) if abs(dp) > EPS else cos(self.phi)
        return hypot(da, q * db) * Radius(radius)

    def rhumbMidpointTo(self, other, height=None):
        '''Return the (loxodromic) midpoint between this and
           an other point.

           @arg other: The other point (spherical LatLon).
           @kwarg height: Optional height, overriding the mean height
                          (C{meter}).

           @return: The midpoint (spherical C{LatLon}).

           @raise TypeError: The I{other} point is not spherical.

           @raise ValueError: Invalid B{C{height}}.

           @example:

           >>> p = LatLon(51.127, 1.338)
           >>> q = LatLon(50.964, 1.853)
           >>> m = p.rhumb_midpointTo(q)
           >>> m.toStr()  # '51.0455°N, 001.5957°E'
        '''
        self.others(other)

        # see <https://MathForum.org/library/drmath/view/51822.html>
        a1, b1 = self.philam
        a2, b2 = other.philam
        if abs(b2 - b1) > PI:
            b1 += PI2  # crossing anti-meridian

        a3 = favg(a1, a2)
        b3 = favg(b1, b2)

        f1 = tanPI_2_2(a1)
        if abs(f1) > EPS:
            f2 = tanPI_2_2(a2)
            f = f2 / f1
            if abs(f) > EPS:
                f = log(f)
                if abs(f) > EPS:
                    f3 = tanPI_2_2(a3)
                    b3 = fsum_(b1 * log(f2),
                              -b2 * log(f1), (b2 - b1) * log(f3)) / f

        h = self._havg(other) if height is None else Height(height)
        return self.classof(degrees90(a3), degrees180(b3), height=h)

    def toNvector(self, Nvector=NvectorBase, **Nvector_kwds):  # PYCHOK signature
        '''Convert this point to C{Nvector} components, I{including
           height}.

           @kwarg Nvector_kwds: Optional, additional B{C{Nvector}}
                                keyword arguments, ignored if
                                B{C{Nvector=None}}.

           @return: An B{C{Nvector}} or a L{Vector4Tuple}C{(x, y, z, h)}
                    if B{C{Nvector}} is C{None}.

           @raise TypeError: Invalid B{C{Nvector}} or B{C{Nvector_kwds}}.
        '''
        return LatLonBase.toNvector(self, Nvector=Nvector, **Nvector_kwds)

    def toWm(self, radius=R_MA):
        '''Convert this point to a I{WM} coordinate.

           @kwarg radius: Optional earth radius (C{meter}).

           @return: The WM coordinate (L{Wm}).

           @see: Function L{toWm} in module L{webmercator} for details.
        '''
        from pygeodesy.webmercator import toWm  # PYCHOK recursive import
        return toWm(self, radius=radius)

# **) MIT License
#
# Copyright (C) 2016-2020 -- mrJean1 at Gmail -- All Rights Reserved.
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
