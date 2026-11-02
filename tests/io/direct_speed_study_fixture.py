"""Small real synthetic MCAPs with a synthetic native-experiment boundary."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from lane_residuals.domain.direct_speed_study import REVISION
from lane_residuals.io import direct_speed_study as study
from lane_residuals.io.recording_inventory import read_inventory
from tests.io.velocity_timing_fixture import recording, row


def fixture(base):
    import numpy as np
    base = Path(base)
    objects, blocks, records, outings = {},[],[],[]
    def store(value):
        raw = json.dumps(value).encode()
        pin = hashlib.sha256(raw).hexdigest();objects[pin] = raw
        return pin
    for i,compression in enumerate(("NONE","ZSTD","LZ4")):
        outing,identifier = f"synthetic_{i}",f"recording_{i}"
        payload = recording(compression)
        raw = base/(identifier+".mcap");raw.write_bytes(payload)
        pin = hashlib.sha256(payload).hexdigest()
        inventory = {"purpose":"development_only_recording_inventory","recordings":[{"recording_id":identifier,
            "raw_sha256":pin,"size_bytes":len(payload),"status":"complete","inventory":read_inventory(BytesIO(payload),len(payload))}]}
        inv_pin = store(inventory)
        rows = [dict(row(j),recording_id=identifier) for j in range(125)]
        for j,r in enumerate(rows):
            r["speed_bracket_evidence"] = {"current_lower_timestamp_ns_decimal_private":r["estimate_source_time_ns_decimal_private"],
                "current_upper_timestamp_ns_decimal_private":r["estimate_source_time_ns_decimal_private"]}
            if j % 3 == 1:
                r["conditions_available"] = False;r["condition_failure_codes"] = ["speed_uses_future_source_sample"]
                r["speed_bracket_evidence"] = {"current_lower_timestamp_ns_decimal_private":str(int(r["estimate_source_time_ns_decimal_private"])-10_000_000),
                    "current_upper_timestamp_ns_decimal_private":str(int(r["estimate_source_time_ns_decimal_private"])+40_000_000)}
        audit_pin = store({"rows":rows})
        summary_pin = store({"preserved_inventory_report_sha256":inv_pin,"artifacts_sha256":{"candidate_audit.json":audit_pin,"residuals.npz":"f"*64}})
        selected = np.array([j for j,r in enumerate(rows) if r["conditions_available"]])
        arrays = {"candidate_index":np.arange(125),"recording_id":np.array([identifier]*125),
            "conditioned_profile_indices":selected,"conditions":np.full((len(selected),6),10.),
            "residuals_m":np.tile(np.arange(125,dtype=float)[:,None],(1,21))/100,
            "stations_m":np.arange(21)*5.}
        archive = SimpleNamespace(summary_sha256=summary_pin,raw_sha256_by_recording={identifier:pin},arrays=arrays)
        blocks.append(SimpleNamespace(outing_id=outing,archive=archive))
        records.append({"raw_sha256":pin,"size_bytes":len(payload),"canonical_paths_private":[str(raw)]})
        outings.append({"outing_id":outing,"cohort_role":"development","raw_sha256":[pin]})
    context = SimpleNamespace(objects=objects,metadata={"records":records},cohort={"outings":outings},cohort_sha256="c"*64,registry_sha256="d"*64)
    inputs = SimpleNamespace(context=context,blocks=tuple(blocks),watched={},file_sets={},unchanged=Mock())
    request = {"revision":REVISION,"experiment_directory":"original_experiment","experiment_sha256":"a"*64,
        "previously_examined_outing_id":"synthetic_0","cases":study.fixed_cases(inputs,"synthetic_0")}
    folder = base/"inputs";folder.mkdir()
    path = folder/"request.private.json"
    data = json.dumps(request).encode();path.write_bytes(data)
    return inputs,request,path,hashlib.sha256(data).hexdigest()
