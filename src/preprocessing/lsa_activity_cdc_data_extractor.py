from pathlib import Path
import csv

from mcap.reader import make_reader
from mcap_protobuf.decoder import DecoderFactory


MCAP_PATH = Path(
    "/data/mcap_data/2025-05-27_14-04-21_2025-05-27_14-04-41_MCAP_000101.mcap"
)

TOPIC = "/adp/lsa_activity_cdc_data"

OUTPUT_PATH = Path("/outputs/topics/lsa_activity_cdc_data.csv")


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = []

    with MCAP_PATH.open("rb") as f:
        reader = make_reader(
            f,
            decoder_factories=[DecoderFactory()],
        )

        first_log_time = None

        for schema, channel, message, decoded in reader.iter_decoded_messages(
            topics=[TOPIC]
        ):
            if first_log_time is None:
                first_log_time = message.log_time

            # Time relative to beginning of this topic
            time_s = (message.log_time - first_log_time) / 1e9

            row = {
                "log_time_ns": message.log_time,
                "time_s": time_s,

                "distance_to_centerline":
                    decoded.distance_to_centerline,

                "distance_to_right_lane_boundary_back_axis":
                    decoded.distance_to_right_lane_boundary_back_axis,

                "distance_to_left_lane_boundary_back_axis":
                    decoded.distance_to_left_lane_boundary_back_axis,

                "lane_change_to_right_detected":
                    decoded.lane_change_to_right_detected,

                "lane_change_to_left_detected":
                    decoded.lane_change_to_left_detected,

                "distance_to_next_street_type":
                    decoded.distance_to_next_street_type,

                "next_street_type":
                    decoded.next_street_type,

                "lane_type_left":
                    decoded.lane_type_left,

                "lane_type_right":
                    decoded.lane_type_right,

                "any_target_available":
                    decoded.any_target_available,

                "longitudinal_distance":
                    decoded.longitudinal_distance,

                "velocity_relative_x":
                    decoded.velocity_relative_x,

                "velocity_relative_y":
                    decoded.velocity_relative_y,

                "acceleration":
                    decoded.acceleration,

                "object_width":
                    decoded.object_width,

                "is_lsa_driver_intervention":
                    decoded.is_lsa_driver_intervention,

                "hoo130_state":
                    decoded.hoo130_state,

                "lane_width":
                    decoded.lane_width,

                "is_system_initiated_lane_change":
                    decoded.is_system_initiated_lane_change,

                "is_extended_ece_lane_change":
                    decoded.is_extended_ece_lane_change,

                "lane_change_state":
                    decoded.lane_change_state,

                "lane_change_use_case":
                    decoded.lane_change_use_case,

                "lane_change_direction":
                    decoded.lane_change_direction,

                "operation_column_status":
                    decoded.operation_column_status,

                "active_indicator":
                    decoded.active_indicator,

                "lane_change_cancellation_reasons":
                    decoded.lane_change_cancellation_reasons,

                "lane_change_availability":
                    decoded.lane_change_availability,

                "alg_state":
                    decoded.alg_state,

                "alg_auto_lane_change_state":
                    decoded.alg_auto_lane_change_state,
            }

            # Derived quantity:
            # lateral position relative to lane center.
            #
            # Sign convention must still be confirmed.
            row["ego_lane_center_offset"] = (
                row["distance_to_right_lane_boundary_back_axis"]
                - row["distance_to_left_lane_boundary_back_axis"]
            ) / 2.0

            rows.append(row)

    if not rows:
        raise RuntimeError(
            f"No decoded messages found for topic {TOPIC}"
        )

    with OUTPUT_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=rows[0].keys(),
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"Topic: {TOPIC}")
    print(f"Samples extracted: {len(rows)}")
    print(f"Duration: {rows[-1]['time_s']:.3f} s")
    print(f"Saved to: {OUTPUT_PATH}")

    print("\nFirst 5 samples:")

    for row in rows[:5]:
        print(
            f"t={row['time_s']:.3f} s | "
            f"left={row['distance_to_left_lane_boundary_back_axis']:.3f} m | "
            f"right={row['distance_to_right_lane_boundary_back_axis']:.3f} m | "
            f"lane_width={row['lane_width']:.3f} m | "
            f"offset={row['ego_lane_center_offset']:.3f} m"
        )


if __name__ == "__main__":
    main()