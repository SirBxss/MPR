"""Run and reconcile whole-module unittest shards for the CI timing trial."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import groupby
import json
import os
from pathlib import Path
from time import perf_counter
import unittest


PROFILES = ("py310-current", "py312-current", "py312-frozen-reader")
SHARDS = 4
BASELINE_EXECUTIONS = 1289
BASELINE_INVENTORY = "fa17ae7caae5bf93894ca99ce10502f996af0b2e5dd25c98f41461ee386b4efc"
BASELINE_SKIPS = (
    "tests.compatibility.test_wheel_contents.WheelContentTests.test_wheel_contains_only_the_lane_residuals_top_level_package",
    "tests.workflows.test_projection_alignment_batch_cli.PrivateHistoricalProjectionParityTests."
    "test_original_ten_mcaps_match_historical_v050_numerically",
)


def _cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _cases(item)
        else:
            yield item


def _plan(cases):
    # Keep every occurrence, including imported TestCases discovered more than once.
    # Module names keep setUpModule and all classes in that module on one runner.
    counts = Counter(type(case).__module__ for case in cases)
    measured = json.loads(Path(__file__).with_name("unittest_module_seconds.json").read_text())
    weights = {name: measured.get(name, 0.1 + 0.05 * count) for name, count in counts.items()}
    loads = [0] * SHARDS
    assignment = {}
    for name in sorted(weights, key=lambda name: (-weights[name], name)):
        shard = min(range(SHARDS), key=lambda i: (loads[i], i))
        assignment[name] = shard
        loads[shard] += weights[name]
    return assignment


class _Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started = []

    def startTest(self, test):
        self.started.append(test.id())
        super().startTest(test)


def run_shard(profile, shard, output, manifest_only=False):
    start = perf_counter()
    loader = unittest.TestLoader()
    cases = list(_cases(loader.discover("tests", top_level_dir=".")))
    if loader.errors or not cases:
        raise SystemExit("\n".join(loader.errors) or "unittest discovery returned no tests")
    assignment = _plan(cases)
    expected = [[case.id(), assignment[type(case).__module__]] for case in cases]
    executed, skipped, durations = [], [], defaultdict(float)
    success = True
    if not manifest_only:
        # Retain full discovery order and each original contiguous module block.
        for name, module_cases in groupby(cases, key=lambda case: type(case).__module__):
            if assignment[name] != shard:
                continue
            before = perf_counter()
            result = unittest.TextTestRunner(resultclass=_Result).run(unittest.TestSuite(module_cases))
            durations[name] += perf_counter() - before
            executed.extend(result.started)
            skipped.extend([test.id(), reason] for test, reason in result.skipped)
            success &= result.wasSuccessful()
        success &= executed == [identifier for identifier, assigned in expected if assigned == shard]
        success &= not (Counter(identifier for identifier, _ in skipped) - Counter(executed))
    report = {"profile": profile, "shard": shard, "expected": expected, "executed": executed,
              "skipped": skipped, "module_seconds": dict(durations),
              "wall_seconds": perf_counter() - start, "passed": success and not manifest_only}
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{profile} shard {shard + 1}/{SHARDS}: {len(executed)} tests, "
          f"{len(skipped)} skipped, {report['wall_seconds']:.2f}s")
    return 0 if success else 1


def reconcile(directory: Path):
    by_profile = defaultdict(dict)
    for path in sorted(directory.rglob("trial-*.json")):
        report = json.loads(path.read_text())
        profile, shard = report["profile"], report["shard"]
        if profile not in PROFILES or not 0 <= shard < SHARDS or shard in by_profile[profile]:
            raise ValueError(f"unexpected or duplicate shard report {path}")
        by_profile[profile][shard] = report
    lines = ["| Environment | Executions | Skipped | Longest shard | Total shard test time |",
             "|---|---:|---:|---:|---:|"]
    for profile in PROFILES:
        reports = by_profile[profile]
        if set(reports) != set(range(SHARDS)) or not all(r["passed"] for r in reports.values()):
            raise ValueError(f"{profile}: incomplete or failed reports")
        manifest = reports[0]["expected"]
        if not manifest or any(r["expected"] != manifest for r in reports.values()):
            raise ValueError(f"{profile}: discovery or assignment differs across runners")
        expected = Counter(identifier for identifier, _ in manifest)
        executed = Counter()
        skips = Counter()
        times = []
        for shard, report in reports.items():
            shard_ids = [identifier for identifier, assigned in manifest if assigned == shard]
            if report["executed"] != shard_ids:
                raise ValueError(f"{profile}: execution differs from plan in shard {shard}")
            executed.update(report["executed"])
            skipped = Counter(identifier for identifier, _ in report["skipped"])
            if skipped - Counter(shard_ids):
                raise ValueError(f"{profile}: unexpected skip outside test inventory")
            skips.update(skipped)
            times.append(report["wall_seconds"])
        if executed != expected:
            raise ValueError(f"{profile}: test multiplicities differ from unittest discovery")
        inventory = sha256(json.dumps(sorted(executed.items()), separators=(",", ":")).encode()).hexdigest()
        if (sum(executed.values()) != BASELINE_EXECUTIONS or inventory != BASELINE_INVENTORY
                or skips != Counter(BASELINE_SKIPS)):
            raise ValueError(f"{profile}: test inventory or opt-in skips differ from the serial baseline")
        lines.append(f"| {profile} | {sum(executed.values())} | {sum(skips.values())} "
                     f"| {max(times) / 60:.2f} min | {sum(times) / 60:.2f} min |")
        print(f"{profile} skip IDs: {dict(skips)}")
    summary = "\n".join(lines)
    print(summary)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(summary + "\n")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="command", required=True)
    run = modes.add_parser("run")
    run.add_argument("--profile", required=True, choices=PROFILES)
    run.add_argument("--shard", type=int, required=True, choices=range(SHARDS))
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--manifest-only", action="store_true", help="Show the assignment without executing tests.")
    summary = modes.add_parser("reconcile")
    summary.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "reconcile":
        return reconcile(args.directory)
    return run_shard(args.profile, args.shard, args.output, args.manifest_only)


if __name__ == "__main__":
    raise SystemExit(main())
