"""Batched synthetic flow sampling with unchanged indexed noise and reset rules.

The original SyntheticFlowModel.sample remains the reference. Batching changes
floating-point reduction order, so multirow batches promise numerical agreement,
not bitwise equality. No real-data fit or model admission is introduced.
"""

import numpy as np

from ..domain.flow_matching import integrate_euler
from .flow_matching import SyntheticFlowModel


def sample_synthetic_flow_batched(model, conditions, lengths, *, sample_count, seed, steps=32, batch_rows=4096):
    if type(model) is not SyntheticFlowModel:
        raise ValueError("synthetic_flow_model_required")
    x, lengths = np.asarray(conditions,dtype=np.float64),np.asarray(lengths)
    if (x.ndim != 3 or x.shape[0] < 1 or x.shape[1] < 1 or x.shape[2] != 6 or not np.isfinite(x).all()
            or lengths.dtype.kind not in "iu" or lengths.shape != (len(x),)
            or np.any(lengths<1) or np.any(lengths>x.shape[1])
            or any(type(v) is not int or v < 1 for v in (sample_count,steps,batch_rows))
            or type(seed) is not int or seed < 0):
        raise ValueError("synthetic_flow_batch_sampling_contract")
    b,frames,_ = x.shape
    noise = np.random.default_rng(seed).standard_normal((sample_count,b,frames,21))
    values = np.zeros_like(noise)
    previous = np.zeros((sample_count,b,21))
    # Each frame's generated state is complete before advancing to the next.
    # Draw/sequence identities match the reference's indexed noise exactly.
    for frame in range(int(lengths.max())):
        active = np.flatnonzero(np.tile(lengths>frame,sample_count))
        for lo in range(0,len(active),batch_rows):
            selected = active[lo:lo+batch_rows]
            draw_index,sequence_index = np.divmod(selected,b)
            z = noise[draw_index,sequence_index,frame]
            features = x[sequence_index,frame]
            history = previous[draw_index,sequence_index]
            starts = np.full(len(selected),frame == 0,dtype=bool)
            def field(latent,time,_features,_history):
                return model.velocity(latent,time,features,history,starts)
            generated = integrate_euler(field,z,features,history,steps)*model.residual_scale+model.residual_mean
            previous[draw_index,sequence_index] = generated
            values[draw_index,sequence_index,frame] = generated
    if not np.isfinite(values).all():
        raise ValueError("synthetic_flow_batch_nonfinite_samples")
    return values
