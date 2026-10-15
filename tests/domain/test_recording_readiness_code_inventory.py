"""Conservative literal-code inventory for the pinned readiness consumers."""

import ast
from pathlib import Path
import unittest

from lane_residuals.domain.recording_readiness import PINNED_DATA_CODES


MODULES = (
    "domain/geometry_validation", "domain/pairing", "domain/alignment",
    "domain/conditional_features", "domain/motion", "domain/exploratory_residuals",
    "io/exploratory_residuals",
)
# Inspect whole modules, including helpers and constructors. These exact sites
# belong only to residual calculation; counts-only readiness never calls them.
EXCLUDED = {
    ("domain/alignment", "compare_spatially_aligned_paths", "reference_alignment_estimate_coverage_incomplete"):
        "Residual-only alignment coverage; readiness uses _h100_geometry's own coverage labels.",
    ("domain/alignment", "compare_spatially_aligned_paths", "reference_alignment_reference_coverage_incomplete"):
        "Residual-only alignment coverage; readiness uses _h100_geometry's own coverage labels.",
    ("domain/exploratory_residuals", "aligned_residual", "anchor_distance_exceeds_1m_or_invalid"):
        "Residual-only guard; readiness independently counts its fixed anchor stage.",
    ("domain/exploratory_residuals", "aligned_residual", "residual_non_finite"):
        "Numeric residuals are not calculated by the counts-only consumer.",
}


class ReadinessCodeInventoryTests(unittest.TestCase):
    def test_pinned_converter_literals_are_classified_or_explicitly_excluded(self):
        root=Path(__file__).resolve().parents[2]/"src/lane_residuals"
        observed=set()
        for module in MODULES:
            tree=ast.parse((root/(module+".py")).read_text())
            for function in ast.walk(tree):
                if not isinstance(function,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(function):
                    call=node.exc if isinstance(node,ast.Raise) else None
                    if not (isinstance(call,ast.Call) and isinstance(call.func,ast.Name)
                            and call.func.id in ("GeometryValidationError","ConditionalFeatureError")):
                        continue
                    self.assertTrue(call.args,(module,function.name,node.lineno))
                    code=call.args[0]
                    self.assertIsInstance(code,ast.Constant,(module,function.name,node.lineno))
                    self.assertIsInstance(code.value,str)
                    site=(module,function.name,code.value)
                    observed.add(site)
                    if site in EXCLUDED:
                        self.assertTrue(EXCLUDED[site])
                    elif site==("io/exploratory_residuals","_estimate_features","estimate_inputs_non_finite"):
                        # This literal has its explicit prefixed CONDITION_DATA entry.
                        from lane_residuals.domain.recording_readiness import CONDITION_DATA
                        self.assertIn("estimate_features_"+code.value,CONDITION_DATA)
                    else:
                        self.assertIn(code.value,PINNED_DATA_CODES,site)
        self.assertTrue(set(EXCLUDED)<=observed,"Remove stale exclusions when consumers change")
