"""Gaussian baselines for the versioned matched-development experiment.

The conditional mean is minimum-norm OLS. Exact constant columns use scale one;
rank deficiency is recorded rather than fixed using held-out observations.
Existing historical model implementations and their artifacts are unchanged.
"""

from dataclasses import dataclass

import numpy as np

MODES = ("unconditional_gaussian", "conditional_gaussian")
REGULARIZATION = 1e-6  # diagonal covariance variance in training-standardized units


def matrix(value, width):
    value = np.asarray(value, dtype=np.float64)
    if value.ndim != 2 or value.shape[1] != width or not len(value) or not np.isfinite(value).all():
        raise ValueError("matched_gaussian_finite_matrix_required")
    return value


def scale(values):
    """No unit-dependent epsilon or held-out information enters this transform."""
    mean, deviation = values.mean(axis=0), values.std(axis=0)
    constant = np.all(values == values[:1], axis=0)
    mean[constant], deviation[constant] = values[0, constant], 1.0
    if not np.isfinite(mean).all() or not np.isfinite(deviation).all() or np.any(deviation <= 0):
        raise ValueError("matched_gaussian_unrepresentable_training_scale")
    return mean, deviation


@dataclass(frozen=True)
class MatchedGaussian:
    mode: str
    residual_mean: np.ndarray
    residual_scale: np.ndarray
    condition_mean: np.ndarray
    condition_scale: np.ndarray
    intercept: np.ndarray
    coefficients: np.ndarray
    covariance: np.ndarray
    training_rows: int
    design_rank: int

    def __post_init__(self):
        if self.mode not in MODES or type(self.training_rows) is not int or self.training_rows < 8:
            raise ValueError("matched_gaussian_model_identity")
        limit = 1 if self.mode == MODES[0] else 7
        if type(self.design_rank) is not int or not 1 <= self.design_rank <= limit:
            raise ValueError("matched_gaussian_design_rank")
        for name, shape in {"residual_mean":(21,), "residual_scale":(21,), "condition_mean":(6,),
                "condition_scale":(6,), "intercept":(21,), "coefficients":(6,21), "covariance":(21,21)}.items():
            a = np.asarray(getattr(self, name), dtype=np.float64).copy()
            if a.shape != shape or not np.isfinite(a).all():
                raise ValueError("matched_gaussian_parameter_shape_or_value")
            if name.endswith("scale") and np.any(a <= 0):
                raise ValueError("matched_gaussian_positive_scale_required")
            a.setflags(write=False)
            object.__setattr__(self, name, a)
        if not np.allclose(self.covariance, self.covariance.T, rtol=1e-12, atol=1e-14):
            raise ValueError("matched_gaussian_covariance_not_symmetric")
        np.linalg.cholesky(self.covariance)
        if self.mode == MODES[0] and (np.any(self.coefficients) or np.any(self.condition_mean)
                                    or not np.array_equal(self.condition_scale, np.ones(6))):
            raise ValueError("matched_unconditional_model_uses_conditions")

    def mean_standardized(self, features):
        x = matrix(features, 6)
        if self.mode == MODES[0]:
            return np.broadcast_to(self.intercept, (len(x), 21))
        return self.intercept + ((x-self.condition_mean)/self.condition_scale) @ self.coefficients

    def predict_mean(self, features):
        return self.mean_standardized(features) * self.residual_scale + self.residual_mean

    def logpdf(self, features, residuals):
        y = matrix(residuals, 21)
        mean = self.mean_standardized(features)
        if mean.shape != y.shape:
            raise ValueError("matched_gaussian_row_alignment")
        cholesky = np.linalg.cholesky(self.covariance)
        error = (y-self.residual_mean)/self.residual_scale - mean
        whitened = np.linalg.solve(cholesky, error.T).T
        logdet = 2*np.log(np.diag(cholesky)).sum()
        # The density is in physical metre coordinates, including the Jacobian.
        return -.5*(21*np.log(2*np.pi)+logdet+np.square(whitened).sum(axis=1)) - np.log(self.residual_scale).sum()

    def sample(self, features, *, sample_count, seed):
        if type(sample_count) is not int or sample_count < 4 or type(seed) is not int or seed < 0:
            raise ValueError("matched_gaussian_sampling_parameters")
        mean = self.mean_standardized(features)
        noise = np.random.default_rng(seed).standard_normal((sample_count, len(mean), 21))
        draws = mean + noise @ np.linalg.cholesky(self.covariance).T
        result = draws*self.residual_scale+self.residual_mean
        if not np.isfinite(result).all():
            raise ValueError("matched_gaussian_nonfinite_samples")
        return result

    def to_dict(self):
        return {"mode":self.mode, "training_rows":self.training_rows, "design_rank":self.design_rank,
                **{name:getattr(self,name).tolist() for name in ("residual_mean","residual_scale","condition_mean",
                    "condition_scale","intercept","coefficients","covariance")}}

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("matched_gaussian_state_fields")
        return cls(**value)


def fit_matched_gaussian(y, x, *, mode):
    """Caller supplies only the explicitly admitted fold's training rows."""
    y, x = matrix(y, 21), matrix(x, 6)
    if mode not in MODES or len(y) != len(x) or len(y) < 8:
        raise ValueError("matched_gaussian_training_contract")
    ym, ys = scale(y)
    z = (y-ym)/ys
    if mode == MODES[1]:
        xm, xs = scale(x)
        design = np.column_stack((np.ones(len(x)), (x-xm)/xs))
        parameters, _, rank, _ = np.linalg.lstsq(design, z, rcond=None)
        intercept, coefficients = parameters[0], parameters[1:]
    else:
        xm, xs = np.zeros(6), np.ones(6)
        intercept, coefficients, rank = z.mean(axis=0), np.zeros((6,21)), 1
    prediction = intercept + ((x-xm)/xs) @ coefficients if mode == MODES[1] else intercept
    errors = z-prediction
    covariance = errors.T @ errors / len(errors) + REGULARIZATION*np.eye(21)
    return MatchedGaussian(mode, ym, ys, xm, xs, intercept, coefficients, covariance, len(y), int(rank))
