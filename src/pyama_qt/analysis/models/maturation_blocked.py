import numpy as np

from .base import ModelBase
from .fitting import simple_fit


# Default values for km and beta are taken from
# Table 1 of doi:10.1016/j.nano.2019.102077
km_0 = 1.28
beta_0 = 5.22e-3

MAX_km = 30
MAX_beta = 10


class MaturationBlockedModel(ModelBase):
    def __init__(self, *args, t0=None, **kwargs):
        if t0 is None:
            print(
                "'t0' is not defined. Using whole time series for fitting. "
                "Specify 't0' using the '-x' parameter, e.g.: '-x t0 1.0'. "
                "When specifying 't0', it must be given in units of hours."
            )
            self.t0 = None
        else:
            self.t0 = float(t0)

        self.params = dict(
            G0=dict(
                values=[],
                min=0,
                max=None,
                fixed=False,
            ),
            Gu0=dict(
                values=[],
                min=0,
                max=None,
                fixed=False,
            ),
            km=dict(
                values=[km_0],
                min=1e-5,
                max=MAX_km,
                fixed=False,
            ),
            beta=dict(
                values=[beta_0],
                min=1e-5,
                max=MAX_beta,
                fixed=False,
            ),
        )

        super().__init__(*args, **kwargs)

    def eval(self, t, G0, Gu0, km, beta, **kwargs):
        """General expression model function"""
        if self.t0 is not None:
            idx = t >= self.t0
            t = t.copy()
            t[idx] -= self.t0
            t[np.logical_not(idx)] = np.NaN
        return G0 * np.exp(-beta * t) + Gu0 * (
            np.exp(-beta * t) - np.exp(-(beta + km) * t)
        )

    def fit(self, t, d, **init_params):
        if self.t0 is not None:
            idx = t >= self.t0
            t = t[idx]
            d = d[idx]
        return simple_fit(self, t, d, **init_params)

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
        ip = {}
        if "G0" in names:
            ip["G0"] = max(0, d[0])
        if "Gu0" in names:
            i_max = np.argmax(d)
            ip["Gu0"] = max(0, (d[i_max] - d[0]) / (t[i_max] - t[0]) / km_0)
        if "km" in names:
            ip["km"] = km_0
        if "beta" in names:
            ip["beta"] = beta_0
        return ip
