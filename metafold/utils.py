import hashlib
from typing import List
from numpy.typing import ArrayLike
from scipy.spatial.transform import Rotation as R  # type: ignore
import numpy as np
import re


def xform(
    translation: ArrayLike | None = None,
    rotation: ArrayLike | None = None,
) -> np.ndarray:
    """Compose transformation matrix.

    Args:
         translation: Translation in the x, y, and z directions.
         rotation: Euler angles in degrees. Rotation is applied in the order Rz, Ry, Rx.

     Returns:
         4 x 4 affine transformation matrix.
    """
    translation = translation or np.array([0.0, 0.0, 0.0])
    rotation = rotation or np.array([0.0, 0.0, 0.0])

    r = R.from_euler("xyz", rotation, degrees=True).as_matrix()
    m = np.eye(4)
    m[:3, :3] = r
    m[3, :3] = translation
    return m


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def natural_sort(l: List):
    def natural_key(s):
        return [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", s)]

    return sorted(l, key=natural_key)
