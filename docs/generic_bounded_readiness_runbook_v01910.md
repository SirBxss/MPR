# v0.19.10 bounded readiness: implementation application and review runbook

Date: 2026-10-15. These complete commands are also the delivered README.
PR #34's contract is accepted and merged. This is a **new implementation PR**,
with implementation review/new-head CI pending. Read
[the implementation record](generic_bounded_readiness_v01910.md) and
[the data-completion handoff](generic_pipeline_data_completion_20261015.md).

## 1. Scope and result

The patch adds the counts-only bounded scientific consumer and tests, retaining
accepted science and historical outputs. It measures H100/SENSOR geometry,
causal-input rejection and contiguous support on newly registered files. No
private MCAP was accessed by the agent. The local suite and maximum-budget
staging evidence are in the bundle; exact-head Python 3.10/3.12 CI and focused
implementation GO precede merge and the one fresh private pilot.

The patch base is merged PR #34, `0f2950e2b76b823fabea0b67309b268afe205806`.
Snapshot tree/patch hashes live in the bundle metadata to avoid circular hashes
from embedding the runbook's own tree. This is not the old a4 contract patch.

## 2. Apply and test

Save `mpr_v01910_bounded_readiness_implementation_a1.zip` in `~/Downloads/MPR/`.
The block extracts it if necessary, checks ZIP/extracted manifest agreement,
selects/creates the implementation branch and verifies exact parent/tree.
It supports a matching correction already applied or fetched from origin.
Unrelated local changes/commits are preserved; a differing branch/base stops.

```bash
(
  set -euo pipefail
  mpr_downloads="$HOME/Downloads/MPR"
  mpr_zip="$mpr_downloads/mpr_v01910_bounded_readiness_implementation_a1.zip"
  mpr_bundle="$mpr_downloads/mpr_v01910_bounded_readiness_implementation_a1"
  mpr_repo="$HOME/PycharmProjects/MPR"
  mpr_branch="feature/v0.19.10-bounded-recording-readiness"
  mpr_base="0f2950e2b76b823fabea0b67309b268afe205806"
  fail() { printf 'Stop: %s\n' "$1" >&2; exit 1; }
  [[ -d "$mpr_repo/.git" ]] || fail "repository directory is missing"
  [[ -f "$mpr_repo/.venv/bin/activate" ]] || fail "virtual environment is missing"
  [[ -f "$mpr_zip" && ! -L "$mpr_zip" ]] || fail "downloaded ZIP is missing or a symlink"
  if [[ ! -e "$mpr_bundle" ]]; then
    unzip "$mpr_zip" -d "$mpr_downloads"
  fi
  [[ -d "$mpr_bundle" && ! -L "$mpr_bundle" ]] || fail "bundle directory is invalid"
  unzip -p "$mpr_zip" mpr_v01910_bounded_readiness_implementation_a1/SHA256SUMS | cmp -s - "$mpr_bundle/SHA256SUMS" || fail "ZIP and extracted manifests differ; preserve both copies"
  (cd "$mpr_bundle" && sha256sum -c SHA256SUMS)
  [[ "$(cat "$mpr_bundle/BASE_COMMIT.txt")" == "$mpr_base" ]] || fail "bundle base differs"
  mpr_tree="$(cat "$mpr_bundle/EXPECTED_TREE.txt")"
  [[ "$mpr_tree" =~ ^[0-9a-f]{40}$ ]] || fail "bundle expected tree is invalid"
  [[ -f "$mpr_bundle/patches/0001-bounded-recording-readiness.patch" ]] || fail "numbered patch is missing"
  cd "$mpr_repo"
  [[ -z "$(git status --porcelain)" ]] || fail "preserve or commit existing changes first"
  git fetch origin
  if git show-ref --verify --quiet "refs/heads/$mpr_branch"; then
    git switch "$mpr_branch"
  elif git show-ref --verify --quiet "refs/remotes/origin/$mpr_branch"; then
    git switch --track -c "$mpr_branch" "origin/$mpr_branch"
  else
    git switch main
    git pull --ff-only origin main
    [[ "$(git rev-parse HEAD)" == "$mpr_base" ]] || fail "main differs from the reviewed patch base; preserve the output"
    git switch -c "$mpr_branch"
    git am "$mpr_bundle/patches/0001-bounded-recording-readiness.patch"
  fi
  [[ "$(git rev-parse HEAD^{tree})" == "$mpr_tree" ]] || fail "implementation tree differs; preserve the unpushed branch"
  [[ "$(git rev-parse HEAD^)" == "$mpr_base" ]] || fail "implementation parent differs; preserve the unpushed branch"
  git diff --quiet "$mpr_base" HEAD -- src/lane_residuals/domain/geometry_validation.py src/lane_residuals/domain/pairing.py src/lane_residuals/domain/conditional_features.py src/lane_residuals/domain/motion.py src/lane_residuals/domain/path_source_probe.py src/lane_residuals/domain/alignment.py src/lane_residuals/domain/exploratory_residuals.py src/lane_residuals/legacy docs/output_contracts.md docs/generic_recording_readiness_v01910_draft.md docs/generic_recording_readiness_v01910_a2_review.md docs/generic_recording_readiness_v01910_a3_review.md docs/generic_recording_readiness_v01910_a4_review.md || fail "protected scientific arithmetic or historical contract changed"
  source .venv/bin/activate
  python -m pip install -e '.[test,mcap]'
  git diff --check "$mpr_base" HEAD
  python -m compileall -q src tests scripts/benchmarks
  python - <<'PYTHON'
import sys, unittest
result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests', top_level_dir='.'))
if not result.wasSuccessful() or result.testsRun != 700 or len(result.skipped) != 2:
    sys.exit('Stop: expected 700 successful tests with exactly two existing skips')
PYTHON
  [[ -z "$(git status --porcelain)" ]] || fail "working tree changed during verification"
  [[ "$(git branch --show-current)" == "$mpr_branch" ]] || fail "branch changed during verification"
  printf 'Implementation applied and tests passed. Next: section 3.\n'
)
```

If anything stops, preserve the output and branch. If `git am` reports patch
application failure, run `git am --abort` in the repository to return to its
pre-apply state. If a later tree/parent/test guard stops, the unpushed branch
preserves the attempted implementation for diagnosis; do not force/reset it.
For differing ZIP/extracted manifests, preserve/rename the extracted folder
before retrying the intended ZIP.

## 3. Push and open the implementation PR

Run only after section 2 prints its success message. This block selects the
correct implementation branch even if you returned to main.

```bash
(
  set -euo pipefail
  cd "$HOME/PycharmProjects/MPR"
  mpr_branch="feature/v0.19.10-bounded-recording-readiness"
  mpr_base="0f2950e2b76b823fabea0b67309b268afe205806"
  mpr_bundle="$HOME/Downloads/MPR/mpr_v01910_bounded_readiness_implementation_a1"
  mpr_zip="$HOME/Downloads/MPR/mpr_v01910_bounded_readiness_implementation_a1.zip"
  fail() { printf 'Stop: %s\n' "$1" >&2; exit 1; }
  [[ -d "$mpr_bundle" && ! -L "$mpr_bundle" ]] || fail "apply/test section 2 first"
  [[ -f "$mpr_zip" && ! -L "$mpr_zip" ]] || fail "downloaded ZIP is missing or a symlink"
  unzip -p "$mpr_zip" mpr_v01910_bounded_readiness_implementation_a1/SHA256SUMS | cmp -s - "$mpr_bundle/SHA256SUMS" || fail "ZIP and extracted manifests differ"
  (cd "$mpr_bundle" && sha256sum -c SHA256SUMS)
  [[ "$(cat "$mpr_bundle/BASE_COMMIT.txt")" == "$mpr_base" ]] || fail "bundle base differs"
  mpr_tree="$(cat "$mpr_bundle/EXPECTED_TREE.txt")"
  [[ "$mpr_tree" =~ ^[0-9a-f]{40}$ ]] || fail "bundle expected tree is invalid"
  [[ -z "$(git status --porcelain)" ]] || fail "preserve or commit existing changes first"
  git show-ref --verify --quiet "refs/heads/$mpr_branch" || fail "apply/test section 2 first"
  [[ "$(git rev-parse "$mpr_branch^{tree}")" == "$mpr_tree" ]] || fail "implementation tree differs"
  [[ "$(git rev-parse "$mpr_branch^")" == "$mpr_base" ]] || fail "implementation parent differs"
  git switch "$mpr_branch"
  git push -u origin "$mpr_branch"
  git rev-parse HEAD
)
```

Open a **new PR into main** using the included PR_DESCRIPTION.md. PR #34 is
already merged. Give Claude the new PR link, pushed head, Actions run link,
CLAUDE_REVIEW_PROMPT.md and the supplied ZIP so the delivered bytes can be
checked. The public runbook contains the identical README commands.

## 4. After implementation acceptance

Obtain focused implementation GO and exact-head Python 3.10/3.12 CI, then
merge. The post-merge one-file counts-only pilot command will use a fresh
output/scratch directory and the existing immutable registration/inventory/
decode evidence. Preserve the currently registered raw path and old outputs.
No completed stage or old deferred `audit` is the next private command.

Return the counts report/receipt to assess geometry, feature and contiguous
support. That determines the next incremental data acquisition and generic
numeric exporter/validator scope. Raw retirement and real fits retain their
separate gates. No additional collection download is needed to run this pilot.
