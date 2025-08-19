import numpy as np
import numpy.linalg as nplin
import scipy.optimize as sco


def make_obj_fun(t, d, model):
    eval_fun = model.eval_fit

    def obj_fun(p, *args, **kwargs):
        nonlocal t, d, eval_fun
        return d - eval_fun(t, *p)

    return obj_fun


def make_jac_fun(t, d, model):
    eval_fun = model.eval_fit
    jac_fun = model.jac_fun

    def fit_jac(p, *args, **kwargs):
        nonlocal t, d, eval_fun, jac_fun
        return (d - eval_fun(t, *p)).reshape((-1, 1)) * jac_fun(t, p) * 2

    return fit_jac


def simple_fit(model, t, d, **init_params):
    init_par = model.make_init_par(t, d, **init_params)
    fit_opt = {}
    if model.jac_fun:
        fit_opt["jac"] = make_jac_fun(t, d, model)
    res = sco.least_squares(
        make_obj_fun(t, d, model),
        init_par,
        bounds=model.get_bounds(),
        **fit_opt,
        **model.fit_properties,
    )

    var = np.sum(res.fun**2) / (res.fun.size - 1)
    try:
        cov = nplin.inv(res.jac.T @ res.jac)
    except Exception:
        cov = None

    return dict(
        params=res.x,
        vals=model.eval_fit(t, *res.x),
        residuals=res.fun,
        std=np.sqrt(var / res.fun.size),
        chisq=np.sum(res.fun**2),
        cov=cov,
        success=res.success,
        message=res.message,
        t_fit=t,
    )
