from numpy.typing import ArrayLike
from scipy.spatial.transform import Rotation as R  # type: ignore
from typing import Optional
import numpy as np


def xform(
    translation: Optional[ArrayLike] = None,
    rotation: Optional[ArrayLike] = None,
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

    r = R.from_euler("xyz", rotation,  degrees=True).as_matrix()
    m = np.eye(4)
    m[:3, :3] = r
    m[3, :3] = translation
    return m
