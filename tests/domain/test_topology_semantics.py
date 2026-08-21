import unittest

from lane_residuals.domain.topology_semantics import (
    ProtobufWireError,
    decode_topology_message,
    extract_top_level_varint,
    numeric_summary,
    topology_interpretation,
)
from tests.domain.test_geometry_validation import (
    _estimated_schema,
    _path,
    _root_message,
)


class TopologySemanticsTests(unittest.TestCase):
    def test_wire_enum_reports_presence_default_and_last_duplicate(self):
        self.assertEqual(extract_top_level_varint(b"\x10\x04", 2), (True, 4, 1))
        self.assertEqual(extract_top_level_varint(b"\x08\x01", 2), (False, None, 0))
        self.assertEqual(
            extract_top_level_varint(b"\x10\x03\x10\x04", 2),
            (True, 4, 2),
        )
        with self.assertRaises(ProtobufWireError):
            extract_top_level_varint(b"\x10", 2)

    def test_descriptor_decode_retains_numeric_name_and_selected_index(self):
        schema = _estimated_schema()
        decoded = decode_topology_message(
            _root_message(schema, [_path(schema)], topology=1),
            raw_payload=b"\x10\x01",
            message_index=7,
            log_time_ns=200,
            publish_time_ns=190,
            schema_fingerprint="abc",
        )
        self.assertEqual(decoded.topology_decoded_value, 1)
        self.assertEqual(
            decoded.topology_source_name,
            "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
        )
        self.assertTrue(decoded.topology_wire_decode_consistent)
        self.assertEqual(decoded.selected_drive_path_count, 1)
        self.assertEqual(decoded.selected_drive_path_index, 0)
        self.assertEqual(decoded.estimator_state, "available_no_error")

    def test_lane_map_interpretation_is_map_but_rlmb_sharing_is_unknown(self):
        result = topology_interpretation(
            3,
            "ROAD_TOPOLOGY_SOURCE_LANE_MAP",
            all_wire_decodes_consistent=True,
        )
        self.assertEqual(result["classification"], "lane_map_topology")
        self.assertFalse(result["sensor_topology_source"])
        self.assertEqual(result["independence_from_rlmb"], "unknown")
        self.assertNotIn("independent_sensor_topology", result)
        self.assertTrue(result["map_or_fused_topology"])
        self.assertEqual(result["fusion_status"], "unknown")
        self.assertEqual(result["shares_upstream_information_with_rlmb"], "unknown")
        self.assertFalse(result["enum_or_schema_decoding_defect"])
        self.assertFalse(result["timing_used_for_semantic_classification"])

    def test_sensor_topology_does_not_claim_rlmb_independence(self):
        result = topology_interpretation(
            4,
            "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
            all_wire_decodes_consistent=True,
        )
        self.assertTrue(result["sensor_topology_source"])
        self.assertEqual(result["classification"], "sensor_topology_estimate")
        self.assertEqual(result["independence_from_rlmb"], "unknown")
        self.assertEqual(result["shares_upstream_information_with_rlmb"], "unknown")
        self.assertNotIn("independent_sensor_topology", result)

    def test_numeric_summary_has_fixed_deterministic_quantiles(self):
        result = numeric_summary([None, "", 1, 2, 3, 4, 5])
        self.assertEqual(result["count"], 5)
        self.assertEqual(result["min"], 1.0)
        self.assertEqual(result["q50"], 3.0)
        self.assertEqual(result["max"], 5.0)


if __name__ == "__main__":
    unittest.main()
