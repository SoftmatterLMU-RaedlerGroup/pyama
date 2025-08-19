import numpy as np

from .base import ModelBase
from .fitting import simple_fit
from .gene_expression_util import guess_t0
# from .gene_expression_util import shape_onset


# Default values for km and beta are taken from
# Table 1 of doi:10.1016/j.nano.2019.102077
t0_0 = 2
km_0 = 1.28
ktl_0 = 20  # 1000 # ktl depends on amplitude (init to ~30% of amplitude)
beta_0 = 5.22e-3
delta_0 = 0.01  # 0.2
offset_0 = 0

MAX_t0 = 30
MAX_ktl = 5e8
MAX_km = 30
MAX_beta = 10
MAX_delta = 11

MIN_ktl = 1


class MaturationModel(ModelBase):
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
            km=dict(
                values=[km_0],
                min=1e-5,
                max=MAX_km,
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
    
    @property
    def fit_properties(self):
        return {"max_nfev": 5000}  # Increase max function evaluations

    def eval(self, t, t0, ktl, km, delta, beta, offset=0):
        """General expression model function"""

        f = np.zeros(np.shape(t))
        idx_after = t > t0
        dt = t[idx_after] - t0

        bmd = beta - delta

        f1 = np.exp(-(beta + km) * dt) / (bmd + km)
        f2 = -np.exp(-beta * dt) / bmd
        f3 = km / bmd / (bmd + km) * np.exp(-delta * dt)

        f[idx_after] = (f1 + f2 + f3) * ktl

        return f + offset

    #    @property
    #    def jac_fun(self):
    #        return self.eval_jac
    #
    #
    #    def eval_jac(self, t, params):
    #        """Returns the Jacobi matrix of the expression model function
    #        with time along axis=0 and parameters along axis=1"""
    #
    #        # Find indices of parameters
    #        if len(params) == self.n_params:
    #            t0, ktl, km, delta, beta, offset = params
    #            i_t0, i_ktl, i_km, i_delta, i_beta, i_offset = range(self.n_params)
    #        else:
    #            it_params = iter(params)
    #            t0, ktl, km, delta, beta, offset = [
    #                    next(it_params) if is_free else val for is_free, val in zip(self.idx_free, self._value_template)]
    #            it_idx = iter(np.sum(self.idx_free))
    #            i_t0, i_ktl, i_km, i_delta, i_beta, i_offset = [
    #                    next(it_idx) if is_free else None for is_free in self.idx_free]
    #
    #        # Initialize Jacobian
    #        jac = np.zeros((t.size, len(params)))
    #
    #        # Get time after onset “kink”
    #        after_t0 = (t > t0)
    #
    #        # Define abbreviations for frequent terms
    #        dt = t[after_t0] - t0
    #        bmd = beta - delta
    #        kbd = km + bmd
    #        kpb = km + beta
    #
    #        exp_delta_dt = np.exp(-delta * dt)
    #        exp_beta_dt = np.exp(-beta * dt)

    #        # Derive w.r.t. t0
    #        if i_t0 is not None:
    #            jac[after_t0, i_t0] = ktl * (km * delta * exp_delta_dt / bmd / kbd
    #                                  - beta * exp_beta_dt / bmd
    #                                  + kpb * np.exp(-kpb * dt) / kbd)
    #
    #        # Derive w.r.t. ktl
    #        if i_ktl is not None:
    #            jac[after_t0, i_ktl] = (km * exp_delta_dt / bmd / kbd
    #                              + np.exp(-kpb * dt) / kbd
    #                              - exp_beta_dt / bmd)
    #
    #        # Derive w.r.t. km
    #        if i_km is not None:
    #            jac[after_t0, i_km] = ktl * (-km * exp_delta_dt / bmd / kbd**2
    #                                   - dt * np.exp(-kpb * dt) / kbd
    #                                   - np.exp(-kpb * dt) / kbd**2
    #                                   + exp_delta_dt / bmd / kbd)
    #
    #        # Derive w.r.t. delta
    #        if i_delta is not None:
    #            jac[after_t0, i_delta] = ktl * (-km * dt * exp_delta_dt / bmd / kbd
    #                                   + km * exp_delta_dt / bmd / kbd**2
    #                                   + km * exp_delta_dt / bmd**2 / kbd
    #                                   + np.exp(-kpb * dt) / kbd**2
    #                                   - exp_beta_dt / bmd**2)
    #
    #        # Derive w.r.t. beta
    #        if i_beta is not None:
    #            jac[after_t0, i_beta] = ktl * (-km * exp_delta_dt / bmd / kbd**2
    #                                   - km * exp_delta_dt / bmd**2 / kbd
    #                                   - dt * np.exp(-kpb * dt) / kbd
    #                                   + dt * exp_beta_dt / bmd
    #                                   - np.exp(-kpb * dt) / kbd**2
    #                                   + exp_beta_dt / bmd**2)
    #
    #        # Derive w.r.t. offset
    #        if i_offset is not None:
    #            jac[:, i_offset] = 1
    #
    #        return jac

    #    def fit(model, t, d, **init_params):
    # shaped = shape_onset(t, d)
    # if shaped is not None:
    #    t, d = shaped
    # import scipy.ndimage as scndi
    # d = scndi.gaussian_filter1d(d, 3)
    # d = d[:-50]
    # t = t[:-50]
    #        return simple_fit(model, t, d, **init_params)

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
        if "t0" in names:
            try:
                ip["t0"] = float(guess_t0(t, d))
            except:
                ip["t0"] = t0_0  # Use default if guess fails
        if "ktl" in names:
            amplitude = d.max() - d.min()
            if amplitude > 0:
                # Limit initial ktl to a reasonable range
                ip["ktl"] = min(amplitude * 0.3, 50000)
            else:
                ip["ktl"] = ktl_0  # Use default if data is flat
        if "km" in names:
            ip["km"] = km_0
        if "delta" in names:
            ip["delta"] = delta_0
        if "beta" in names:
            ip["beta"] = beta_0
        if "offset" in names:
            ip["offset"] = offset_0
        return ip
