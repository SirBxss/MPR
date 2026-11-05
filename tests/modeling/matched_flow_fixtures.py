"""Artificial fold scale data for numerical screen regression, never BMW data."""
from types import SimpleNamespace

import numpy as np


def large_training_blocks(*, seed: int, innovation: str) -> list:
    """Six blocks, 8802 rows and short sequences with a maximum of 14 frames.

    Conditions are artificial Gaussian numbers, not physical vehicle features.
    Innovation scales grow across stations. Each exact sequence starts afresh;
    an AR coefficient of 0.8 supplies dependence only inside that sequence.
    """
    if innovation not in ("gaussian", "student_t5"):
        raise ValueError("synthetic_innovation_required")
    rng = np.random.default_rng(seed)
    cycle = (1, 1, 1, 1, 2, 2, 2, 3, 3, 4, 6, 8, 12, 14)
    offsets = [0]
    while offsets[-1] < 1467:
        length = min(cycle[(len(offsets)-1) % len(cycle)], 1467-offsets[-1])
        offsets.append(offsets[-1]+length)
    offsets = np.asarray(offsets, dtype=np.int64)
    scales = np.linspace(.15, .8, 21)
    blocks = []
    for i in range(6):
        x = rng.normal(size=(1467, 6))
        noise = (rng.normal(size=(1467, 21)) if innovation == "gaussian" else
                 rng.standard_t(5, size=(1467, 21))/np.sqrt(5/3))
        residual = noise.copy()
        for lo, hi in zip(offsets[:-1], offsets[1:]):
            for row in range(lo+1, hi):
                residual[row] = .8*residual[row-1]+.6*noise[row]
        y = (residual+.2*x[:, :1]+x[:, 1:2]*np.linspace(-.2, .2, 21))*scales
        blocks.append(SimpleNamespace(outing_id="synthetic_"+str(i), x=x, y=y, offsets=offsets.copy()))
    return blocks
