import numpy as np

from .base import ModelBase
from .fitting import simple_fit


t0_0 = 2
ktl_0 = 20
beta_0 = 0.0436275356035
delta_0 = 0.07
offset_0 = 0

MAX_t0 = 30
MAX_ktl = 5e4
MAX_beta = 10
MAX_delta = 10.1

MIN_ktl = 1


class TrivialModel(ModelBase):
    def __init__(self, *args, **kwargs):
        self.params = dict(
            t0=dict(
                values=[t0_0],
                min=None,
                max=MAX_t0,
                fixed=False,
            ),
            ktl=dict(
                values=[ktl_0],
                min=MIN_ktl,
                max=MAX_ktl,
                fixed=False,
            ),
            delta=dict(
                values=[delta_0],
                min=1e-5,
                max=MAX_delta,
                fixed=False,
            ),
            beta=dict(
                values=[beta_0],
                min=1e-5,
                max=MAX_beta,
                fixed=False,
            ),
            offset=dict(
                values=[offset_0],
                min=None,
                max=None,
                fixed=False,
            ),
        )

        super().__init__(*args, **kwargs)

    fit = simple_fit

    def eval(self, t, t0, ktl, delta, beta, offset=0):
        """General expression model function"""
        dt = t - t0
        dmb = delta - beta
        return offset + (ktl / dmb * (1 - np.exp(-dmb * dt)) * np.exp(-beta * dt)).clip(
            0
        )
