# v0.19.11 exact EDP compatibility: apply, test and review

Date: 2026-10-15. This is a **new implementation/amendment PR** on merged
PR #35 `4cf0af37ffad05e34b632571ec271485d6de50c3`.
Read [the proposed amendment](edp_descriptor_compatibility_v01911.md).
No private scientific command is issued before focused amendment/code GO,
new-head Python 3.10/3.12 CI and merge. Do not reapply PR #35 or rerun its pilot.

The delivered ZIP contains a numbered source patch plus private audit evidence.
Keep the bundle in Downloads; apply only the numbered patch. Its `evidence/`
ZIPs and validation files are review material, not files to add to Git.
This README is byte-identical to the public runbook. BASE/EXPECTED_TREE metadata
avoid embedding the runbook's own circular tree hash.

## 1. Apply and test

Save `mpr_v01911_edp_descriptor_compatibility_a1.zip` in `~/Downloads/MPR/`.
This selects the right feature branch from main or a matching local/remote
branch. A clean base branch after `git am --abort` can retry. If origin already
has the matching correction, a local base branch fast-forwards to it.
Unrelated work is preserved; no reset or force-push is used.

```bash
(
  set -euo pipefail
  mpr_downloads="$HOME/Downloads/MPR"
  mpr_zip="$mpr_downloads/mpr_v01911_edp_descriptor_compatibility_a1.zip"
  mpr_bundle="$mpr_downloads/mpr_v01911_edp_descriptor_compatibility_a1"
  mpr_repo="$HOME/PycharmProjects/MPR"
  mpr_branch="feature/v0.19.11-edp-descriptor-compatibility"
  mpr_base="4cf0af37ffad05e34b632571ec271485d6de50c3"
  fail() { printf 'Stop: %s\n' "$1" >&2; exit 1; }
  [[ -d "$mpr_repo/.git" ]] || fail "repository directory is missing"
  [[ -f "$mpr_repo/.venv/bin/activate" ]] || fail "virtual environment is missing"
  [[ -f "$mpr_zip" && ! -L "$mpr_zip" ]] || fail "downloaded ZIP is missing or a symlink"
  if [[ ! -e "$mpr_bundle" ]]; then
    unzip "$mpr_zip" -d "$mpr_downloads"
  fi
  [[ -d "$mpr_bundle" && ! -L "$mpr_bundle" ]] || fail "bundle directory is invalid"
  unzip -p "$mpr_zip" mpr_v01911_edp_descriptor_compatibility_a1/SHA256SUMS | cmp -s - "$mpr_bundle/SHA256SUMS" || fail "ZIP and extracted manifests differ; preserve both copies"
  (cd "$mpr_bundle" && sha256sum -c SHA256SUMS)
  [[ "$(cat "$mpr_bundle/BASE_COMMIT.txt")" == "$mpr_base" ]] || fail "bundle base differs"
  mpr_tree="$(cat "$mpr_bundle/EXPECTED_TREE.txt")"
  [[ "$mpr_tree" =~ ^[0-9a-f]{40}$ ]] || fail "bundle expected tree is invalid"
  [[ -f "$mpr_bundle/patches/0001-edp-descriptor-compatibility.patch" ]] || fail "numbered patch is missing"
  cd "$mpr_repo"
  [[ ! -d "$(git rev-parse --git-path rebase-apply)" ]] || fail "git am/rebase is in progress; finish or abort it first"
  [[ ! -d "$(git rev-parse --git-path rebase-merge)" ]] || fail "rebase is in progress; finish or abort it first"
  [[ -z "$(git status --porcelain)" ]] || fail "preserve or commit existing changes first"
  git fetch origin
  if git show-ref --verify --quiet "refs/heads/$mpr_branch"; then
    git switch "$mpr_branch"
    if [[ "$(git rev-parse HEAD)" == "$mpr_base" ]] && git show-ref --verify --quiet "refs/remotes/origin/$mpr_branch"; then
      if [[ "$(git rev-parse "origin/$mpr_branch^{tree}")" == "$mpr_tree" && "$(git rev-parse "origin/$mpr_branch^")" == "$mpr_base" ]]; then
        git merge --ff-only "origin/$mpr_branch"
      fi
    fi
  elif git show-ref --verify --quiet "refs/remotes/origin/$mpr_branch"; then
    git switch --track -c "$mpr_branch" "origin/$mpr_branch"
  else
    git switch main
    git pull --ff-only origin main
    [[ "$(git rev-parse HEAD)" == "$mpr_base" ]] || fail "main differs from reviewed patch base; preserve the output"
    git switch -c "$mpr_branch"
  fi
  if [[ "$(git rev-parse HEAD)" == "$mpr_base" ]]; then
    git am "$mpr_bundle/patches/0001-edp-descriptor-compatibility.patch"
  fi
  [[ "$(git rev-parse HEAD^{tree})" == "$mpr_tree" ]] || fail "implementation tree differs; preserve the unpushed branch"
  [[ "$(git rev-parse HEAD^)" == "$mpr_base" ]] || fail "implementation parent differs; preserve the unpushed branch"
  git diff --name-only "$mpr_base" HEAD | LC_ALL=C sort | cmp -s - "$mpr_bundle/FILES_CHANGED.txt" || fail "changed-file list differs"
  mpr_source_changes="$(git diff --name-only "$mpr_base" HEAD -- src)"
  [[ "$mpr_source_changes" == $'src/lane_residuals/domain/path_source_probe.py\nsrc/lane_residuals/io/bounded_recording_readiness.py' ]] || fail "unexpected source path changed"
  git diff --quiet "$mpr_base" HEAD -- src/lane_residuals/legacy docs/output_contracts.md docs/independent_outing_schema_v2_amendment.md docs/generic_recording_readiness_v01910_draft.md docs/generic_recording_readiness_v01910_a2_review.md docs/generic_recording_readiness_v01910_a3_review.md docs/generic_recording_readiness_v01910_a4_review.md config pyproject.toml .github || fail "protected history, contracts, dependencies or configuration changed"
  source .venv/bin/activate
  export PYTHONPATH=src:. MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
  git diff --check "$mpr_base" HEAD
  python -m compileall -q src tests scripts/benchmarks
  python - <<'PYTHON'
import sys, unittest
result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests', top_level_dir='.'))
if not result.wasSuccessful() or result.testsRun != 713 or len(result.skipped) != 2:
    sys.exit('Stop: expected 713 successful tests with exactly two existing skips')
PYTHON
  [[ -z "$(git status --porcelain)" ]] || fail "working tree changed during verification"
  [[ "$(git branch --show-current)" == "$mpr_branch" ]] || fail "branch changed during verification"
  printf 'Compatibility candidate applied and tests passed. Next: section 2.\n'
)
```

If patch application fails, preserve its output and run `git am --abort` in
the repository. A clean base branch can retry the intended bundle. If a later
source/tree/test check fails, preserve the unpushed branch; do not reset/force it.
For differing ZIP/extracted manifests, preserve/rename the extracted directory
before retrying the intended ZIP. No dependency change is needed; missing MCAP
extras or extra skips are verification failures, not permission to skip tests.

## 2. Push and open a new PR

After section 1 succeeds, run this block, which selects the correct branch.

```bash
(
  set -euo pipefail
  cd "$HOME/PycharmProjects/MPR"
  mpr_branch="feature/v0.19.11-edp-descriptor-compatibility"
  mpr_base="4cf0af37ffad05e34b632571ec271485d6de50c3"
  mpr_bundle="$HOME/Downloads/MPR/mpr_v01911_edp_descriptor_compatibility_a1"
  mpr_zip="$HOME/Downloads/MPR/mpr_v01911_edp_descriptor_compatibility_a1.zip"
  fail() { printf 'Stop: %s\n' "$1" >&2; exit 1; }
  [[ -d "$mpr_bundle" && ! -L "$mpr_bundle" ]] || fail "apply/test section 1 first"
  [[ -f "$mpr_zip" && ! -L "$mpr_zip" ]] || fail "downloaded ZIP is missing or a symlink"
  unzip -p "$mpr_zip" mpr_v01911_edp_descriptor_compatibility_a1/SHA256SUMS | cmp -s - "$mpr_bundle/SHA256SUMS" || fail "ZIP and extracted manifests differ"
  (cd "$mpr_bundle" && sha256sum -c SHA256SUMS)
  [[ "$(cat "$mpr_bundle/BASE_COMMIT.txt")" == "$mpr_base" ]] || fail "bundle base differs"
  mpr_tree="$(cat "$mpr_bundle/EXPECTED_TREE.txt")"
  [[ "$mpr_tree" =~ ^[0-9a-f]{40}$ ]] || fail "bundle expected tree is invalid"
  [[ -z "$(git status --porcelain)" ]] || fail "preserve or commit existing changes first"
  git show-ref --verify --quiet "refs/heads/$mpr_branch" || fail "apply/test section 1 first"
  [[ "$(git rev-parse "$mpr_branch^{tree}")" == "$mpr_tree" ]] || fail "implementation tree differs"
  [[ "$(git rev-parse "$mpr_branch^")" == "$mpr_base" ]] || fail "implementation parent differs"
  git switch "$mpr_branch"
  git push -u origin "$mpr_branch"
  git rev-parse HEAD
)
```

Open a **new PR into main** using `PR_DESCRIPTION.md`. PR #35 remains merged.
Give Claude the new PR link, pushed head, Actions run link,
`CLAUDE_REVIEW_PROMPT.md` and this actual ZIP. It contains the original private
result/descriptor evidence so byte-level conformance can be checked directly.
The review must assess the explicit amendment and implementation together.
The original 703-test PR #35 CI does not verify this new source.

## 3. After GO, exact-head CI and merge

Return the focused review and new Actions link. Once accepted and merged,
prepare one new v0.19.11 counts-only successor with a fresh output and local
scratch, the original registration/inventory/decode inputs, and a private receipt
retaining the failed v0.19.10 report hash. Do not rerun the old pilot or completed
predecessors. Actual geometry/features/sequences remain unmeasured here.
No real data command, export, fit, split assignment or raw retirement is issued
by this candidate. The next data consumer after measured readiness is generic
numeric export and strict archive validation, followed by evidenced sessions
and the existing model/data gates.
