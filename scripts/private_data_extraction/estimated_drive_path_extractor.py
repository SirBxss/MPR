from pathlib import Path
import csv
import json

from mcap.reader import make_reader
from mcap_protobuf.decoder import DecoderFactory


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MCAP_PATH = PROJECT_ROOT / "data/raw/mcap/2025-05-27_14-04-21_2025-05-27_14-04-41_MCAP_000101.mcap"

TOPIC = "/adp/estimated_drive_paths"

OUTPUT_DIR = PROJECT_ROOT / "outputs/diagnostics/validation/topics"

PATH_OUTPUT = OUTPUT_DIR / "estimated_drive_paths.csv"
CONFIDENCE_OUTPUT = OUTPUT_DIR / "estimated_drive_path_confidences.csv"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path_rows = []
    confidence_rows = []

    first_log_time = None

    with MCAP_PATH.open("rb") as f:
        reader = make_reader(
            f,
            decoder_factories=[DecoderFactory()],
        )

        for schema, channel, message, decoded in reader.iter_decoded_messages(
            topics=[TOPIC]
        ):
            if first_log_time is None:
                first_log_time = message.log_time

            time_s = (message.log_time - first_log_time) / 1e9

            # Timestamp contained inside the protobuf message
            internal_timestamp = getattr(decoded, "time_stamp", None)

            # One message can contain multiple estimated drive paths
            for path_index, drive_path in enumerate(decoded.drive_paths):

                model = drive_path.model_parameters

                row = {
                    # MCAP timing
                    "log_time_ns": message.log_time,
                    "time_s": time_s,

                    # Internal message timestamp
                    "time_stamp": internal_timestamp,

                    # Which path inside this message
                    "path_index": path_index,

                    # Drive path metadata
                    "lane_topology_ids": json.dumps(
                        list(drive_path.lane_topology_ids)
                    ),

                    "error": drive_path.error,
                    "role": drive_path.role,

                    "estimation_age":
                        drive_path.estimation_age,

                    "distance_driven_since_last_external_constraint":
                        drive_path.distance_driven_since_last_external_constraint,

                    "model_parameters_optional_flag":
                        drive_path.model_parameters_optional_flag,

                    "sensor_boundary_cut_off_distance":
                        drive_path.sensor_boundary_cut_off_distance,

                    # Initial geometric state
                    "x_0": model.x_0,
                    "y_0": model.y_0,
                    "theta_0": model.theta_0,
                    "curvature_0": model.curvature_0,
                    "index_0": model.index_0,

                    # Piecewise path representation
                    "segment_starts": json.dumps(
                        list(model.segment_starts)
                    ),

                    "curvature_change": json.dumps(
                        list(model.curvature_change)
                    ),

                    # Useful counts
                    "num_segments":
                        len(model.segment_starts),

                    "num_curvature_changes":
                        len(model.curvature_change),

                    "num_confidences":
                        len(drive_path.drive_path_confidences),

                    # Message-level qualifiers
                    "event_data_qualifier":
                        decoded.event_data_qualifier,

                    "extended_data_qualifier":
                        decoded.extended_data_qualifier,

                    "topology_source":
                        decoded.topology_source,
                }

                path_rows.append(row)

                # Save confidence values separately in long format
                for confidence_index, confidence in enumerate(
                    drive_path.drive_path_confidences
                ):
                    confidence_rows.append({
                        "log_time_ns": message.log_time,
                        "time_s": time_s,
                        "time_stamp": internal_timestamp,
                        "path_index": path_index,
                        "role": drive_path.role,
                        "confidence_index": confidence_index,
                        "confidence": confidence,
                    })

    if not path_rows:
        raise RuntimeError(
            f"No decoded messages found for topic {TOPIC}"
        )

    # ---------------------------------------------------------
    # Save drive path information
    # ---------------------------------------------------------

    with PATH_OUTPUT.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=path_rows[0].keys(),
        )

        writer.writeheader()
        writer.writerows(path_rows)

    # ---------------------------------------------------------
    # Save confidence values
    # ---------------------------------------------------------

    with CONFIDENCE_OUTPUT.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=confidence_rows[0].keys(),
        )

        writer.writeheader()
        writer.writerows(confidence_rows)

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    unique_times = {
        row["log_time_ns"]
        for row in path_rows
    }

    print(f"Topic: {TOPIC}")
    print(f"Messages: {len(unique_times)}")
    print(f"Drive-path rows: {len(path_rows)}")
    print(f"Confidence rows: {len(confidence_rows)}")

    print(
        f"Duration: "
        f"{max(row['time_s'] for row in path_rows):.3f} s"
    )

    print(f"\nSaved:")
    print(f"  {PATH_OUTPUT}")
    print(f"  {CONFIDENCE_OUTPUT}")

    print("\nFirst drive paths:")

    for row in path_rows[:5]:
        print(
            f"t={row['time_s']:.3f} s | "
            f"path={row['path_index']} | "
            f"role={row['role']} | "
            f"x0={row['x_0']:.3f} | "
            f"y0={row['y_0']:.3f} | "
            f"theta0={row['theta_0']:.4f} | "
            f"kappa0={row['curvature_0']:.6f} | "
            f"conf_samples={row['num_confidences']}"
        )


if __name__ == "__main__":
    main()
