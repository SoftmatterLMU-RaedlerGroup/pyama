# Tests for the class `pyama.stack.shape.Shape`

from collections import OrderedDict
import pytest
from pyama.stack.shape import Shape


def init_shape():
    return Shape(dict(T=100, C=2, X=1500, Y=1000))


def test_init():
    assert init_shape().shape, OrderedDict([('T', 100), ('C', 2), ('Z', None), ('Y', 1000), ('X', 1500)])


def test_init_missing_dim():
    with pytest.raises(ValueError):
        Shape(dict(C=2, X=1500, Y=1000))


def test_init_none_dim():
    with pytest.raises(ValueError):
        Shape(dict(T=100, C=None, X=1500, Y=1000))


def test_reshape():
    s = init_shape()
    s.reshape(C=3)
    assert s, OrderedDict([('T', 100), ('C', 3), ('Z', None), ('Y', 1000), ('X', 1500)])


def test_getitem():
    s = init_shape()
    assert s['T'], 100


def test_setitem():
    s = init_shape()
    s['C'] += 1
    assert s, OrderedDict([('T', 100), ('C', 3), ('Z', None), ('Y', 1000), ('X', 1500)])


def test_reshape_forbidden():
    s = init_shape()
    with pytest.raises(ValueError):
        s.reshape(X=2000)


def test_make_reshapable():
    s = init_shape()
    s.make_reshapable('X')
    s.reshape(X=2000)
    assert s['X'], 2000


def test_make_fixed():
    s = init_shape()
    s.make_fixed('C')
    with pytest.raises(ValueError):
        s['C'] = 3


def test_reshape_notification():
    changed_dims = None

    def on_notify(changes):
        nonlocal changed_dims
        changed_dims = changes

    s = init_shape()
    s.register_listener(on_notify)
    s.reshape(C=3)
    assert changed_dims, dict(C=dict(old=2, new=3))
