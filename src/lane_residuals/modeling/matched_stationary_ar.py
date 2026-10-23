"""A stationary scalar AR(1) control with an immutable Gaussian marginal.

This is a new matched memory control, not the historical station-wise AIOHMM.
For e_t = standardized_y_t - frozen_mean(x_t), reset e_0 ~ N(0,Sigma),
and e_t = phi*e_{t-1} + sqrt(1-phi**2)*L*noise. Thus every frame retains
the accepted conditional Gaussian marginal, for any supplied feature sequence.
Only phi is fitted, using the training set's retained adjacent transitions.
"""

from dataclasses import dataclass
import math

import numpy as np

from .matched_gaussian import MatchedGaussian, matrix

MODEL_NAME = "matched_stationary_scalar_ar1"
MAXIMUM_ABSOLUTE_PHI = 0.99
REVISION = "v0.19.17-stationary-scalar-ar1-2026-10-23-a1"


def offsets_for(offsets, rows):
    value = np.asarray(offsets)
    if (value.ndim != 1 or value.dtype.kind not in "iu" or len(value) < 2
            or value[0] != 0 or value[-1] != rows or np.any(value[1:] <= value[:-1])):
        raise ValueError("stationary_ar_exact_offsets_required")
    return value.astype(np.int64, copy=False)


def transition_indices(offsets, rows):
    offsets = offsets_for(offsets, rows)
    right = np.ones(rows, dtype=bool)
    right[offsets[:-1]] = False
    return np.flatnonzero(right)


def objective(phi, statistics):
    """Conditional transition NLL, omitting phi-independent physical constants."""
    xx, yy, xy, df = statistics
    v = 1.0 - phi*phi
    return 0.5*(df*np.log(v)+(yy-2*phi*xy+phi*phi*xx)/v)


@dataclass(frozen=True)
class StationaryAR:
    base: MatchedGaussian
    phi: float
    training_transitions: int
    sufficient_statistics: tuple

    def __post_init__(self):
        if (not isinstance(self.base, MatchedGaussian) or self.base.mode != "conditional_gaussian"
                or type(self.phi) not in (int,float) or not math.isfinite(self.phi)
                or abs(self.phi) > MAXIMUM_ABSOLUTE_PHI or type(self.training_transitions) is not int
                or not 1 <= self.training_transitions < self.base.training_rows):
            raise ValueError("stationary_ar_state_identity")
        s = tuple(self.sufficient_statistics)
        if (len(s) != 4 or any(type(v) not in (float,int) or not math.isfinite(v) for v in s)
                or min(s[:2]) < 0 or s[0]+s[1] <= 0 or s[3] != self.training_transitions*21
                or abs(s[2]) > np.sqrt(s[0])*np.sqrt(s[1])*(1+1e-12)):
            raise ValueError("stationary_ar_statistics")
        object.__setattr__(self, "sufficient_statistics", s)

    def sample(self, features, offsets, *, sample_count, seed):
        features = matrix(features, 6)
        offsets = offsets_for(offsets, len(features))
        if self.phi == 0:
            return self.base.sample(features, sample_count=sample_count, seed=seed)
        if type(sample_count) is not int or sample_count < 4 or type(seed) is not int or seed < 0:
            raise ValueError("stationary_ar_sampling_parameters")
        noise = np.random.default_rng(seed).standard_normal((sample_count,len(features),21))
        innovation = noise @ np.linalg.cholesky(self.base.covariance).T
        deviations = np.empty_like(innovation)
        factor = np.sqrt(1-self.phi*self.phi)
        for a,b in zip(offsets[:-1],offsets[1:]):
            deviations[:,a] = innovation[:,a]
            for t in range(a+1,b):
                deviations[:,t] = self.phi*deviations[:,t-1]+factor*innovation[:,t]
        result = ((self.base.mean_standardized(features)+deviations)*self.base.residual_scale
                  +self.base.residual_mean)
        if not np.isfinite(result).all():
            raise ValueError("stationary_ar_nonfinite_samples")
        return result

    def logpdf_observed_history(self, features, residuals, offsets):
        """Offline chain density; observed past pseudo-residuals are not online inputs."""
        y = matrix(residuals,21)
        x = matrix(features,6)
        if len(y) != len(x):
            raise ValueError("stationary_ar_row_alignment")
        offsets = offsets_for(offsets,len(y))
        if self.phi == 0:
            return self.base.logpdf(x,y)
        e = (y-self.base.residual_mean)/self.base.residual_scale-self.base.mean_standardized(x)
        right = transition_indices(offsets,len(y))
        errors = e.copy()
        errors[right] -= self.phi*e[right-1]
        variance = np.ones(len(y))
        variance[right] = 1-self.phi*self.phi
        whitened = np.linalg.solve(np.linalg.cholesky(self.base.covariance),errors.T).T
        logdet = np.linalg.slogdet(self.base.covariance)[1]
        return (-.5*(21*np.log(2*np.pi)+logdet+21*np.log(variance)
                     +np.square(whitened).sum(axis=1)/variance)
                -np.log(self.base.residual_scale).sum())

    def to_dict(self):
        return {"contract_revision":REVISION,"model":MODEL_NAME,"base":self.base.to_dict(),
                "phi":self.phi,"maximum_absolute_phi":MAXIMUM_ABSOLUTE_PHI,
                "training_transitions":self.training_transitions,
                "sufficient_statistics":list(self.sufficient_statistics)}

    @classmethod
    def from_dict(cls,value):
        fields = {"contract_revision","model","base","phi","maximum_absolute_phi",
                  "training_transitions","sufficient_statistics"}
        if (type(value) is not dict or set(value) != fields or value["contract_revision"] != REVISION
                or value["model"] != MODEL_NAME or type(value["maximum_absolute_phi"]) not in (int,float)
                or value["maximum_absolute_phi"] != MAXIMUM_ABSOLUTE_PHI):
            raise ValueError("stationary_ar_closed_state_schema")
        return cls(MatchedGaussian.from_dict(value["base"]),value["phi"],
                   value["training_transitions"],tuple(value["sufficient_statistics"]))


def fit_stationary_ar(base, training_blocks):
    """Minimize one bounded transition likelihood; never refit the base Gaussian.

The derivative numerator is df*p^3 - xy*p^2 + (xx+yy-df)*p - xy.
Evaluate every real stationary root and both fixed endpoints, plus p=0.
The cap is inherited prospectively from the earlier development freeze,
not selected from any result on the current held-out outings.
"""
    if not isinstance(base,MatchedGaussian) or base.mode != "conditional_gaussian":
        raise ValueError("stationary_ar_conditional_base_required")
    cholesky = np.linalg.cholesky(base.covariance)
    xx,yy,xy,transitions,rows = 0.0,0.0,0.0,0,0
    for residuals,features,offsets in training_blocks:
        y,x = matrix(residuals,21),matrix(features,6)
        if len(y) != len(x):
            raise ValueError("stationary_ar_row_alignment")
        right = transition_indices(offsets,len(y))
        e = (y-base.residual_mean)/base.residual_scale-base.mean_standardized(x)
        whitened = np.linalg.solve(cholesky,e.T).T
        a,b = whitened[right-1],whitened[right]
        xx += float(np.square(a).sum()); yy += float(np.square(b).sum())
        xy += float((a*b).sum()); transitions += len(right); rows += len(y)
    if rows != base.training_rows or transitions < 1 or not np.isfinite([xx,yy,xy]).all() or xx+yy <= 0:
        raise ValueError("stationary_ar_identifiable_training_pairs_required")
    statistics = (xx,yy,xy,transitions*21)
    coefficients = np.array([transitions*21,-xy,xx+yy-transitions*21,-xy],dtype=float)
    roots = np.roots(coefficients/np.max(np.abs(coefficients)))
    candidates = [-MAXIMUM_ABSOLUTE_PHI,0.0,MAXIMUM_ABSOLUTE_PHI]
    candidates += [float(r.real) for r in roots if abs(r.imag) <= 1e-10
                   and abs(r.real) <= MAXIMUM_ABSOLUTE_PHI]
    phi = min(candidates,key=lambda p:(objective(p,statistics),abs(p),-p))
    return StationaryAR(base,float(phi),transitions,statistics)
