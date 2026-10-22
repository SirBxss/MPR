"""Hash-pinned synthetic flow state; no real-data fitting or pickle loading."""

from dataclasses import fields
import hashlib
from pathlib import Path

from ..modeling.flow_matching import SyntheticFlowModel
from .development_experiment import encoded, metadata_path, pinned_json

REVISION = "v0.19.16-synthetic-flow-state-2026-10-22-a1"
MAXIMUM_BYTES = 8*1024**2


def save_synthetic_flow(model, destination):
    if type(model) is not SyntheticFlowModel:
        raise ValueError("synthetic_flow_model_type_required")
    payload = {f.name:(getattr(model,f.name).tolist() if hasattr(getattr(model,f.name),"tolist") else
                         list(getattr(model,f.name)) if f.name == "training_losses" else getattr(model,f.name))
               for f in fields(model)}
    raw = encoded({"contract_revision":REVISION,"scope":"synthetic_only","real_fit_authorized":False,"model":payload})
    if len(raw) > MAXIMUM_BYTES:
        raise ValueError("synthetic_flow_state_size_limit")
    destination = metadata_path(destination)
    if destination.suffix != ".json":
        raise ValueError("synthetic_flow_json_path_required")
    with destination.open("xb") as stream:
        stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def load_synthetic_flow(path, expected_sha256):
    path = metadata_path(path)
    if path.stat().st_size > MAXIMUM_BYTES:
        raise ValueError("synthetic_flow_state_size_limit")
    value,_ = pinned_json(path,expected_sha256)
    if (type(value) is not dict or set(value) != {"contract_revision","scope","real_fit_authorized","model"}
            or value["contract_revision"] != REVISION or value["scope"] != "synthetic_only"
            or value["real_fit_authorized"] is not False or type(value["model"]) is not dict
            or set(value["model"]) != {f.name for f in fields(SyntheticFlowModel)}):
        raise ValueError("synthetic_flow_state_scope_or_schema")
    return SyntheticFlowModel(**value["model"])
