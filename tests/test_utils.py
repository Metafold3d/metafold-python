from metafold.utils import xform
from numpy.testing import assert_allclose


def test_xform():
    m = xform([1.0, 2.0, 3.0])  # T
    assert_allclose(m, [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [1.0, 2.0, 3.0, 1.0],
    ], atol=1.0e-7)

    m = xform(
        rotation=[180.0, -90.0, 0.0])  # R
    assert_allclose(m, [
        [0.0,  0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0, 0.0],
        [1.0,  0.0, 0.0, 0.0],
        [0.0,  0.0, 0.0, 1.0],
    ], atol=1.0e-7)

    m = xform(
        [1.0, 2.0, 3.0],      # T
        [180.0, -90.0, 0.0])  # R
    assert_allclose(m, [
        [0.0,  0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0, 0.0],
        [1.0,  0.0, 0.0, 0.0],
        [1.0,  2.0, 3.0, 1.0],
    ], atol=1.0e-7)

