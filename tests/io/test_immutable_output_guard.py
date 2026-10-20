"""Native writer misuse must leave immutable parent snapshots byte-identical."""

import unittest

from lane_residuals.domain.artifact_registry import RegistryError
from lane_residuals.io import artifact_registry as registry, generic_cohort as cohort
from tests.io import test_generic_cohort as fixtures


def tree(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes() if p.is_file() else None
            for p in directory.rglob("*")}


class ImmutableOutputGuardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.GenericCohortIOTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_cohort_inside_registry_and_objects_rejected_before_any_creation(self):
        f = self.fixture
        before = tree(f.native.project)
        for output in (f.registry_directory / "new-cohort", f.registry_directory / "objects/new-cohort"):
            with self.subTest(output=output), self.assertRaises(RegistryError):
                cohort.create_cohort(**{**f.arguments(), "output_directory": output})
            self.assertEqual(tree(f.native.project), before)
            registry.load_registry(f.registry_directory, f.registry_pin)

    def test_registry_inside_registry_is_rejected_and_parent_still_replays(self):
        f = self.fixture
        before = tree(f.native.project)
        for output in (f.registry_directory, f.registry_directory / "next", f.registry_directory / "objects/next"):
            with self.subTest(output=output), self.assertRaises(RegistryError):
                registry.import_evidence(f.native.manifest_path, project_root=f.native.project,
                    output_directory=output, previous_directory=f.registry_directory, expected_previous_sha256=f.registry_pin)
            self.assertEqual(tree(f.native.project), before)
            registry.load_registry(f.registry_directory, f.registry_pin)

    def test_cohort_container_and_partial_markers_are_also_immutable(self):
        f = self.fixture
        _, pin = cohort.create_cohort(**f.arguments())
        before = tree(f.native.project)
        with self.assertRaises(RegistryError):
            registry.import_evidence(f.native.manifest_path, project_root=f.native.project,
                output_directory=f.output / "nested", previous_directory=f.registry_directory, expected_previous_sha256=f.registry_pin)
        self.assertEqual(tree(f.native.project), before)
        cohort.load_cohort(f.output, pin, f.registry_directory)
        partial = f.output.with_name("partial")
        partial.mkdir()
        (partial / "registry.json").write_text("{")
        before = tree(f.native.project)
        with self.assertRaises(RegistryError):
            registry._private_output(f.native.project, partial / "nested")
        self.assertEqual(tree(f.native.project), before)

    def test_explicit_input_ancestor_and_symlink_or_traversal_are_rejected(self):
        f = self.fixture
        output = f.native.project / "data/catalog/private/new/child"
        # Protect even an external caller-supplied partial snapshot without a marker.
        with self.assertRaisesRegex(RegistryError, "overlaps_immutable_input"):
            registry._private_output(f.native.project, output, (output.parent,))
        with self.assertRaisesRegex(RegistryError, "overlaps_immutable_input"):
            registry.separate_output(output.parent, (output,))
        alias = f.native.project / "data/catalog/private/alias"
        alias.symlink_to(f.registry_directory, target_is_directory=True)
        for output in (alias / "new", f.native.project / "data/catalog/private/new/../other"):
            with self.subTest(output=output), self.assertRaises(RegistryError):
                registry._private_output(f.native.project, output)
