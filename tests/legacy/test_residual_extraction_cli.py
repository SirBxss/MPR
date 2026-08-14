import contextlib
import io
import unittest

from lane_residuals.residual_extraction_cli import main


class WithdrawnResidualCliTests(unittest.TestCase):
    def test_old_provisional_gt_command_is_fail_closed(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = main([])
        self.assertEqual(status, 3)
        self.assertIn("withdrawn", stderr.getvalue())
        self.assertIn("reference_audit_cli", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
