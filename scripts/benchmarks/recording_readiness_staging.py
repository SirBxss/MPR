"""Maximum-budget synthetic SQLite/matcher/feature staging under 4 GiB.

This measures staging, sort/index and all candidate scalar rows, not Protobuf
conversion or compressed MCAP performance. It never reads a raw recording.
"""

from __future__ import annotations

import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import argparse
import json
from pathlib import Path
import resource
import sys
import time
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))

from lane_residuals.domain.pairing import EgoRelativePath
from lane_residuals.io.bounded_recording_readiness import ScientificSink
from lane_residuals.io.exploratory_residuals import _time_key
from lane_residuals.io.recording_decode_check import _snapshot
from lane_residuals.io.recording_pair_feasibility import _pack_path
from lane_residuals.io.recording_readiness_resources import Observations, Workspace, scientific_failure
from lane_residuals.workflows.bounded_recording_readiness import _resources
import numpy as np


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-directory",type=Path,required=True)
    parser.add_argument("--output-report",type=Path,required=True)
    args=parser.parse_args()
    if args.output_report.exists():raise ValueError("new output report required")
    previous=resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS,(min(4*1024**3,previous[0]) if previous[0]!=resource.RLIM_INFINITY else 4*1024**3,previous[1]))
    observations=Observations();observations.phase("selected_decode")
    started=time.monotonic();checkpoints=[];maximum_allocation=0
    report={"synthetic_only":True,"schema_conversion_exercised":False,"mcap_payload_decoding_exercised":False,
        "odometry_message_count":1_000_000,"estimate_message_count":100_000,"reference_message_count":100_000,
        "process_address_space_soft_limit_bytes":resource.getrlimit(resource.RLIMIT_AS)[0],"status":"inconclusive","failure_code":None}
    try:
        with Workspace(args.scratch_directory,lambda:_resources(args.scratch_directory),observations,started+1800) as workspace:
            sink=ScientificSink(workspace);sink.binding_observations=[]
            schema=SimpleNamespace(name="Adp.OdometryState",data=b"synthetic-benchmark-schema")
            channel=SimpleNamespace(message_encoding="protobuf")
            timestamp=2_000_000_000
            for i in range(1_000_000):
                stamp=timestamp+i*10_000_000
                sink.odometry.add(schema,channel,SimpleNamespace(log_time=stamp,publish_time=stamp),SimpleNamespace(timestamp=stamp,x_position=i*.1,y_position=0.,yaw_angle=0.))
                if i%1024==0:workspace.checkpoint()
            checkpoints.append({"phase":"odometry_staged",**_snapshot()})
            points=np.asarray([-1.,120.]);zeros=np.zeros(2)
            paths=[]
            for y in (0.,.5):
                paths.append(_pack_path(EgoRelativePath(source="synthetic",stations_m=points,x_m=points,y_m=zeros+y,heading_rad=zeros,
                    origin_footpoint_m=np.asarray([0.,y]),origin_distance_m=y,origin_heading_rad=0.,reversed_to_positive_x=False)))
            topology="ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY"
            for i in range(100_000):
                stamp=timestamp+50_000_000+i*100_000_000
                for role,payload in zip(("estimate","reference"),paths):
                    sink.geometry.times[role].append(stamp)
                    metadata={"topology":topology,"failure":None,"estimator_available":role=="estimate"}
                    if role=="reference":metadata["reference_failure_detail"]=None
                    workspace.science.execute("INSERT INTO geometry VALUES (?,?,?,?)",(role,i,json.dumps(metadata),payload))
                workspace.science.execute("INSERT INTO estimate_inputs VALUES (?,?,?,?,?,NULL)",(i,_time_key(stamp),_time_key(stamp),_time_key(stamp),"[0,0,0.5,0.5,0.5]"))
                sink.geometry.topology_counts[topology]+=1
                sink._diagnostics.reference(None,{})
                if i%1024==0:workspace.checkpoint()
            # Explicit index/sort work uses MEMORY temp within the same cap.
            workspace.science.execute("CREATE INDEX benchmark_role_position ON geometry(role,position)")
            workspace.science.execute("SELECT time FROM odometry ORDER BY x DESC LIMIT 1").fetchone()
            workspace.science.commit();workspace.checkpoint()
            maximum_allocation=sum(max(p.stat().st_size,p.stat().st_blocks*512) for p in workspace.directory.iterdir())
            checkpoints.append({"phase":"geometry_inputs_and_sort_staged",**_snapshot()})
            observations.phase("scientific_finalize")
            readiness,availability,checked=sink.finalize()
            assert readiness["sensor_geometry_support"]["frame_count"]==100_000
            assert readiness["complete_condition_support"]["frame_count"]==100_000
            assert readiness["complete_condition_support"]["transition_count"]==99_999
            assert availability=="available_for_checks" and checked
            checkpoints.append({"phase":"matching_and_features_complete",**_snapshot()})
            report.update(status="complete",sensor_geometry_frames=100_000,complete_condition_frames=100_000,complete_condition_transitions=99_999)
    except Exception as error:
        report["failure_code"]=scientific_failure(error)
        if "workspace" in locals() and workspace.unexpected_scratch_names:
            report["unexpected_scratch_names_synthetic_only"]=workspace.unexpected_scratch_names
    finally:
        report.update(elapsed_seconds=time.monotonic()-started,execution_observations=observations.summary(),checkpoints=checkpoints,
            maximum_sampled_database_allocation_bytes=maximum_allocation)
        resource.setrlimit(resource.RLIMIT_AS,previous)
    args.output_report.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="complete" else 3


if __name__=="__main__":raise SystemExit(main())
