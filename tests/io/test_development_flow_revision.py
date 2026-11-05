"""A prospective numerical revision never inherits an older fit authorization."""
import unittest

from lane_residuals.io import development_flow as contract


class FlowRevisionTests(unittest.TestCase):
    def test_adopted_old_revision_is_not_authorization_for_corrected_protocol(self):
        pin = "a"*64
        auth = contract.authorization_draft(pin)
        auth["attestations"] = dict.fromkeys(auth["attestations"], True)
        contract.require_authorization(auth, pin)
        auth["contract_revision"] = "v0.19.27-matched-flow-owner-2026-11-04"
        with self.assertRaisesRegex(ValueError, "explicit_owner_authorization"):
            contract.require_authorization(auth, pin)

    def test_old_request_revision_is_refused_without_reading_inputs(self):
        request = dict.fromkeys(contract.FIELDS, "synthetic")
        request.update(contract_revision="v0.19.27-matched-flow-2026-11-04",
            expected_original_one_state_experiment_sha256="a"*64, expected_one_state_ar_result_sha256="b"*64)
        with self.assertRaisesRegex(ValueError, "closed_request_schema"):
            contract.validate_request(request)
