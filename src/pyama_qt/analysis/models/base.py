from collections import OrderedDict
import numpy as np


class ModelBase:
    def __init__(self, parameters, limits=None, fixed=None, n_starts=1):
        self.n_starts = n_starts

        # self.params = {}
        # for name, values in parameters.items():
        #   val = tuple(values)
        #   self.params[name] = {
        #           'values': val,
        #           'min': None,
        #           'max': None,
        #           'fixed': False,
        #       }
        for name, values in parameters.items():
            if name in self.params and values:
                val = np.ravel(values)
                self.params[name]["values"] = val
                if val.size > self.n_starts:
                    self.n_starts = val.size
            elif name not in self.params:
                raise KeyError(f"Parameter '{name}' not defined for this model.")

        if limits:
            for name, (limit_min, limit_max) in limits.items():
                if limit_min is not None:
                    if limit_min == -np.inf:
                        limit_min = -np.inf
                    self.params[name]["min"] = limit_min
                if limit_max is not None:
                    if limit_max == np.inf:
                        limit_max = np.inf
                    self.params[name]["max"] = limit_max

        self._value_template = np.empty(self.n_params)
        self.idx_free = np.ones(self.n_params, dtype=np.bool_)
        if fixed:
            for name in fixed:
                self.params[name]["fixed"] = True
            for i, p in enumerate(self.params.values()):
                if p["fixed"]:
                    self._value_template[i] = p["values"][0]
                    self.idx_free[i] = False
        self.has_fixed = not np.all(self.idx_free)

    @property
    def n_params(self):
        return len(self.params)

    @property
    def fit_properties(self):
        return {}

    @property
    def jac_fun(self):
        return None

    def get_params(self, *params):
        """Return parameters.

        If `params` are not given, return tuple of all parameter names.
        Else, `params` is a list of values for the free parameters, and
        an array of values for all parameters is returned.
        """
        if not params:
            return tuple(self.params.keys())
        else:
            values = self._value_template.copy()
            values[self.idx_free] = params
            return values

    def get_bounds(self, include_fixed=False):
        min_vec = []
        max_vec = []
        for p in self.params.values():
            if p["fixed"] and not include_fixed:
                continue
            min_val = p["min"]
            if min_val is not None:
                min_vec.append(min_val)
            else:
                min_vec.append(-np.inf)

            max_val = p["max"]
            if max_val is not None:
                max_vec.append(max_val)
            else:
                max_vec.append(np.inf)
        return min_vec, max_vec

    def eval_fit(self, t, *params, **kwargs):
        """Evaluation method for fitting"""
        if self.has_fixed:
            return self.eval_fixed(t, *params, **kwargs)
        else:
            return self.eval(t, *params, **kwargs)

    def eval(self, t, *params, **kwargs):
        raise NotImplementedError

    def eval_fixed(self, t, *params, **kwargs):
        return self.eval(t, *self.get_params(*params), **kwargs)

    def fit(self, t, d, **init_params):
        raise NotImplementedError

    def init_named_par(self, t, d, *names, **init_params):
        """Model-specific parameter initialization.

        Arguements:
            t -- time-vector
            d -- data vector to be fitted
            names -- iterable of parameters to be initialized
            init_params -- dict of names and values of parameters that
                           are initialzed already

        Should return a dict of names and values for all parameters
        listed in `names`.
        """
        raise NotImplementedError

    def make_init_par(self, t, d, **init_params):
        """Data-dependent estimation of initial values.

        Additional parameter values may be given by `params`.
        If possible, the values from `params` should be respected.
        Should return a vector of non-fixed parameter values.
        """
        parameters = OrderedDict(
            (name, None)
            for is_free, name in zip(self.idx_free, self.get_params())
            if is_free
        )
        for name, value in init_params.items():
            if name in parameters:
                parameters[name] = value
            else:
                raise ValueError(f"Unknown parameter '{name}'")
        for name, value in parameters.items():
            if value is None and self.params[name]["values"]:
                parameters[name] = self.params[name]["values"][0]
        names_missing = tuple(
            name for name, value in parameters.items() if value is None
        )
        if names_missing:
            values = {name: val for name, val in parameters.items() if val is not None}
            try:
                init_spec = self.init_named_par(t, d, *names_missing, **values)
            except NotImplementedError:
                pass
            else:
                for name, value in init_spec.items():
                    if name in parameters:
                        parameters[name] = value
            if None in parameters.values():
                names_missing = (
                    name for name, val in parameters.items() if val is None
                )
                raise ValueError(
                    f"No start values found for parameters '{', '.join(names_missing)}'"
                )
        return np.array(tuple(parameters.values()))
