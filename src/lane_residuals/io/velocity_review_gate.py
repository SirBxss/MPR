"""Read-only GitHub evidence and local merged-source checks before raw access."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen

from .velocity_summary_probe import pinned_json, require

REPOSITORY = "SirBxss/MPR"
JOBS = {"unit-tests (3.10, current)", "unit-tests (3.12, current)", "unit-tests (3.12, frozen-reader)"}


def runtime_sha256(project):
    source = Path(project)/"src"
    digest = hashlib.sha256()
    for path in sorted(source.rglob("*.py")):
        digest.update(path.relative_to(source).as_posix().encode()+b"\0"+path.read_bytes()+b"\0")
    return digest.hexdigest()


def git(project, *arguments):
    return subprocess.check_output(["git", *arguments], cwd=project, timeout=15, text=True).strip()


def api(endpoint):
    # Public repository: no credentials or third-party service is needed.
    request = Request("https://api.github.com/repos/"+REPOSITORY+"/"+endpoint,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "MPR-read-only-source-gate"})
    with urlopen(request, timeout=15) as response:
        raw = response.read(5*1024**2+1)
    require(len(raw) <= 5*1024**2, "pilot_github_response_budget")
    return json.loads(raw)


def source_evidence(project, expected_runtime, request_sha256):
    """Actual branch, remote main, merged PR, equal tree and all exact-head jobs."""
    project = Path(project).resolve(strict=True)
    require(git(project, "branch", "--show-current") == "main", "pilot_merged_main_required")
    require(not git(project, "status", "--porcelain"), "pilot_clean_worktree_required")
    commit = git(project, "rev-parse", "HEAD")
    tree = git(project, "rev-parse", "HEAD^{tree}")
    require(commit == git(project, "rev-parse", "refs/remotes/origin/main"), "pilot_local_origin_main_mismatch")
    require(runtime_sha256(project) == expected_runtime, "pilot_runtime_source_mismatch")
    remote = api("commits/main")
    require(remote["sha"] == commit and remote["commit"]["tree"]["sha"] == tree, "pilot_live_main_mismatch")
    pulls = api(f"commits/{commit}/pulls?per_page=10")
    merged = [p for p in pulls if p.get("merged_at") and p.get("merge_commit_sha") == commit]
    require(len(merged) == 1, "pilot_unique_merged_pr_required")
    pr = merged[0]
    head = pr["head"]["sha"]
    tested = api("commits/"+head)
    require(tested["commit"]["tree"]["sha"] == tree, "pilot_reviewed_head_tree_mismatch")
    runs = api(f"actions/runs?head_sha={head}&event=pull_request&per_page=20")["workflow_runs"]
    runs = [r for r in runs if r["head_sha"] == head and r.get("path") == ".github/workflows/tests.yml"]
    require(bool(runs), "pilot_exact_head_ci_missing")
    # A newer failed/running attempt cannot be hidden behind an older success.
    run = max(runs, key=lambda r: (r["id"], r.get("run_attempt", 1)))
    require(run["status"] == "completed" and run["conclusion"] == "success", "pilot_exact_head_ci_not_success")
    jobs = api(f"actions/runs/{run['id']}/jobs?filter=latest&per_page=100")["jobs"]
    selected = [j for j in jobs if j["name"] in JOBS]
    require(len(selected) == 3 and {j["name"] for j in selected} == JOBS and
        all(j["status"] == "completed" and j["conclusion"] == "success" for j in selected), "pilot_three_ci_jobs_required")
    return {"repository": REPOSITORY, "commit": commit, "tree": tree, "reviewed_head": head,
        "pr_number": pr["number"], "ci_run_id": run["id"], "ci_run_attempt": run.get("run_attempt", 1),
        "ci_jobs": sorted([{"id": j["id"], "name": j["name"], "conclusion": j["conclusion"]} for j in selected], key=lambda j: j["name"]),
        "runtime_sha256": expected_runtime, "request_sha256": request_sha256}


def seal(project, expected_runtime, request_sha256, review_note, output, *, independent_review_go=False):
    require(independent_review_go is True, "pilot_owner_review_go_required")
    review_note, output = Path(review_note).resolve(strict=True), Path(output).absolute()
    with review_note.open("rb") as stream:
        raw = stream.read(256*1024+1)
    require(0 < len(raw) <= 256*1024, "pilot_review_note_budget")
    raw.decode("utf-8")
    require(not output.exists() and not output.is_symlink(), "pilot_gate_must_be_new")
    evidence = source_evidence(project, expected_runtime, request_sha256)
    evidence.update(independent_review_go_owner_attested=True, review_note_path_private=str(review_note),
        review_note_sha256=hashlib.sha256(raw).hexdigest(), revision="v0.19.20-source-gate-a1")
    with output.open("x") as stream:
        stream.write(json.dumps(evidence, indent=2, sort_keys=True)+"\n")
    return hashlib.sha256(output.read_bytes()).hexdigest()


def validate(project, gate_path, gate_sha256, expected_runtime, request_sha256):
    gate = pinned_json(gate_path, gate_sha256)
    require(gate.get("revision") == "v0.19.20-source-gate-a1" and
        gate.get("independent_review_go_owner_attested") is True, "pilot_review_gate_required")
    with Path(gate["review_note_path_private"]).open("rb") as stream:
        note = stream.read(256*1024+1)
    require(len(note) <= 256*1024, "pilot_review_note_budget")
    require(hashlib.sha256(note).hexdigest() == gate["review_note_sha256"], "pilot_review_note_changed")
    fresh = source_evidence(project, expected_runtime, request_sha256)
    require(all(gate.get(k) == v for k, v in fresh.items()), "pilot_gate_source_or_ci_changed")
    return gate
