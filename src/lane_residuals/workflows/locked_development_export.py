"""Sequential, fail-closed development exports through a frozen reviewed producer.

Only the owner runs this on private data, after implementation review/CI/merge.
The metadata consumer orchestrates reservations/publication; it never becomes an
implicitly accepted numeric producer. Every failed attempt is retained.
"""

from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

from ..domain import artifact_registry as policy
from ..io import artifact_registry as registry, locked_development as locked
from ..io.numeric_export_inputs import read_json
from .recording_ingestion import _runtime

REVISION = "v0.19.15-locked-development-export-plan-2026-10-20-a1"
FROZEN_VERSIONS = {"python": "3.12.3", "mcap": "1.4.0", "mcap-protobuf-support": "0.5.4",
                   "numpy": "2.5.1", "protobuf": "7.35.1", "lz4": "4.4.5", "zstandard": "0.25.0"}
require = policy.require


def sha(path):
    with Path(path).open("rb") as stream:
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(1024**2), b""):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    """Exclusive durable evidence; partial files are preserved on failure."""
    raw = value if isinstance(value, bytes) else (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with Path(path).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    registry._fsync_directory(Path(path).parent)


def environment(release):
    return {**os.environ, "PYTHONPATH": str(release / "src"), "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1"}


def versions(release):
    code = ('import importlib.metadata as m,json,platform;'
            'import mcap,mcap_protobuf,google.protobuf,numpy,zstandard,lz4.frame,sqlite3;'
            'v={n:m.version(n) for n in ["lz4","mcap","mcap-protobuf-support","numpy","protobuf","zstandard"]};'
            'v["python"]=platform.python_version();print(json.dumps(v,sort_keys=True))')
    return json.loads(subprocess.check_output([sys.executable, "-c", code], cwd=release,
                                              env=environment(release), text=True))


def resources(project):
    available = next(int(s.split()[1]) * 1024 for s in Path("/proc/meminfo").read_text().splitlines()
                     if s.startswith("MemAvailable:"))
    free = shutil.disk_usage("/var/tmp").free
    require(available >= 12 * 1024**3 and free >= 19_864_223_744, "locked_export_operational_headroom_insufficient")
    require((project / "data").stat().st_dev == Path("/var/tmp").stat().st_dev,
            "locked_export_scratch_output_filesystem_mismatch")
    return {"mem_available_bytes": available, "scratch_free_bytes": free}


def logged(command, release, log, lock_fds):
    with log.open("x") as stream:
        with subprocess.Popen(command, cwd=release, env=environment(release), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, bufsize=1, pass_fds=tuple(lock_fds)) as process:
            try:
                for line in process.stdout:
                    stream.write(line)
                    stream.flush()
                    print(line, end="", flush=True)
                return process.wait()
            except BaseException:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise


def package(result, roots):
    members = {}
    for folder, prefix in roots:
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            require(not path.is_symlink(), "locked_export_result_symlink")
            if path.is_file():
                require(not path.name.lower().endswith((".mcap", ".mcap.zst")), "locked_export_raw_in_result_forbidden")
                members[prefix + "/" + path.relative_to(folder).as_posix()] = path
    hashes = {name: sha(path) for name, path in members.items()}
    with zipfile.ZipFile(result, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(members.items()):
            archive.write(path, name)
        archive.writestr("SHA256SUMS", "".join(h + "  " + name + "\n" for name, h in sorted(hashes.items())))
    with zipfile.ZipFile(result) as archive:
        require(archive.testzip() is None and len(archive.namelist()) == len(hashes) + 1 and
                set(archive.namelist()) == set(hashes) | {"SHA256SUMS"}, "locked_export_result_crc_or_file_set")
        require(all(hashlib.sha256(archive.read(name)).hexdigest() == h for name, h in hashes.items()),
                "locked_export_result_checksum")


def execute(*, project_root, plan_path, expected_plan_sha256, expected_consumer_tree,
            expected_consumer_runtime):
    """Run one issued plan once. No retry, role amendment, scan or training mode."""
    project = Path(project_root).expanduser().resolve(strict=True)
    require(not str(plan_path).lower().endswith((".mcap", ".mcap.zst")), "locked_export_metadata_required")
    plan, pin, _ = read_json(plan_path)
    require(pin == policy.digest(expected_plan_sha256), "locked_export_plan_digest_mismatch")
    policy.keys(plan, {"contract_revision", "cohort_directory", "expected_cohort_sha256", "original_registry_directory",
        "expected_original_registry_sha256", "descendants", "frozen_release_directory", "frozen_release_pin",
        "expected_frozen_release_pin_sha256", "collection_lock_path", "targets", "attempt_directory", "result_zip"})
    require(plan["contract_revision"] == REVISION, "locked_export_plan_revision")
    def path(value):
        require(type(value) is str and value and ".." not in Path(value).parts, "locked_export_path_invalid")
        p = Path(value).expanduser()
        p = p if p.is_absolute() else project / p
        # Check parents only. Authorization endpoints must reach ObjectStore's
        # registered-raw guard before any endpoint stat/resolve/open.
        require(p.parent.resolve() == p.parent, "locked_export_path_symlink")
        return p
    cohort_dir, original = path(plan["cohort_directory"]), path(plan["original_registry_directory"])
    require(type(plan["descendants"]) is list, "locked_export_chain_required")
    chain = []
    for item in plan["descendants"]:
        policy.keys(item, {"directory", "sha256"})
        chain.append(locked.RegistryCheckpoint(path(item["directory"]), policy.digest(item["sha256"])))
    context_args = dict(cohort_directory=cohort_dir, expected_cohort_sha256=plan["expected_cohort_sha256"],
                        original_registry_directory=original)
    targets = plan["targets"]
    require(type(targets) is list and 0 < len(targets) <= policy.MAX_EVENTS, "locked_export_target_limit")
    for target in targets:
        policy.keys(target, {"raw_sha256", "authorization", "expected_authorization_sha256", "numeric_output",
                             "reserved_registry", "complete_registry"})
    raws = [t["raw_sha256"] for t in targets]
    release, release_pin_path = path(plan["frozen_release_directory"]), path(plan["frozen_release_pin"])
    require(not release.is_symlink() and release.is_dir(), "locked_export_release_symlink_or_missing")
    protected = [cohort_dir, original, release, *(c.directory for c in chain)]
    attempt, result = path(plan["attempt_directory"]), path(plan["result_zip"])
    require(attempt.is_relative_to(project / "outputs/run_receipts") and attempt != project / "outputs/run_receipts" and result.suffix == ".zip",
            "locked_export_attempt_or_result_path")
    outputs = [attempt, result]
    for target in targets:
        numeric = path(target["numeric_output"])
        require(numeric.is_relative_to(project / "data/derived") and numeric != project / "data/derived", "locked_export_numeric_output_location")
        outputs.extend([numeric, registry._private_output(project, path(target["reserved_registry"]), protected),
                        registry._private_output(project, path(target["complete_registry"]), protected)])
    require(len(outputs) == len(set(outputs)), "locked_export_duplicate_output")
    for i, output in enumerate(outputs):
        registry.separate_output(output, protected + outputs[:i] + outputs[i+1:])
        require(not os.path.lexists(output), "locked_export_attempt_or_output_exists_preserve_no_retry")
    # Reject container misuse before even temporary metadata replay directories.
    context = locked.load_context(**context_args, descendants=chain)
    require(context.cohort["registry_sha256"] == policy.digest(plan["expected_original_registry_sha256"]),
            "locked_export_original_registry_mismatch")
    locked.preflight_targets(context, raws)
    lineages = [locked.readiness_files(context, raw) for raw in raws]
    # Learn raw aliases before inspecting owner authorization endpoints.
    store = registry.ObjectStore()
    for record in context.metadata["records"]:
        store.raw_paths.update(record["canonical_paths_private"])
    for event in context.metadata["events"]:
        if event["kind"] in {"registration", "archive"}:
            key = "source_specification.json" if event["kind"] == "registration" else "registration/source_specification.json"
            spec = registry.decode(context.objects[event["files"][key]])
            store.raw_paths.update(r["local_path_private"] for r in spec["recordings"])
    watched = {Path(plan_path).expanduser().absolute(): pin}
    store.add(plan_path, pin)
    for target, files in zip(targets, lineages):
        auth_path = path(target["authorization"])
        auth_pin = store.add(auth_path, target["expected_authorization_sha256"])
        auth = registry.decode(store.objects[auth_pin])
        require(registry.authorization(auth), "locked_export_owner_authorization_not_adopted")
        registration = registry.decode(context.original_objects[files["registration/registration.json"]])
        require(auth["authorized_raw_sha256"] == [target["raw_sha256"]] and
                auth["registration_sha256"] == files["registration/registration.json"] and
                auth["source_specification_sha256"] == files["registration/source_specification.json"] and
                auth["preserved_readiness_report_sha256"] == files["readiness.json"] and
                auth["batch_id"] == registration["batch_id"], "locked_export_authorization_lineage_mismatch")
        watched[auth_path] = auth_pin
    # Registry imports scan all project consent, so unselected new consent must
    # not reserve finals/outsiders as an incidental side effect of this run.
    known_auth = {e["sha256"] for e in context.metadata["events"] if e["kind"] == "authorization"}
    selected_auth = {t["expected_authorization_sha256"] for t in targets}
    config = project / "config/private"
    config_paths = sorted(config.rglob("*.json"))
    for p in config_paths:
        h = store.add(p)
        value = registry.decode(store.objects[h])
        if isinstance(value, dict) and (value.get("purpose") == registry.numeric.AUTHORIZATION_PURPOSE or
                value.get("contract_revision") == registry.numeric.AUTHORIZATION_REVISION or
                p.name.startswith("numeric_export_authorization_")):
            if registry.authorization(value):
                require(h in known_auth | selected_auth, "locked_export_unselected_new_authorization")
        watched[p] = h
    frozen, frozen_pin, _ = read_json(release_pin_path)
    require(frozen_pin == policy.digest(plan["expected_frozen_release_pin_sha256"]) and isinstance(frozen.get("files"), dict),
            "locked_export_frozen_source_pin_mismatch")
    watched[release_pin_path] = frozen_pin
    for name, h in frozen["files"].items():
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and ".." not in relative.parts, "locked_export_release_relative_path")
        p = path(str(release / name))
        store.add(p, h)
        watched[p] = h
    def unchanged():
        tree = subprocess.check_output(["git", "-C", str(project), "rev-parse", "HEAD^{tree}"], text=True).strip()
        dirty = subprocess.check_output(["git", "-C", str(project), "status", "--porcelain"], text=True).strip()
        require(tree == expected_consumer_tree and not dirty and
                _runtime(include_compression=True)["runtime_source_sha256"] == policy.digest(expected_consumer_runtime),
                "locked_export_consumer_source_changed")
        require({p.relative_to(release).as_posix() for p in release.rglob("*") if p.is_file()} == set(frozen["files"]),
                "locked_export_frozen_file_set_changed")
        package_files = {p.relative_to(release / "src/lane_residuals").as_posix(): sha(p)
                         for p in sorted((release / "src/lane_residuals").rglob("*.py"))}
        require(hashlib.sha256(json.dumps(package_files, sort_keys=True).encode()).hexdigest() == policy.ACCEPTED_NUMERIC_PRODUCER,
                "locked_export_frozen_producer_changed")
        for p, h in watched.items():
            store_check = registry.ObjectStore()
            store_check.raw_paths.update(store.raw_paths)
            store_check.add(p, h)
        require(sorted(config.rglob("*.json")) == config_paths, "locked_export_authorization_set_changed")
        require(versions(release) == FROZEN_VERSIONS, "locked_export_frozen_versions_changed")
    unchanged()
    observation = resources(project)
    locked.require_project_history(context, project)
    lock_paths = [project / "data/catalog/private/.registry-write.lock", path(plan["collection_lock_path"])]
    require(lock_paths[1].is_relative_to(project / "outputs/run_receipts") and lock_paths[1].suffix == ".lock" and
            lock_paths[0] != lock_paths[1], "locked_export_collection_lock_location")
    with ExitStack() as stack:
        fds = []
        for lock_path in lock_paths:
            # Parents already exist from the accepted metadata/collection work.
            fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            stack.callback(os.close, fd)
            require(stat.S_ISREG(os.fstat(fd).st_mode), "locked_export_regular_lock_required")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise policy.RegistryError("locked_export_another_writer_or_collection_running") from exc
            fds.append(fd)
        # Repeat under the shared writer lock before an attempt exists.
        context = locked.load_context(**context_args, descendants=chain)
        locked.preflight_targets(context, raws)
        locked.require_project_history(context, project)
        unchanged()
        for output in outputs:
            require(not os.path.lexists(output), "locked_export_output_appeared")
            registry.separate_output(output, protected)
        fingerprints = {"plan_sha256": pin, "consumer_git_tree": expected_consumer_tree,
            "consumer_runtime_source_sha256": expected_consumer_runtime,
            "consumer_git_commit": subprocess.check_output(["git", "-C", str(project), "rev-parse", "HEAD"], text=True).strip(),
            "producer_runtime_versions": dict(FROZEN_VERSIONS),
            "producer_release_pin_sha256": frozen_pin}
        attempt.parent.mkdir(parents=True, exist_ok=True)
        attempt.mkdir(mode=0o700)
        return _run(project, plan, context_args, context, chain, targets, lineages, release, attempt,
                    result, fds, observation, unchanged, path, fingerprints, store.objects[pin])


def _run(project, plan, context_args, context, chain, targets, lineages, release, attempt,
         result, fds, observation, unchanged, path, fingerprints, plan_raw):
    receipt = {"contract_revision": REVISION, "status": "failed_preserve_attempt", "exit_code": 2,
        "cohort_sha256": context.cohort_sha256, "original_registry_sha256": context.cohort["registry_sha256"],
        "initial_registry_sha256": context.registry_sha256, "producer_runtime_source_sha256": policy.ACCEPTED_NUMERIC_PRODUCER,
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "resources_at_start": observation,
        "failures": [], "targets": [], "stages": {}, "descendants": [], "input_integrity_verified": False,
        "raw_payload_processing_attempted": False, "model_admission_authorized": False, "raw_cache_deletion_authorized": False}
    receipt.update(fingerprints)
    roots = [(attempt, "attempt")]
    stage = "preserve_plan"
    def snapshot(name, manifest, destination):
        nonlocal context
        manifest_path = attempt / (name + "_manifest.private.json")
        write(manifest_path, manifest)
        roots.append((destination, "registries/" + name))
        receipt["stages"][name] = None
        previous = chain[-1].directory if chain else path(plan["original_registry_directory"])
        _, pin = registry._import_evidence_locked(manifest_path, project_root=project, output_directory=destination,
            previous_directory=previous, expected_previous_sha256=context.registry_sha256)
        chain.append(locked.RegistryCheckpoint(destination, pin))
        receipt["descendants"].append({"directory": str(destination), "sha256": pin})
        context = locked.load_context(**context_args, descendants=chain)
        receipt["stages"][name] = 0
    def command(name, args):
        write(attempt / (name + "_command.json"), args)
        receipt["stages"][name] = None
        code = logged(args, release, attempt / (name + ".log"), fds)
        receipt["stages"][name] = code
        require(code == 0, "locked_export_native_stage_failed_preserve_attempt")
    def manifest():
        return {"contract_revision": policy.MANIFEST_REVISION, "registrations": [], "archives": [],
                "relationships": [], "additional_authorizations": []}
    try:
        write(attempt / "ISSUED_PLAN.private.json", plan_raw)
        for i, (target, files) in enumerate(zip(targets, lineages), 1):
            tag, raw = f"target_{i:03d}", target["raw_sha256"]
            stage = tag + "_preflight"
            locked.preflight_targets(context, [raw])
            unchanged()
            resources(project)
            folder = attempt / tag
            registry.materialize(folder, files, context.original_objects)
            auth, auth_pin = path(target["authorization"]), target["expected_authorization_sha256"]
            shutil.copyfile(auth, folder / "authorization.json")
            receipt["targets"].append({"raw_sha256": raw, "status": "attempt_started", "stages_prefix": tag})
            stage = tag + "_reservation"
            m = manifest()
            m["additional_authorizations"] = [{"path": str(auth), "expected_sha256": auth_pin}]
            snapshot(stage, m, path(target["reserved_registry"]))
            # This must precede the first raw-reading command, not merely the
            # publication. Existing all-target consent can reserve targets early.
            locked.preflight_targets(context, [raw])
            require(next(r for r in context.metadata["records"] if r["raw_sha256"] == raw)
                    ["permanent_development_reservation"], "locked_export_reservation_missing")
            args = ["--registration-directory", str(folder / "registration"),
                "--preserved-inventory-report", str(folder / "inventory.json"),
                "--preserved-decode-report", str(folder / "decode.json"),
                "--preserved-readiness-report", str(folder / "readiness.json"),
                "--expected-readiness-sha256", files["readiness.json"],
                "--exposure-authorization", str(folder / "authorization.json"),
                "--expected-exposure-authorization-sha256", auth_pin]
            for topic in registry.TOPICS:
                args.extend(["--topic", topic])
            numeric = path(target["numeric_output"])
            roots.append((numeric, "numeric/" + tag))
            stage = tag + "_numeric_export"
            unchanged()
            resources(project)
            numeric.parent.mkdir(parents=True, exist_ok=True)
            receipt["raw_payload_processing_attempted"] = True
            with tempfile.TemporaryDirectory(prefix="mpr-locked-numeric-", dir="/var/tmp") as scratch:
                command(stage, [sys.executable, "-m", "lane_residuals.cli.recording_ingestion", "export-residuals",
                    *args, "--scratch-directory", scratch, "--output-directory", str(numeric)])
            summary_pin = sha(numeric / "numeric_export.json")
            write(folder / "summary_pin.json", {"summary_sha256": summary_pin})
            stage = tag + "_standalone_validation"
            validation = folder / "archive_validation.json"
            command(stage, [sys.executable, "-m", "lane_residuals.cli.numeric_archive", *args,
                "--export-directory", str(numeric), "--expected-summary-sha256", summary_pin,
                "--validation-receipt", str(validation)])
            stage = tag + "_publication"
            m = manifest()
            m["archives"] = [{"registration_directory": str(folder / "registration"),
                "preserved_inventory_report": str(folder / "inventory.json"), "preserved_decode_report": str(folder / "decode.json"),
                "preserved_readiness_report": str(folder / "readiness.json"), "expected_readiness_sha256": files["readiness.json"],
                "exposure_authorization": str(folder / "authorization.json"), "expected_exposure_authorization_sha256": auth_pin,
                "export_directory": str(numeric), "expected_summary_sha256": summary_pin,
                "validation_receipt": str(validation), "expected_validation_receipt_sha256": sha(validation)}]
            snapshot(stage, m, path(target["complete_registry"]))
            receipt["targets"][-1].update(status="complete_validated_numeric_export", summary_sha256=summary_pin)
        stage = "matched_development_validation"
        receipt["stages"][stage] = None
        selection = sorted(pin for pin, archive in context.datasets.items() if
            all(any(raw in o["raw_sha256"] and o["cohort_role"] == "development" for o in context.cohort["outings"])
                for raw in archive.raw_sha256_by_recording.values()))
        view = locked.load_development_dataset(**context_args, descendants=chain, archive_sha256=selection)
        require(view.model_admission_authorized is False, "locked_export_model_scope")
        receipt["matched_archives_sha256"] = selection
        receipt["matched_archive_support"] = [{"summary_sha256": a.summary_sha256,
            "geometry_vectors": len(a.geometry_residuals_m), "complete_feature_rows": len(a.conditions),
            "complete_sequences": len(a.arrays["conditioned_sequence_offsets"]) - 1,
            "valid_transitions": len(a.conditions) - len(a.arrays["conditioned_sequence_offsets"]) + 1}
            for a in view.archives]
        receipt["stages"][stage] = 0
        receipt.update(status="complete_locked_development_exports", exit_code=0, latest_registry_sha256=context.registry_sha256)
    except (Exception, KeyboardInterrupt) as exc:
        receipt["exit_code"] = 130 if isinstance(exc, KeyboardInterrupt) else 2
        receipt["failures"].append({"stage": stage, "failure_code": getattr(exc, "code", type(exc).__name__)})
        print("Stopped at", stage, ":", str(exc), flush=True)
    try:
        unchanged()
        locked.load_context(**context_args, descendants=chain)
        receipt["input_integrity_verified"] = True
    except (Exception, KeyboardInterrupt) as exc:
        receipt.update(status="failed_preserve_attempt", exit_code=2)
        receipt["failures"].append({"stage": "postflight_integrity", "failure_code": getattr(exc, "code", type(exc).__name__)})
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write(attempt / "run_receipt.json", receipt)
    package(result, roots)
    print("Result ZIP:", result, "SHA-256:", sha(result), flush=True)
    return receipt["exit_code"]
