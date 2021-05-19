from collections import namedtuple, OrderedDict
from threading import Lock

from . import const
from ..util.listener import Listeners


class Shape:
    """Manage the shape of a stack or channel.

    The following dimensions are supported:
    T (time), Z (slice, not implemented), C (channel),
    Y (pixel rows), X (pixel columns).

    The dimensions must have the order [TZC]YX, wherein [TZC] may
    be any permutation of these three dimensions.
    Z may have size None (default), which means that it is not present.
    All other dimensions must have non-negative integer sizes.

    Arguments:
        shape -- dict-like object with dimension names (see above) as keys
                 and the corresponding dimension sizes as values.
        reshapable_dims -- tuple of dimension names or None,
                 dimensions that can be reshaped after initialization.
    """
    def __init__(self, shape, reshapable_dims=(const.C,)):
        self.lock = Lock()
        self._listeners = Listeners(kinds=(const.EVT_RESHAPE,))
        self._reshapable_dims = set()
        if reshapable_dims:
            self._reshapable_dims.update(reshapable_dims)

        self._shape_dict = self.make_shape_dict(shape)


    @staticmethod
    def make_shape_dict(shape):
        """Create a valid shape dictionary.

        `shape` is a dict-like object with dimension letters as keys
        and dimension sizes as values. 

        If `shape` is invalid, an exception is raised.
        Else, an OrderedDict of a valid shape is returned, with dimension letters
        as keys and non-negative integer dimension sizes as values.

        The dimensions TCYX are required. The Z dimension is optional;
        if the Z dimension is not present, it may be omitted or its size set to None.
        The dimensions TCZ are returned in the order as they appear in `shape`;
        if Z is not provided, it is appended with a size of None.
        The dimensions YX are always returned as last dimensions in this order.
        """
        stack_dims = set(const.STACK_DIM)
        input_dims = list(shape.keys())
        sd = OrderedDict()

        for dim, val in shape.items():
            try:
                stack_dims.remove(dim)
            except KeyError:
                continue
            sd[dim] = Shape._validate_dim_size(dim, val)

        try:
            stack_dims.remove(const.Z)
        except KeyError:
            pass
        else:
            sd[const.Z] = None

        if stack_dims:
            dims = "".join(d for d in stack_dims)
            raise ValueError(f"Undefined stack dimensions: {dims}")

        for dim in (const.Y, const.X):
            try:
                sd[dim] = Shape._validate_dim_size(dim, shape[dim])
            except KeyError:
                raise ValueError(f"Missing size for required dimension '{dim}'") from None
            except (ValueError, TypeError):
                raise ValueError(f"Invalid size for dimension '{dim}': {shape[dim]}") from None
        return sd


    @staticmethod
    def _validate_dim_size(dim, size):
        is_valid = True
        try:
            size = int(size)
            if size < 0:
                is_valid = False
        except (ValueError, TypeError):
            if dim != const.Z or size is not None:
                is_valid = False
        if not is_valid:
            raise ValueError(f"The dimension size must be a non-negative integer (or None for Z).") from None
        return size


    @staticmethod
    def _validate_dim_name(*dim, do_raise=True):
        invalid_dims = set(dim).difference(const.ALL_DIM)
        if invalid_dims and do_raise:
            names = "', '".join(d in invalid_dims)
            raise ValueError(f"Invalid dimension names given: '{names}'")
        return invalid_dims

            
    @property
    def reshapable_dims(self):
        """Get a set of the dimensions that can be reshaped"""
        with self.lock:
            return self._reshapable_dims.copy()


    def make_reshapable(self, *dims):
        """Allow reshaping for the given dimensions"""
        self._validate_dim_name(*dims)
        with self.lock:
            self._reshapable_dims.update(dims)


    def make_fixed(self, *dims):
        """Disable reshaping for the given dimensions"""
        with self.lock:
            if dims:
                self._reshapable_dims.difference_update(dims)
            else:
                self._reshapable_dims.clear()


    @property
    def shape(self):
        with self.lock:
            return self._shape_dict.copy()


    def __str__(self):
        return f"""{self.__class__.__name__}({", ".join(f"{k}={'None' if v is None else str(int(v))}" for k, v in self.shape.items())})"""


    def reshape(self, **dims):
        """Reshape the given dimensions.

        `dims` has the reshaped dimension names as keys
        and the new dimension sizes as values.
        """
        self._validate_dim_name(*dims.keys())
        changed_dims = {}
        with self.lock:
            fixed_dims = set(dims.keys()).difference(self._reshapable_dims)
            if fixed_dims:
                names = "', '".join(d for d in fixed_dims)
                raise ValueError(f"Reshaping is disabled for dimension '{names}'")
            for dim, val in dims.items():
                old_val = self._shape_dict[dim]
                val = self._validate_dim_size(dim, val)
                self._shape_dict[dim] = val
                changed_dims[dim] = dict(old=old_val, new=val)
            if changed_dims:
                self.notify_listeners(changed_dims)


    def notify_listeners(self, changed_dims):
        """Notify listeners about reshape"""
        self._listeners.notify(const.EVT_RESHAPE, changed_dims)

    def register_listener(self, fun, queue=None):
        """Register a new reshape listener"""
        return self._listeners.register(fun, kind=const.EVT_RESHAPE, queue=queue)

    def delete_listener(self, lid):
        """Delege a reshape listener"""
        self._listeners.delete(lid)
