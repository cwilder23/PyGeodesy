
# -*- coding: utf-8 -*-

u'''Classes L{HeightCubic}, L{HeightIDWcosineAndoyerLambert},
L{HeightIDWcosineForsytheAndoyerLambert}, L{HeightIDWcosineLaw},
L{HeightIDWdistanceTo}, L{HeightIDWequirectangular}, L{HeightIDWeuclidean},
L{HeightIDWflatLocal}, L{HeightIDWflatPolar}, L{HeightIDWhaversine},
L{HeightIDWhubeny}, L{HeightIDWkarney}, L{HeightIDWthomas}, L{HeightIDWvincentys},
L{HeightLinear}, L{HeightLSQBiSpline} and L{HeightSmoothBiSpline}
to interpolate the height of C{LatLon} locations or separate
lat-/longitudes from a set of C{LatLon} points with known heights.

Classes L{HeightCubic} and L{HeightLinear} require package U{numpy
<https://PyPI.org/project/numpy>}, classes L{HeightLSQBiSpline} and
L{HeightSmoothBiSpline} require package U{scipy<https://SciPy.org>} and
classes L{HeightIDWdistanceTo} -iff used with L{ellipsoidalKarney.LatLon}
points- and L{HeightIDWkarney} requires I{Charles Karney's}
U{geographiclib<https://PyPI.org/project/geographiclib>} to be
installed.

Typical usage is as follows.  First create an interpolator from a
given set of C{LatLon} points with known heights, called C{knots}.

C{hinterpolator = HeightXyz(knots, **options)}

Get the interpolated height of other C{LatLon} location(s) with

C{h = hinterpolator(ll)}

or

C{h0, h1, h2, ... = hinterpolator(ll0, ll1, ll2, ...)}

or

C{hs = hinterpolator(lls)}  # C{list, tuple, generator, ...}

For separate lat-/longitudes invoke the C{.height} method

C{h = hinterpolator.height(lat, lon)}

or

C{h0, h1, h2, ... = hinterpolator.height(lats, lons)}  # C{list, ...}


The C{knots} do not need to be ordered for any of the height
interpolators.

Errors from C{scipy} as raised as L{SciPyError}s.  Warnings issued
by C{scipy} can be thrown as L{SciPyWarning} exceptions, provided
Python C{warnings} are filtered accordingly, see L{SciPyWarning}.

@see: U{SciPy<https://docs.SciPy.org/doc/scipy/reference/interpolate.html>}.
'''

from pygeodesy.basics import EPS, PI, NN, PI2, PI_2, _bkwds, \
                             isscalar, len2, map1, map2, \
                             property_RO, _xinstanceof
from pygeodesy.datum import Datum, Datums
from pygeodesy.errors import _AssertionError, _item_, LenError, PointsError, \
                             _SciPyIssue
from pygeodesy.fmath import fidw, hypot2
from pygeodesy.formy import cosineAndoyerLambert_, cosineForsytheAndoyerLambert_, \
                            cosineLaw_, euclidean_, flatPolar_, haversine_, \
                            _scale_rad, thomas_, vincentys_
from pygeodesy.lazily import _ALL_DOCS, _ALL_LAZY, _FOR_DOCS
from pygeodesy.named import _Named, notOverloaded
from pygeodesy.points import LatLon_
from pygeodesy.units import Int_
from pygeodesy.utily import radiansPI, radiansPI2, unrollPI

__all__ = _ALL_LAZY.heights + _ALL_DOCS('_HeightBase')
__version__ = '20.06.17'


class HeightError(PointsError):
    '''Height interpolator C{Height...} or interpolation issue.
    '''
    pass


def _alist(ais):
    # return list of floats, not numpy.float64s
    return list(map(float, ais))


def _allis2(llis, m=1, Error=HeightError):  # imported by .geoids
    # dtermine return type and convert lli C{LatLon}s to list
    if not isinstance(llis, tuple):  # llis are *args
        raise _AssertionError('type(%s): %r' % ('*llis', llis))

    n = len(llis)
    if n == 1:  # convert single lli to 1-item list
        llis = llis[0]
        try:
            n, llis = len2(llis)
            _as = _alist  # return list of interpolated heights
        except TypeError:  # single lli
            n, llis = 1, [llis]
            _as = _ascalar  # return single interpolated heights
    else:  # of 0, 2 or more llis
        _as = _atuple  # return tuple of interpolated heights

    if n < m:
        raise _insufficientError(m, Error=Error, llis=n)
    return _as, llis


def _ascalar(ais):  # imported by .geoids
    # return single float, not numpy.float64
    ais = list(ais)  # np.array, etc. to list
    if len(ais) != 1:
        raise _AssertionError('len(%r): %s != 1' % (ais, len(ais)))
    return float(ais[0])  # remove np.<type>


def _atuple(ais):
    # return tuple of floats, not numpy.float64s
    return tuple(map(float, ais))


def _axyllis4(atype, llis, m=1, off=True):
    # convert lli C{LatLon}s to tuples or C{NumPy} arrays of
    # C{SciPy} sphericals and determine the return type
    _as, llis = _allis2(llis, m=m)
    xis, yis, _ =  zip(*_xyhs(llis, off=off))  # PYCHOK unzip
    return _as, atype(xis), atype(yis), llis


def _insufficientError(need, Error=HeightError, **name_value):
    # create an insufficient Error instance
    t = 'insufficient, need %s' % (need,)
    return Error(txt=t, **name_value)


def _ordedup(ts, lo=EPS, hi=PI2-EPS):
    # clip, order and remove duplicates
    p, ks = 0, []
    for k in sorted(max(lo, min(hi, t)) for t in ts):
        if k > p:
            ks.append(k)
            p = k
    return ks


def _xyhs(lls, off=True, name='llis'):
    # map (lat, lon, h) to (x, y, h) in radians, offset as
    # x: 0 <= lon <= PI2, y: 0 <= lat <= PI if off is True
    # else x: -PI <= lon <= PI, y: -PI_2 <= lat <= PI_2
    if off:
        xf = yf = 0.0
    else:  # undo offset
        xf, yf = PI, PI_2
    try:
        for i, ll in enumerate(lls):
            yield (max(0.0, radiansPI2(ll.lon + 180.0)) - xf), \
                  (max(0.0, radiansPI( ll.lat +  90.0)) - yf), ll.height
    except AttributeError as x:
        raise HeightError(_item_(name, i), ll, txt=str(x))


def _xyhs3(atype, m, knots, off=True):
    # convert knot C{LatLon}s to tuples or C{NumPy} arrays and C{SciPy} sphericals
    xs, ys, hs = zip(*_xyhs(knots, off=off, name='knots'))  # PYCHOK unzip
    n = len(hs)
    if n < m:
        raise _insufficientError(m, knots=n)
    return map1(atype, xs, ys, hs)


class _HeightBase(_Named):  # imported by .geoids
    '''(INTERNAL) Interpolator base class.
    '''
    _adjust = None  # not applicable
    _datum  = None  # not applicable
    _kmin   = 2     # min number of knots
    _np     = None  # numpy
    _np_v   = None  # version
    _spi    = None  # scipy.interpolate
    _sp_v   = None  # version
    _wrap   = None  # not applicable

    def __call__(self, *args):  # PYCHOK no cover
        '''(INTERNAL) I{Must be overloaded}.
        '''
        notOverloaded(self, '__call__', *args)

    @property_RO
    def adjust(self):
        '''Get the adjust setting (C{bool} or C{None} if not applicable).
        '''
        return self._adjust

    def _axyllis4(self, llis):
        return _axyllis4(self._np.array, llis)

    @property_RO
    def datum(self):
        '''Get the datum (L{Datum} or C{None} if not applicable).
        '''
        return self._datum

    def _ev(self, *args):  # PYCHOK no cover
        '''(INTERNAL) I{Must be overloaded}.
        '''
        notOverloaded(self, self._ev, *args)

    def _eval(self, llis):  # XXX single arg, not *args
        _as, xis, yis, _ = self._axyllis4(llis)
        try:  # SciPy .ev signature: y first, then x!
            return _as(self._ev(yis, xis))
        except Exception as x:
            raise _SciPyIssue(x)

    def _height(self, lats, lons, Error=HeightError):
        if isscalar(lats) and isscalar(lons):
            llis = LatLon_(lats, lons)
        else:
            n, lats = len2(lats)
            m, lons = len2(lons)
            if n != m:
                # format a LenError, but raise an Error
                e = LenError(self.__class__, lats=n, lons=m, txt=None)
                raise e if Error is LenError else Error(str(e))
            llis = [LatLon_(*ll) for ll in zip(lats, lons)]
        return self(llis)  # __call__(lli) or __call__(llis)

    @property_RO
    def kmin(self):
        '''Get the minimum number of knots (C{int}).
        '''
        return self._kmin

    def _NumSciPy(self, throwarnings=False):
        '''(INTERNAL) Import C{numpy} and C{scipy}.
        '''
        if throwarnings:  # raise SciPyWarnings, but ...
            # ... not if scipy has been imported already
            import sys
            if 'scipy' not in sys.modules:
                import warnings
                warnings.filterwarnings('error')

        import scipy as sp
        import scipy.interpolate as spi
        import numpy as np

        _HeightBase._np   = np
        _HeightBase._np_v = np.__version__
        _HeightBase._spi  = spi
        _HeightBase._sp_v = sp.__version__

        return np, spi

    def _xyhs3(self, knots):
        return _xyhs3(self._np.array, self._kmin, knots)

    @property_RO
    def wrap(self):
        '''Get the wrap setting (C{bool} or C{None} if not applicable).
        '''
        return self._wrap


class HeightCubic(_HeightBase):
    '''Height interpolator based on C{SciPy} U{interp2d<https://docs.SciPy.org/
       doc/scipy/reference/generated/scipy.interpolate.interp2d.html>}
       C{kind='cubic'}.
    '''
    _interp2d =  None
    _kind     = 'cubic'
    _kmin     =  16

    def __init__(self, knots, name=NN):
        '''New L{HeightCubic} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               invalid B{C{knot}}.

           @raise ImportError: Package C{numpy} or C{scipy} not found
                               or not installed.

           @raise SciPyError: A C{scipy.interpolate.interp2d} issue.

           @raise SciPyWarning: A C{scipy.interpolate.interp2d} warning
                                as exception.
        '''
        _, spi = self._NumSciPy()

        xs, ys, hs = self._xyhs3(knots)
        try:  # SciPy.interpolate.interp2d kind 'linear' or 'cubic'
            self._interp2d = spi.interp2d(xs, ys, hs, kind=self._kind)
        except Exception as x:
            raise _SciPyIssue(x)

        if name:
            self.name = name

    def __call__(self, *llis):
        '''Interpolate the height for one or several locations.

           @arg llis: The location or locations (C{LatLon}, ... or
                      C{LatLon}s).

           @return: A single interpolated height (C{float}) or a list
                    or tuple of interpolated heights (C{float}s).

           @raise HeightError: Insufficient number of B{C{llis}} or
                               an invalid B{C{lli}}.

           @raise SciPyError: A C{scipy.interpolate.interp2d} issue.

           @raise SciPyWarning: A C{scipy.interpolate.interp2d} warning
                                as exception.
        '''
        return _HeightBase._eval(self, llis)

    def _ev(self, yis, xis):  # PYCHOK expected
        # to make SciPy .interp2d signature(x, y), single (x, y)
        # match SciPy .ev signature(ys, xs), flipped multiples
        return map(self._interp2d, xis, yis)

    def height(self, lats, lons):
        '''Interpolate the height for one or several lat-/longitudes.

           @arg lats: Latitude or latitudes (C{degrees} or C{degrees}s).
           @arg lons: Longitude or longitudes (C{degrees} or C{degrees}s).

           @return: A single interpolated height (C{float}) or a list of
                    interpolated heights (C{float}s).

           @raise HeightError: Insufficient or non-matching number of
                               B{C{lats}} and B{C{lons}}.

           @raise SciPyError: A C{scipy.interpolate.interp2d} issue.

           @raise SciPyWarning: A C{scipy.interpolate.interp2d} warning
                                as exception.
        '''
        return _HeightBase._height(self, lats, lons)


class HeightLinear(HeightCubic):
    '''Height interpolator based on C{SciPy} U{interp2d<https://docs.SciPy.org/
       doc/scipy/reference/generated/scipy.interpolate.interp2d.html>}
       C{kind='linear}.
    '''
    _kind = 'linear'
    _kmin =  2

    def __init__(self, knots, name=NN):
        '''New L{HeightLinear} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}}.

           @raise ImportError: Package C{numpy} or C{scipy} not found
                               or not installed.

           @raise SciPyError: A C{scipy.interpolate.interp2d} issue.

           @raise SciPyWarning: A C{scipy.interpolate.interp2d} warning
                                as exception.
        '''
        HeightCubic.__init__(self, knots, name=name)

    if _FOR_DOCS:  # PYCHOK no cover
        __call__ = HeightCubic.__call__
        height   = HeightCubic.height


class _HeightIDW(_HeightBase):
    '''(INTERNAL) Base class for U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW)
       height interpolators.
    '''
    _beta = 0     # inverse distance power
    _hs   = ()    # known heights
    _xs   = ()    # knot lons
    _ys   = ()    # knot lats

    def __init__(self, knots, beta=2, name=NN, **wrap_adjust):
        '''New L{_HeightIDW} interpolator.
        '''
        self._xs, self._ys, self._hs = _xyhs3(tuple, self._kmin, knots, off=False)
        self.beta = beta
        if name:
            self.name = name
        if wrap_adjust:
            _bkwds(self, Error=HeightError, **wrap_adjust)

    def __call__(self, *llis):
        '''Interpolate the height for one or several locations.

           @arg llis: The location or locations (C{LatLon}, ... or
                      C{LatLon}s).

           @return: A single interpolated height (C{float}) or a list
                    or tuple of interpolated heights (C{float}s).

           @raise HeightError: Insufficient number of B{C{llis}},
                               an invalid B{C{lli}} or an L{fidw}
                               issue.
        '''
        _as, xis, yis, _ = _axyllis4(tuple, llis, off=False)
        return _as(map(self._hIDW, xis, yis))

    def _datum_setter(self, datum, knots):
        '''(INTERNAL) Set the datum.
        '''
        d = datum or getattr(knots[0], 'datum', datum)
        if d and d != self.datum:
            _xinstanceof(Datum, datum=d)
            self._datum = d

    def _distances(self, x, y):  # PYCHOK unused (x, y) radians
        '''Must be overloaded.
        '''
        raise NotImplementedError('method: %s' % (self._distances.__name__,))

    def _distances_angular_(self, func_, x, y):
        # return angular distances from func_
        for xk, yk in zip(self._xs, self._ys):
            r, _ = unrollPI(xk, x, wrap=self._wrap)
            yield func_(yk, y, r)

    def _distances_angular_datum_(self, func_, x, y):
        # return angular distances from func_
        for xk, yk in zip(self._xs, self._ys):
            r, _ = unrollPI(xk, x, wrap=self._wrap)
            yield func_(yk, y, r, datum=self._datum)

    def _hIDW(self, x, y):
        # interpolate height at (x, y) radians or degrees
        try:
            ds = self._distances(x, y)
            return fidw(self._hs, ds, beta=self._beta)
        except ValueError as x:
            raise HeightError(str(x))

    @property
    def beta(self):
        '''Get the inverse distance power (C{int}).
        '''
        return self._beta

    @beta.setter  # PYCHOK setter!
    def beta(self, beta):
        '''Set the inverse distance power.

           @arg beta: New inverse distance power (C{int} 1, 2, or 3).

           @raise HeightError: Invalid B{C{beta}}.
        '''
        self._beta = Int_(beta, name='beta', Error=HeightError, low=1, high=3)

    def height(self, lats, lons):
        '''Interpolate the height for one or several lat-/longitudes.

           @arg lats: Latitude or latitudes (C{degrees} or C{degrees}s).
           @arg lons: Longitude or longitudes (C{degrees} or C{degrees}s).

           @return: A single interpolated height (C{float}) or a list of
                    interpolated heights (C{float}s).

           @raise HeightError: Insufficient or non-matching number of
                               B{C{lats}} and B{C{lons}} or an L{fidw}
                               issue.
        '''
        return _HeightBase._height(self, lats, lons)


class HeightIDWcosineAndoyerLambert(_HeightIDW):
    '''Height interpolator using U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW)
       and the I{angular} distance in C{radians} from function
       L{cosineAndoyerLambert_}.

       @see: L{HeightIDWcosineForsytheAndoyerLambert}, L{HeightIDWdistanceTo},
             L{HeightIDWflatLocal}, L{HeightIDWhubeny}, L{HeightIDWthomas},
             U{IDW<https://www.Geo.FU-Berlin.DE/en/v/soga/Geodata-analysis/
             geostatistics/Inverse-Distance-Weighting/index.html>} and
             U{SHEPARD_INTERP_2D<https://People.SC.FSU.edu/~jburkardt/c_src/
             shepard_interp_2d/shepard_interp_2d.html>}.
    '''
    _datum = Datums.WGS84
    _wrap  = False

    def __init__(self, knots, datum=None, beta=2, wrap=False, name=NN):
        '''New L{HeightIDWcosineAndoyerLambert} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg datum: Optional datum overriding the default C{Datums.WGS84}
                         and first B{C{knots}}' datum (L{Datum}).
           @kwarg beta: Inverse distance power (C{int} 1, 2, or 3).
           @kwarg wrap: Wrap and L{unrollPI} longitudes (C{bool}).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}} or B{C{beta}}.

           @raise TypeError: Invalid B{C{datum}}.
        '''
        _HeightIDW.__init__(self, knots, beta=beta, name=name, wrap=wrap)
        self._datum_setter(datum, knots)

    def _distances(self, x, y):  # (x, y) radians
        return self._distances_angular_datum_(cosineAndoyerLambert_, x, y)

    if _FOR_DOCS:  # PYCHOK no cover
        __call__ = _HeightIDW.__call__
        height   = _HeightIDW.height


class HeightIDWcosineForsytheAndoyerLambert(_HeightIDW):
    '''Height interpolator using U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW)
       and the I{angular} distance in C{radians} from function
       L{cosineForsytheAndoyerLambert_}.

       @see: L{HeightIDWcosineAndoyerLambert}, L{HeightIDWdistanceTo},
             L{HeightIDWflatLocal}, L{HeightIDWhubeny}, L{HeightIDWthomas},
             U{IDW<https://www.Geo.FU-Berlin.DE/en/v/soga/Geodata-analysis/
             geostatistics/Inverse-Distance-Weighting/index.html>} and
             U{SHEPARD_INTERP_2D<https://People.SC.FSU.edu/~jburkardt/c_src/
             shepard_interp_2d/shepard_interp_2d.html>}.
    '''
    _datum = Datums.WGS84
    _wrap  = False

    def __init__(self, knots, datum=None, beta=2, wrap=False, name=NN):
        '''New L{HeightIDWcosineForsytheAndoyerLambert} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg datum: Optional datum overriding the default C{Datums.WGS84}
                         and first B{C{knots}}' datum (L{Datum}).
           @kwarg beta: Inverse distance power (C{int} 1, 2, or 3).
           @kwarg wrap: Wrap and L{unrollPI} longitudes (C{bool}).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}} or B{C{beta}}.

           @raise TypeError: Invalid B{C{datum}}.
        '''
        _HeightIDW.__init__(self, knots, beta=beta, name=name, wrap=wrap)
        self._datum_setter(datum, knots)

    def _distances(self, x, y):  # (x, y) radians
        return self._distances_angular_datum_(cosineForsytheAndoyerLambert_, x, y)

    if _FOR_DOCS:  # PYCHOK no cover
        __call__ = _HeightIDW.__call__
        height   = _HeightIDW.height


class HeightIDWcosineLaw(_HeightIDW):
    '''Height interpolator using U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW)
       and the I{angular} distance in C{radians} from function L{cosineLaw_}.

       @see: L{HeightIDWequirectangular}, L{HeightIDWeuclidean},
             L{HeightIDWflatPolar}, L{HeightIDWhaversine}, L{HeightIDWvincentys},
             U{IDW<https://www.Geo.FU-Berlin.DE/en/v/soga/Geodata-analysis/
             geostatistics/Inverse-Distance-Weighting/index.html>} and
             U{SHEPARD_INTERP_2D<https://People.SC.FSU.edu/~jburkardt/c_src/
             shepard_interp_2d/shepard_interp_2d.html>}.

       @note: See note at function L{vincentys_}.
    '''
    _wrap = False

    def __init__(self, knots, beta=2, wrap=False, name=NN):
        '''New L{HeightIDWcosineLaw} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg beta: Inverse distance power (C{int} 1, 2, or 3).
           @kwarg wrap: Wrap and L{unrollPI} longitudes (C{bool}).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}} or B{C{beta}}.
        '''
        _HeightIDW.__init__(self, knots, beta=beta, name=name, wrap=wrap)

    def _distances(self, x, y):  # (x, y) radians
        return self._distances_angular_(cosineLaw_, x, y)

    if _FOR_DOCS:  # PYCHOK no cover
        __call__ = _HeightIDW.__call__
        height   = _HeightIDW.height


class HeightIDWdistanceTo(_HeightIDW):
    '''Height interpolator using U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW)
       and the distance from the points' C{LatLon.distanceTo} method,
       conventionally in C{meter}.

       @see: L{HeightIDWcosineAndoyerLambert}, L{HeightIDWcosineForsytheAndoyerLambert},
             L{HeightIDWflatPolar}, L{HeightIDWkarney}, L{HeightIDWthomas},
             U{IDW<https://www.Geo.FU-Berlin.DE/en/v/soga/Geodata-analysis/
             geostatistics/Inverse-Distance-Weighting/index.html>} and
             U{SHEPARD_INTERP_2D<https://People.SC.FSU.edu/~jburkardt/c_src/
             shepard_interp_2d/shepard_interp_2d.html>}.
    '''
    _distanceTo_kwds = {}
    _ks              = ()

    def __init__(self, knots, beta=2, name=NN, **distanceTo_kwds):
        '''New L{HeightIDWdistanceTo} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg beta: Inverse distance power (C{int} 1, 2, or 3).
           @kwarg name: Optional name for this height interpolator (C{str}).
           @kwarg distanceTo_kwds: Optional keyword arguments for the
                                   B{C{points}}' C{LatLon.distanceTo}
                                   method.

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}} or B{C{beta}}.

           @raise ImportError: Package U{GeographicLib
                  <https://PyPI.org/project/geographiclib>} missing
                  iff B{C{points}} are L{ellipsoidalKarney.LatLon}s.

           @note: All B{C{points}} I{must} be instances of the same
                  ellipsoidal or spherical C{LatLon} class, I{not
                  checked however}.
        '''
        n, self._ks = len2(knots)
        if n < self._kmin:
            raise _insufficientError(self._kmin, knots=n)

        self.beta = beta
        if name:
            self.name = name
        if distanceTo_kwds:
            self._distanceTo_kwds = distanceTo_kwds

    def __call__(self, *llis):
        '''Interpolate the height for one or several locations.

           @arg llis: The location or locations (C{LatLon}, ... or
                      C{LatLon}s).

           @return: A single interpolated height (C{float}) or a list
                    or tuple of interpolated heights (C{float}s).

           @raise HeightError: Insufficient number of B{C{llis}},
                               an invalid B{C{lli}} or an L{fidw}
                               issue.
        '''
        _as, llis = _allis2(llis)
        return _as(map(self._hIDW, llis))

    def height(self, lats, lons):  # PYCHOK unused
        '''Interpolate the height for one or several lat-/longitudes.

           @raise HeightError: Not implemented.
        '''
        return HeightError('not implemented: %s.%s' % (self.classname, self.height.__name__))

    def _hIDW(self, lli):  # PYCHOK expected
        # interpolate height at point lli
        try:
            kwds = self._distanceTo_kwds
            ds = (k.distanceTo(lli, **kwds) for k in self._ks)
            return fidw(self._hs, ds, beta=self._beta)
        except ValueError as x:
            raise HeightError(str(x))

    @property_RO
    def _hs(self):  # see HeightIDWkarney
        for k in self._ks:
            yield k.height


class HeightIDWequirectangular(_HeightIDW):
    '''Height interpolator using U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW) and
       the I{angular} distance in C{radians squared} like function
       L{equirectangular_}.

       @see: L{HeightIDWeuclidean}, L{HeightIDWflatPolar},
             L{HeightIDWhaversine}, L{HeightIDWvincentys},
             U{IDW<https://www.Geo.FU-Berlin.DE/en/v/soga/Geodata-analysis/
             geostatistics/Inverse-Distance-Weighting/index.html>} and
             U{SHEPARD_INTERP_2D<https://People.SC.FSU.edu/~jburkardt/c_src/
             shepard_interp_2d/shepard_interp_2d.html>}.
    '''
    _adjust = True
    _wrap   = False

    def __init__(self, knots, adjust=True, wrap=False, name=NN):
        '''New L{HeightIDWequirectangular} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg adjust: Adjust the wrapped, unrolled longitudinal
                          delta by the cosine of the mean latitude (C{bool}).
           @kwarg wrap: Wrap and L{unrollPI} longitudes (C{bool}).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}}.
        '''
        _HeightIDW.__init__(self, knots, beta=1, name=name, wrap=wrap,
                                                          adjust=adjust)

    def _distances(self, x, y):  # (x, y) radians**2
        for xk, yk in zip(self._xs, self._ys):
            d, _ = unrollPI(xk, x, wrap=self._wrap)
            if self._adjust:
                d *= _scale_rad(yk, y)
            yield hypot2(d, yk - y)  # like equirectangular_ distance2

    if _FOR_DOCS:  # PYCHOK no cover
        __call__ = _HeightIDW.__call__
        height   = _HeightIDW.height


class HeightIDWeuclidean(_HeightIDW):
    '''Height interpolator using U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW)
       and the I{angular} distance in C{radians} from function L{euclidean_}.

       @see: L{HeightIDWcosineLaw}, L{HeightIDWequirectangular},
             L{HeightIDWhaversine}, L{HeightIDWvincentys},
             U{IDW<https://www.Geo.FU-Berlin.DE/en/v/soga/Geodata-analysis/
             geostatistics/Inverse-Distance-Weighting/index.html>} and
             U{SHEPARD_INTERP_2D<https://People.SC.FSU.edu/~jburkardt/c_src/
             shepard_interp_2d/shepard_interp_2d.html>}.
    '''
    _adjust = True

    def __init__(self, knots, adjust=True, beta=2, name=NN):
        '''New L{HeightIDWeuclidean} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg adjust: Adjust the longitudinal delta by the cosine
                          of the mean latitude for B{C{adjust}}=C{True}.
           @kwarg beta: Inverse distance power (C{int} 1, 2, or 3).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}} or B{C{beta}}.
        '''
        _HeightIDW.__init__(self, knots, beta=beta, name=name, adjust=adjust)

    def _distances(self, x, y):  # (x, y) radians
        for xk, yk in zip(self._xs, self._ys):
            yield euclidean_(yk, y, xk - x, adjust=self._adjust)

    if _FOR_DOCS:  # PYCHOK no cover
        __call__ = _HeightIDW.__call__
        height   = _HeightIDW.height


class HeightIDWflatLocal(_HeightIDW):
    '''Height interpolator using U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW)
       and the I{angular} distance in C{radians squared} like function
       L{flatLocal_}/L{hubeny_}.

       @see: L{HeightIDWcosineAndoyerLambert}, L{HeightIDWcosineForsytheAndoyerLambert},
             L{HeightIDWdistanceTo}, L{HeightIDWhubeny}, L{HeightIDWthomas},
             U{IDW<https://www.Geo.FU-Berlin.DE/en/v/soga/Geodata-analysis/
             geostatistics/Inverse-Distance-Weighting/index.html>} and
             U{SHEPARD_INTERP_2D<https://People.SC.FSU.edu/~jburkardt/c_src/
             shepard_interp_2d/shepard_interp_2d.html>}.
    '''
    _datum = Datums.WGS84
    _wrap  = False

    def __init__(self, knots, datum=None, beta=2, wrap=False, name=NN):
        '''New L{HeightIDWflatLocal}/L{HeightIDWhubeny} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg datum: Optional datum overriding the default C{Datums.WGS84}
                         and first B{C{knots}}' datum (L{Datum}).
           @kwarg beta: Inverse distance power (C{int} 1, 2, or 3).
           @kwarg wrap: Wrap and L{unrollPI} longitudes (C{bool}).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}} or B{C{beta}}.

           @raise TypeError: Invalid B{C{datum}}.
        '''
        _HeightIDW.__init__(self, knots, beta=beta, name=name, wrap=wrap)
        self._datum_setter(datum, knots)

    def _distances(self, x, y):  # (x, y) radians
        _r2_ = self._datum.ellipsoid._hubeny2_
        return self._distances_angular_(_r2_, x, y)  # radians**2

    if _FOR_DOCS:  # PYCHOK no cover
        __call__ = _HeightIDW.__call__
        height   = _HeightIDW.height


class HeightIDWflatPolar(_HeightIDW):
    '''Height interpolator using U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW)
       and the I{angular} distance in C{radians} from function L{flatPolar_}.

       @see: L{HeightIDWcosineLaw}, L{HeightIDWequirectangular},
             L{HeightIDWeuclidean}, L{HeightIDWhaversine}, L{HeightIDWvincentys},
             U{IDW<https://www.Geo.FU-Berlin.DE/en/v/soga/Geodata-analysis/
             geostatistics/Inverse-Distance-Weighting/index.html>} and
             U{SHEPARD_INTERP_2D<https://People.SC.FSU.edu/~jburkardt/c_src/
             shepard_interp_2d/shepard_interp_2d.html>}.
    '''
    _wrap = False

    def __init__(self, knots, beta=2, wrap=False, name=NN):
        '''New L{HeightIDWflatPolar} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg beta: Inverse distance power (C{int} 1, 2, or 3).
           @kwarg wrap: Wrap and L{unrollPI} longitudes (C{bool}).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}} or B{C{beta}}.
        '''
        _HeightIDW.__init__(self, knots, beta=beta, name=name, wrap=wrap)

    def _distances(self, x, y):  # (x, y) radians
        return self._distances_angular_(flatPolar_, x, y)

    if _FOR_DOCS:  # PYCHOK no cover
        __call__ = _HeightIDW.__call__
        height   = _HeightIDW.height


class HeightIDWhaversine(_HeightIDW):
    '''Height interpolator using U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW)
       and the I{angular} distance in C{radians} from function L{haversine_}.

       @see: L{HeightIDWcosineLaw}, L{HeightIDWequirectangular}, L{HeightIDWeuclidean},
             L{HeightIDWflatPolar}, L{HeightIDWvincentys},
             U{IDW<https://www.Geo.FU-Berlin.DE/en/v/soga/Geodata-analysis/
             geostatistics/Inverse-Distance-Weighting/index.html>} and
             U{SHEPARD_INTERP_2D<https://People.SC.FSU.edu/~jburkardt/c_src/
             shepard_interp_2d/shepard_interp_2d.html>}.

       @note: See note at function L{vincentys_}.
    '''
    _wrap = False

    def __init__(self, knots, beta=2, wrap=False, name=NN):
        '''New L{HeightIDWhaversine} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg beta: Inverse distance power (C{int} 1, 2, or 3).
           @kwarg wrap: Wrap and L{unrollPI} longitudes (C{bool}).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an  B{C{knot}} or B{C{beta}}.
        '''
        _HeightIDW.__init__(self, knots, beta=beta, name=name, wrap=wrap)

    def _distances(self, x, y):  # (x, y) radians
        return self._distances_angular_(haversine_, x, y)

    if _FOR_DOCS:  # PYCHOK no cover
        __call__ = _HeightIDW.__call__
        height   = _HeightIDW.height


class HeightIDWhubeny(HeightIDWflatLocal):  # for Karl Hubeny
    if _FOR_DOCS:  # PYCHOK no cover
        __doc__  = HeightIDWflatLocal.__doc__
        __init__ = HeightIDWflatLocal.__init__
        __call__ = HeightIDWflatLocal.__call__
        height   = HeightIDWflatLocal.height


class HeightIDWkarney(_HeightIDW):
    '''Height interpolator using U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW) and
       the I{angular} distance in C{degrees} from I{Charles F. F. Karney's}
       U{GeographicLib<https://PyPI.org/project/geographiclib>} U{Geodesic
       <https://geographiclib.sourceforge.io/1.49/python/code.html>}
       Inverse method.

       @see: L{HeightIDWcosineAndoyerLambert},
             L{HeightIDWcosineForsytheAndoyerLambert}, L{HeightIDWdistanceTo},
             L{HeightIDWflatLocal}, L{HeightIDWhubeny}, L{HeightIDWthomas},
             U{IDW<https://www.Geo.FU-Berlin.DE/en/v/soga/Geodata-analysis/
             geostatistics/Inverse-Distance-Weighting/index.html>} and
             U{SHEPARD_INTERP_2D<https://People.SC.FSU.edu/~jburkardt/c_src/
             shepard_interp_2d/shepard_interp_2d.html>}.
    '''
    _datum    = Datums.WGS84
    _Inverse1 = None
    _ks       = ()
    _wrap     = False

    def __init__(self, knots, datum=None, beta=2, wrap=False, name=NN):
        '''New L{HeightIDWkarney} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg datum: Optional datum overriding the default C{Datums.WGS84}
                         and first B{C{knots}}' datum (L{Datum}).
           @kwarg beta: Inverse distance power (C{int} 1, 2, or 3).
           @kwarg wrap: Wrap and L{unroll180} longitudes (C{bool}).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}}, B{C{datum}} or
                               B{C{beta}}.

           @raise ImportError: Package U{GeographicLib
                  <https://PyPI.org/project/geographiclib>} missing.

           @raise TypeError: Invalid B{C{datum}}.
        '''
        n, self._ks = len2(knots)
        if n < self._kmin:
            raise _insufficientError(self._kmin, knots=n)
        self._datum_setter(datum, self._ks)
        self._Inverse1 = self.datum.ellipsoid.geodesic.Inverse1

        self.beta = beta
        if wrap:
            self._wrap = True
        if name:
            self.name = name

    def _distances(self, x, y):  # (x, y) degrees
        for k in self._ks:
            # non-negative I{angular} distance in C{degrees}
            yield self._Inverse1(y, x, k.lat, k.lon, wrap=self._wrap)

    @property_RO
    def _hs(self):  # see HeightIDWdistanceTo
        for k in self._ks:
            yield k.height

    def __call__(self, *llis):
        '''Interpolate the height for one or several locations.

           @arg llis: The location or locations (C{LatLon}, ... or
                      C{LatLon}s).

           @return: A single interpolated height (C{float}) or a list
                    or tuple of interpolated heights (C{float}s).

           @raise HeightError: Insufficient number of B{C{llis}},
                               an invalid B{C{lli}} or an L{fidw}
                               issue.
        '''
        def _xy2(lls):
            try:  # like _xyhs above, but keeping degrees
                for i, ll in enumerate(lls):
                    yield ll.lon, ll.lat
            except AttributeError as x:
                raise HeightError(_item_('llis', i), ll, txt=str(x))

        _as, llis = _allis2(llis)
        return _as(map(self._hIDW, *zip(*_xy2(llis))))

    if _FOR_DOCS:  # PYCHOK no cover
        height   = _HeightIDW.height


class HeightIDWthomas(_HeightIDW):
    '''Height interpolator using U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW)
       and the I{angular} distance in C{radians} from function L{thomas_}.

       @see: L{HeightIDWcosineAndoyerLambert}, L{HeightIDWcosineForsytheAndoyerLambert},
             L{HeightIDWdistanceTo}, L{HeightIDWflatLocal}, L{HeightIDWhubeny},
             U{IDW<https://www.Geo.FU-Berlin.DE/en/v/soga/Geodata-analysis/
             geostatistics/Inverse-Distance-Weighting/index.html>} and
             U{SHEPARD_INTERP_2D<https://People.SC.FSU.edu/~jburkardt/c_src/
             shepard_interp_2d/shepard_interp_2d.html>}.
    '''
    _datum = Datums.WGS84
    _wrap  = False

    def __init__(self, knots, datum=None, beta=2, wrap=False, name=NN):
        '''New L{HeightIDWthomas} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg datum: Optional datum overriding the default C{Datums.WGS84}
                         and first B{C{knots}}' datum (L{Datum}).
           @kwarg beta: Inverse distance power (C{int} 1, 2, or 3).
           @kwarg wrap: Wrap and L{unrollPI} longitudes (C{bool}).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}} or B{C{beta}}.

           @raise TypeError: Invalid B{C{datum}}.
        '''
        _HeightIDW.__init__(self, knots, beta=beta, name=name, wrap=wrap)
        self._datum_setter(datum, knots)

    def _distances(self, x, y):  # (x, y) radians
        return self._distances_angular_datum_(thomas_, x, y)

    if _FOR_DOCS:  # PYCHOK no cover
        __call__ = _HeightIDW.__call__
        height   = _HeightIDW.height


class HeightIDWvincentys(_HeightIDW):
    '''Height interpolator using U{Inverse Distance Weighting
       <https://WikiPedia.org/wiki/Inverse_distance_weighting>} (IDW)
       and the I{angular} distance in C{radians} from function L{vincentys_}.

       @see: L{HeightIDWcosineLaw}, L{HeightIDWequirectangular},
             L{HeightIDWeuclidean}, L{HeightIDWflatPolar}, L{HeightIDWhaversine},
             U{IDW<https://www.Geo.FU-Berlin.DE/en/v/soga/Geodata-analysis/
             geostatistics/Inverse-Distance-Weighting/index.html>} and
             U{SHEPARD_INTERP_2D<https://People.SC.FSU.edu/~jburkardt/c_src/
             shepard_interp_2d/shepard_interp_2d.html>}.

       @note: See note at function L{vincentys_}.
    '''
    _wrap = False

    def __init__(self, knots, beta=2, wrap=False, name=NN):
        '''New L{HeightIDWvincentys} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg beta: Inverse distance power (C{int} 1, 2, or 3).
           @kwarg wrap: Wrap and L{unrollPI} longitudes (C{bool}).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}} or B{C{beta}}.
        '''
        _HeightIDW.__init__(self, knots, beta=beta, name=name, wrap=wrap)

    def _distances(self, x, y):  # (x, y) radians
        return self._distances_angular_(vincentys_, x, y)

    if _FOR_DOCS:  # PYCHOK no cover
        __call__ = _HeightIDW.__call__
        height   = _HeightIDW.height


class HeightLSQBiSpline(_HeightBase):
    '''Height interpolator using C{SciPy} U{LSQSphereBivariateSpline
       <https://docs.SciPy.org/doc/scipy/reference/generated/scipy.
       interpolate.LSQSphereBivariateSpline.html>}.
    '''
    _kmin = 16  # k = 3, always

    def __init__(self, knots, weight=None, name=NN):
        '''New L{HeightLSQBiSpline} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg weight: Optional weight or weights for each B{C{knot}}
                          (C{scalar} or C{scalar}s).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}} or B{C{weight}}.

           @raise LenError: Number of B{C{knots}} and B{C{weight}}s
                            don't match.

           @raise ImportError: Package C{numpy} or C{scipy} not found
                               or not installed.

           @raise SciPyError: A C{LSQSphereBivariateSpline} issue.

           @raise SciPyWarning: A C{LSQSphereBivariateSpline} warning
                                as exception.
        '''
        np, spi = self._NumSciPy()

        xs, ys, hs = self._xyhs3(knots)
        n = len(hs)

        w = weight
        if isscalar(w):
            w = float(w)
            if w <= 0:
                raise HeightError(weight=w)
            w = [w] * n
        elif w is not None:
            m, w = len2(w)
            if m != n:
                raise LenError(HeightLSQBiSpline, weight=m, knots=n)
            w = map2(float, w)
            m = min(w)
            if m <= 0:
                raise HeightError(_item_(weight=w.find(m)), m)
        try:
            T = 1.0e-4  # like SciPy example
            ps = np.array(_ordedup(xs, T, PI2 - T))
            ts = np.array(_ordedup(ys, T, PI  - T))
            self._ev = spi.LSQSphereBivariateSpline(ys, xs, hs,
                                                    ts, ps, eps=EPS, w=w).ev
        except Exception as x:
            raise _SciPyIssue(x)

        if name:
            self.name = name

    def __call__(self, *llis):
        '''Interpolate the height for one or several locations.

           @arg llis: The location or locations (C{LatLon}, ... or
                      C{LatLon}s).

           @return: A single interpolated height (C{float}) or a list
                    or tuple of interpolated heights (C{float}s).

           @raise HeightError: Insufficient number of B{C{llis}} or
                               an invalid B{C{lli}}.

           @raise SciPyError: A C{LSQSphereBivariateSpline} issue.

           @raise SciPyWarning: A C{LSQSphereBivariateSpline} warning
                                as exception.
        '''
        return _HeightBase._eval(self, llis)

    def height(self, lats, lons):
        '''Interpolate the height for one or several lat-/longitudes.

           @arg lats: Latitude or latitudes (C{degrees} or C{degrees}s).
           @arg lons: Longitude or longitudes (C{degrees} or C{degrees}s).

           @return: A single interpolated height (C{float}) or a list of
                    interpolated heights (C{float}s).

           @raise HeightError: Insufficient or non-matching number of
                               B{C{lats}} and B{C{lons}}.

           @raise SciPyError: A C{LSQSphereBivariateSpline} issue.

           @raise SciPyWarning: A C{LSQSphereBivariateSpline} warning
                                as exception.
        '''
        return _HeightBase._height(self, lats, lons)


class HeightSmoothBiSpline(_HeightBase):
    '''Height interpolator using C{SciPy} U{SmoothSphereBivariateSpline
       <https://docs.SciPy.org/doc/scipy/reference/generated/scipy.
       interpolate.SmoothSphereBivariateSpline.html>}.
    '''
    _kmin = 16  # k = 3, always

    def __init__(self, knots, s=4, name=NN):
        '''New L{HeightSmoothBiSpline} interpolator.

           @arg knots: The points with known height (C{LatLon}s).
           @kwarg s: The spline smoothing factor (C{4}).
           @kwarg name: Optional name for this height interpolator (C{str}).

           @raise HeightError: Insufficient number of B{C{knots}} or
                               an invalid B{C{knot}} or B{C{s}}.

           @raise ImportError: Package C{numpy} or C{scipy} not found
                               or not installed.

           @raise SciPyError: A C{SmoothSphereBivariateSpline} issue.

           @raise SciPyWarning: A C{SmoothSphereBivariateSpline} warning
                                as exception.
        '''
        _, spi = self._NumSciPy()

        s = Int_(s, name='smooting', Error=HeightError, low=4)

        xs, ys, hs = self._xyhs3(knots)
        try:
            self._ev = spi.SmoothSphereBivariateSpline(ys, xs, hs,
                                                       eps=EPS, s=s).ev
        except Exception as x:
            raise _SciPyIssue(x)

        if name:
            self.name = name

    def __call__(self, *llis):
        '''Interpolate the height for one or several locations.

           @arg llis: The location or locations (C{LatLon}, ... or
                      C{LatLon}s).

           @return: A single interpolated height (C{float}) or a list
                    or tuple of interpolated heights (C{float}s).

           @raise HeightError: Insufficient number of B{C{llis}} or
                               an invalid B{C{lli}}.

           @raise SciPyError: A C{SmoothSphereBivariateSpline} issue.

           @raise SciPyWarning: A C{SmoothSphereBivariateSpline} warning
                                as exception.
        '''
        return _HeightBase._eval(self, llis)

    def height(self, lats, lons):
        '''Interpolate the height for one or several lat-/longitudes.

           @arg lats: Latitude or latitudes (C{degrees} or C{degrees}s).
           @arg lons: Longitude or longitudes (C{degrees} or C{degrees}s).

           @return: A single interpolated height (C{float}) or a list of
                    interpolated heights (C{float}s).

           @raise HeightError: Insufficient or non-matching number of
                               B{C{lats}} and B{C{lons}}.

           @raise SciPyError: A C{SmoothSphereBivariateSpline} issue.

           @raise SciPyWarning: A C{SmoothSphereBivariateSpline} warning
                                as exception.
        '''
        return _HeightBase._height(self, lats, lons)

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
