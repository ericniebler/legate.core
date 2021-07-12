# Copyright 2021 NVIDIA Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import numpy as np

import legate.core.types as ty

from .legion import AffineTransform
from .partition import Tiling
from .shape import Shape


class Transform(object):
    def __repr__(self):
        return str(self)

    def serialize(self, launcher):
        code = self._runtime.get_transform_code(self.__class__.__name__)
        launcher.add_scalar_arg(code, ty.int32)


class Shift(Transform):
    def __init__(self, runtime, dim, offset):
        self._runtime = runtime
        self._dim = dim
        self._offset = offset

    def compute_shape(self, shape):
        return shape

    def __str__(self):
        return f"Shift(dim: {self._dim}, slice: {self._offset})"

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self._dim == other._dim and self._offset == other._offset

    def __hash__(self):
        return hash((type(self), self._dim, self._offset))

    @property
    def invertible(self):
        return True

    def invert(self, partition):
        if isinstance(partition, Tiling):
            offset = partition.offset[self._dim] - self._offset
            return Tiling(
                self._runtime,
                partition.tile_shape,
                partition.color_shape,
                partition.offset.update(self._dim, offset),
            )
        else:
            raise ValueError(
                f"Unsupported partition: {type(partition).__name__}"
            )

    def get_inverse_transform(self, shape, parent_transform=None):
        result = AffineTransform(shape.ndim, shape.ndim, True)
        result.offset[self._dim] = -self._offset
        if parent_transform is not None:
            result = result.compose(parent_transform)
        return result

    def serialize(self, launcher):
        super(Shift, self).serialize(launcher)
        launcher.add_scalar_arg(self._dim, ty.int32)
        launcher.add_scalar_arg(self._offset, ty.int64)


class Promote(Transform):
    def __init__(self, runtime, extra_dim, dim_size):
        self._runtime = runtime
        self._extra_dim = extra_dim
        self._dim_size = dim_size

    def compute_shape(self, shape):
        return shape.insert(self._extra_dim, self._dim_size)

    def __str__(self):
        return f"Promote(dim: {self._extra_dim}, size: {self._dim_size})"

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return (
            self._extra_dim == other._extra_dim
            and self._dim_size == other._dim_size
        )

    def __hash__(self):
        return hash((type(self), self._extra_dim, self._dim_size))

    @property
    def invertible(self):
        return True

    def invert(self, partition):
        if isinstance(partition, Tiling):
            return Tiling(
                self._runtime,
                partition.tile_shape.drop(self._extra_dim),
                partition.color_shape.drop(self._extra_dim),
                partition.offset.drop(self._extra_dim),
            )
        else:
            raise ValueError(
                f"Unsupported partition: {type(partition).__name__}"
            )

    def get_inverse_transform(self, shape, parent_transform=None):
        parent_ndim = shape.ndim - 1
        result = AffineTransform(parent_ndim, shape.ndim, False)
        parent_dim = 0
        for child_dim in range(shape.ndim):
            if child_dim != self._extra_dim:
                result.trans[parent_dim, child_dim] = 1
                parent_dim += 1
        if parent_transform is not None:
            result = result.compose(parent_transform)
        return result

    def serialize(self, launcher):
        super(Promote, self).serialize(launcher)
        launcher.add_scalar_arg(self._extra_dim, ty.int32)
        launcher.add_scalar_arg(self._dim_size, ty.int64)


class Project(Transform):
    def __init__(self, runtime, dim, index):
        self._runtime = runtime
        self._dim = dim
        self._index = index

    def compute_shape(self, shape):
        return shape.drop(self._dim)

    def __str__(self):
        return f"Project(dim: {self._dim}, index: {self._index})"

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self._dim == other._dim and self._index == other._index

    def __hash__(self):
        return hash((type(self), self._dim, self._index))

    @property
    def invertible(self):
        return True

    def invert(self, partition):
        if isinstance(partition, Tiling):
            return Tiling(
                self._runtime,
                partition.tile_shape.insert(self._dim, 1),
                partition.color_shape.insert(self._dim, 1),
                partition.offset.insert(self._dim, self._index),
            )
        else:
            raise ValueError(
                f"Unsupported partition: {type(partition).__name__}"
            )

    def get_inverse_transform(self, shape, parent_transform=None):
        parent_ndim = shape.ndim + 1
        result = AffineTransform(parent_ndim, shape.ndim, False)
        result.offset[self._dim] = self._index
        child_dim = 0
        for parent_dim in range(parent_ndim):
            if parent_dim != self._dim:
                result.trans[parent_dim, child_dim] = 1
                child_dim += 1
        if parent_transform is not None:
            result = result.compose(parent_transform)
        return result

    def serialize(self, launcher):
        super(Project, self).serialize(launcher)
        launcher.add_scalar_arg(self._dim, ty.int32)
        launcher.add_scalar_arg(self._index, ty.int64)


class Transpose(Transform):
    def __init__(self, runtime, axes):
        self._runtime = runtime
        self._axes = axes
        self._inverse = tuple(np.argsort(self._axes))

    def compute_shape(self, shape):
        new_shape = Shape(tuple(shape[dim] for dim in self._axes))
        return new_shape

    def __str__(self):
        return f"Transpose(axes: {self._axes})"

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self._axes == other._axes

    def __hash__(self):
        return hash((type(self), tuple(self._axes)))

    @property
    def invertible(self):
        return True

    def invert(self, partition):
        if isinstance(partition, Tiling):
            return Tiling(
                self._runtime,
                partition.tile_shape.map(self._inverse),
                partition.color_shape.map(self._inverse),
                partition.offset.map(self._inverse),
            )
        else:
            raise ValueError(
                f"Unsupported partition: {type(partition).__name__}"
            )

    def get_inverse_transform(self, shape, parent_transform=None):
        result = AffineTransform(shape.ndim, shape.ndim, False)
        for dim in range(shape.ndim):
            result.trans[dim, self._axes[dim]] = 1
        if parent_transform is not None:
            result = result.compose(parent_transform)
        return result

    def serialize(self, launcher):
        super(Transpose, self).serialize(launcher)
        launcher.add_scalar_arg(self._axes, (ty.int32,))


class Delinearize(Transform):
    def __init__(self, runtime, dim, shape):
        self._runtime = runtime
        self._dim = dim
        self._shape = Shape(shape)
        self._strides = self._shape.strides()

    def compute_shape(self, shape):
        return shape.replace(self._dim, self._shape)

    def __str__(self):
        return f"Delinearize(dim: {self._dim}, shape: {self._shape})"

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self._dim == other._dim and self._shape == other._shape

    def __hash__(self):
        return hash((type(self), self._shape, self._strides))

    @property
    def invertible(self):
        return False

    def invert(self, partition):
        if isinstance(partition, Tiling):
            if (
                partition.color_shape[
                    self._dim : self._dim + self._shape.ndim
                ].volume()
                == 1
                and partition.offset[
                    self._dim : self._dim + self._shape.ndim
                ].sum()
                == 0
                and partition.tile_shape[
                    self._dim : self._dim + self._shape.ndim
                ]
                == self._shape
            ):
                tile_shape = partition.tile_shape
                color_shape = partition.color_shape
                offset = partition.offset
                for n in range(self._shape.ndim):
                    tile_shape = tile_shape.drop(self._dim)
                    color_shape = color_shape.drop(self._dim)
                    offset = offset.drop(self._dim)

                tile_shape = tile_shape.insert(self._dim, self._shape.volume())
                color_shape = color_shape.insert(self._dim, 1)
                offset = offset.insert(self._dim, 0)

                return Tiling(self._runtime, tile_shape, color_shape, offset)
            else:
                raise ValueError(f"Unsupported partition: {partition}")
        else:
            raise ValueError(
                f"Unsupported partition: {type(partition).__name__}"
            )

    def get_inverse_transform(self, shape, parent_transform=None):
        assert shape.ndim >= self._strides.ndim
        out_ndim = shape.ndim - self._strides.ndim + 1
        result = AffineTransform(out_ndim, shape.ndim, False)

        in_dim = 0
        for out_dim in range(out_ndim):
            if out_dim == self._dim:
                for dim, stride in enumerate(self._strides):
                    result.trans[out_dim, in_dim + dim] = stride
                in_dim += self._strides.ndim
            else:
                result.trans[out_dim, in_dim] = 1
                in_dim += 1

        if parent_transform is not None:
            result = result.compose(parent_transform)
        return result

    def serialize(self, launcher):
        super(Delinearize, self).serialize(launcher)
        launcher.add_scalar_arg(self._dim, ty.int32)
        launcher.add_scalar_arg(self._shape, (ty.int64,))