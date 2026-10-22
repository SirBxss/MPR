"""Physical-unit, sample-based scores on identical rows and retained resets."""

import numpy as np

TAIL_THRESHOLDS_M = (0.5, 1.0, 2.0)


def evaluate_matched_samples(y, offsets, draws):
    y, draws = np.asarray(y), np.asarray(draws)
    offsets = np.asarray(offsets)
    if (y.ndim != 2 or y.shape[1] != 21 or not len(y) or draws.ndim != 3
            or draws.shape[1:] != y.shape or draws.shape[0] < 4 or draws.shape[0] % 2
            or not np.isfinite(y).all() or not np.isfinite(draws).all()
            or offsets.dtype.kind not in "iu" or offsets.ndim != 1 or len(offsets) < 2
            or offsets[0] != 0 or offsets[-1] != len(y) or np.any(np.diff(offsets) <= 0)):
        raise ValueError("matched_evaluation_shape_values_or_resets")
    mean = draws.mean(axis=0)
    error = mean-y
    half = len(draws)//2
    pair = draws[:half]-draws[half:]
    energy_by_frame = np.linalg.norm(draws-y,axis=2).mean(axis=0) - .5*np.linalg.norm(pair,axis=2).mean(axis=0)
    sequence_energy = []
    for a,b in zip(offsets[:-1],offsets[1:]):
        # Flatten only inside this exact retained sequence; never join a reset.
        first = np.linalg.norm((draws[:,a:b]-y[a:b]).reshape(len(draws),-1),axis=1).mean()
        second = np.linalg.norm(pair[:,a:b].reshape(half,-1),axis=1).mean()
        sequence_energy.append(float((first-.5*second)/np.sqrt((b-a)*21)))
    intervals = {}
    for level in (.5,.8,.95):
        low,high = np.quantile(draws,[(1-level)/2,(1+level)/2],axis=0)
        intervals[str(level)] = {"coverage":float(((low<=y)&(y<=high)).mean()),
            "mean_width_m":float((high-low).mean()),
            "station_coverage":((low<=y)&(y<=high)).mean(axis=0).tolist()}
    valid = np.ones(len(y)-1,dtype=bool)
    valid[offsets[1:-1]-1] = False
    left,right = np.flatnonzero(valid),np.flatnonzero(valid)+1
    def correlations(values):
        a,b = values[...,left,:],values[...,right,:]
        a,b = a-a.mean(axis=-2,keepdims=True),b-b.mean(axis=-2,keepdims=True)
        denominator = np.sqrt(np.square(a).sum(axis=-2)*np.square(b).sum(axis=-2))
        return np.divide((a*b).sum(axis=-2),denominator,out=np.full_like(denominator,np.nan),where=denominator>0)
    lag, lag_stations = None, 0
    if len(left) >= 2:
        observed, generated = correlations(y),correlations(draws)
        mask = np.isfinite(observed)&np.isfinite(generated).all(axis=0)
        lag_stations = int(mask.sum())
        if lag_stations:
            lag = float(np.median(np.abs(np.median(generated[:,mask],axis=0)-observed[mask])))
    tail = {}
    for threshold in TAIL_THRESHOLDS_M:
        event = (np.abs(y).max(axis=1)>threshold).astype(float)
        probability = (np.abs(draws).max(axis=2)>threshold).mean(axis=0)
        tail[str(threshold)] = {"observed_fraction":float(event.mean()), "predicted_fraction":float(probability.mean()),
            "brier_score":float(np.square(probability-event).mean())}
    return {"frame_count":len(y),"sequence_count":len(offsets)-1,"valid_transitions":len(left),
        "sample_mean_rmse_m":float(np.sqrt(np.square(error).mean())),
        "station_rmse_m":np.sqrt(np.square(error).mean(axis=0)).tolist(),"station_bias_m":error.mean(axis=0).tolist(),
        "mean_energy_score_m":float(energy_by_frame.mean()),
        "mean_normalized_sequence_energy_score_m":float(np.mean(sequence_energy)),
        "mean_marginal_crps_m":float(np.abs(draws-y).mean()-.5*np.abs(pair).mean()),
        "intervals":intervals,"profile_max_absolute_tail":tail,
        "median_absolute_lag_one_correlation_error":lag,"lag_valid_station_count":lag_stations,
        "lag_scope":"only_retained_adjacent_transitions_no_long_horizon_claim"}
