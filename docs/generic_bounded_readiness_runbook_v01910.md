# PR #35 bounded readiness: a2 correction runbook

Date: 2026-10-15. Apply this delta to the existing PR #35 branch. Its exact
base is reviewed head `b11459adea73452f02b10f5acba8cf6f99f4473e`, tree
`16acf58fa565650c6a2ee1a3fd5bcec4ef9e28b0`. PR #34 remains merged; PR #35
is open. Do not reapply the original implementation or open a second PR.

Read [the independent evaluation](generic_bounded_readiness_v01910_a2_review.md).
B-1 maps the existing ambiguous projection rejection to common H100. O-1 adds
literal-code coverage, O-3 releases the last streamed record before matching,
and O-2 makes clean base-branch retry possible after an aborted patch attempt.
Scientific arithmetic, accepted a4 contract and resource limits are unchanged.
This README and the delivered README are byte-identical. Snapshot tree/hash
values are in bundle metadata, avoiding a circular hash of this document.

## 1. Apply and test the correction

Save `mpr_v01910_bounded_readiness_review_a2.zip` in `~/Downloads/MPR/`.
The block handles starting on main, the existing local or remote PR branch,
and the identical correction already applied. It preserves unrelated work.

```bash
(
  set -euo pipefail
  mpr_downloads="$HOME/Downloads/MPR"
  mpr_zip="$mpr_downloads/mpr_v01910_bounded_readiness_review_a2.zip"
  mpr_bundle="$mpr_downloads/mpr_v01910_bounded_readiness_review_a2"
  mpr_repo="$HOME/PycharmProjects/MPR"
  mpr_branch="feature/v0.19.10-bounded-recording-readiness"
  mpr_base="b11459adea73452f02b10f5acba8cf6f99f4473e"
  fail() { printf 'Stop: %s\n' "$1" >&2; exit 1; }
  [[ -d "$mpr_repo/.git" ]] || fail "repository directory is missing"
  [[ -f "$mpr_repo/.venv/bin/activate" ]] || fail "virtual environment is missing"
  [[ -f "$mpr_zip" && ! -L "$mpr_zip" ]] || fail "downloaded ZIP is missing or a symlink"
  if [[ ! -e "$mpr_bundle" ]]; then
    unzip "$mpr_zip" -d "$mpr_downloads"
  fi
  [[ -d "$mpr_bundle" && ! -L "$mpr_bundle" ]] || fail "bundle directory is invalid"
  unzip -p "$mpr_zip" mpr_v01910_bounded_readiness_review_a2/SHA256SUMS | cmp -s - "$mpr_bundle/SHA256SUMS" || fail "ZIP and extracted manifests differ; preserve both copies"
  (cd "$mpr_bundle" && sha256sum -c SHA256SUMS)
  [[ "$(cat "$mpr_bundle/BASE_COMMIT.txt")" == "$mpr_base" ]] || fail "bundle base differs"
  mpr_tree="$(cat "$mpr_bundle/EXPECTED_TREE.txt")"
  [[ "$mpr_tree" =~ ^[0-9a-f]{40}$ ]] || fail "bundle expected tree is invalid"
  [[ -f "$mpr_bundle/patches/0001-readiness-review-a2.patch" ]] || fail "numbered patch is missing"
  cd "$mpr_repo"
  [[ ! -d "$(git rev-parse --git-path rebase-apply)" ]] || fail "git am/rebase is in progress; preserve its output and finish or abort it first"
  [[ ! -d "$(git rev-parse --git-path rebase-merge)" ]] || fail "rebase is in progress; preserve its output and finish or abort it first"
  [[ -z "$(git status --porcelain)" ]] || fail "preserve or commit existing changes first"
  git fetch origin
  if git show-ref --verify --quiet "refs/heads/$mpr_branch"; then
    git switch "$mpr_branch"
  elif git show-ref --verify --quiet "refs/remotes/origin/$mpr_branch"; then
    git switch --track -c "$mpr_branch" "origin/$mpr_branch"
  else
    git cat-file -e "$mpr_base^{commit}" || fail "reviewed PR head is unavailable"
    git switch -c "$mpr_branch" "$mpr_base"
  fi
  if [[ "$(git rev-parse HEAD)" == "$mpr_base" ]]; then
    git am "$mpr_bundle/patches/0001-readiness-review-a2.patch"
  fi
  [[ "$(git rev-parse HEAD^{tree})" == "$mpr_tree" ]] || fail "correction tree differs; preserve the unpushed branch"
  [[ "$(git rev-parse HEAD^)" == "$mpr_base" ]] || fail "correction parent differs; preserve the unpushed branch"
  git diff --quiet "$mpr_base" HEAD -- src/lane_residuals/domain/geometry_validation.py src/lane_residuals/domain/pairing.py src/lane_residuals/domain/conditional_features.py src/lane_residuals/domain/motion.py src/lane_residuals/domain/path_source_probe.py src/lane_residuals/domain/alignment.py src/lane_residuals/domain/exploratory_residuals.py src/lane_residuals/io/mcap.py src/lane_residuals/io/independent_outing_intake.py src/lane_residuals/io/odometry.py src/lane_residuals/io/recording_decode_check.py src/lane_residuals/io/recording_readiness_resources.py src/lane_residuals/io/bounded_recording_readiness.py src/lane_residuals/workflows/bounded_recording_readiness.py src/lane_residuals/legacy docs/output_contracts.md docs/generic_recording_readiness_v01910_draft.md docs/generic_recording_readiness_v01910_a2_review.md docs/generic_recording_readiness_v01910_a3_review.md docs/generic_recording_readiness_v01910_a4_review.md || fail "protected science, reader, workflow or historical contract changed"
  source .venv/bin/activate
  python -m pip install -e '.[test,mcap]'
  git diff --check "$mpr_base" HEAD
  python -m compileall -q src tests scripts/benchmarks
  python - <<'PYTHON'
import sys, unittest
result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests', top_level_dir='.'))
if not result.wasSuccessful() or result.testsRun != 703 or len(result.skipped) != 2:
    sys.exit('Stop: expected 703 successful tests with exactly two existing skips')
PYTHON
  [[ -z "$(git status --porcelain)" ]] || fail "working tree changed during verification"
  [[ "$(git branch --show-current)" == "$mpr_branch" ]] || fail "branch changed during verification"
  printf 'PR #35 correction applied and tests passed. Next: section 2.\n'
)
```

If patch application fails, preserve the output and run `git am --abort` in
the repository. The PR branch remains at the exact reviewed base; rerunning
section 1 then applies the correct patch. No branch deletion/reset is needed.
If a tree/parent/test check fails after application, preserve the unpushed
branch and output for diagnosis. Do not force-push or reset unrelated work.
For mismatched ZIP/extracted manifests, preserve/rename the extracted folder
before retrying the intended ZIP.

## 2. Push the existing PR branch

Run after section 1 succeeds. This selects the correct branch even from main.

```bash
(
  set -euo pipefail
  cd "$HOME/PycharmProjects/MPR"
  mpr_branch="feature/v0.19.10-bounded-recording-readiness"
  mpr_base="b11459adea73452f02b10f5acba8cf6f99f4473e"
  mpr_bundle="$HOME/Downloads/MPR/mpr_v01910_bounded_readiness_review_a2"
  mpr_zip="$HOME/Downloads/MPR/mpr_v01910_bounded_readiness_review_a2.zip"
  fail() { printf 'Stop: %s\n' "$1" >&2; exit 1; }
  [[ -d "$mpr_bundle" && ! -L "$mpr_bundle" ]] || fail "apply/test section 1 first"
  [[ -f "$mpr_zip" && ! -L "$mpr_zip" ]] || fail "downloaded ZIP is missing or a symlink"
  unzip -p "$mpr_zip" mpr_v01910_bounded_readiness_review_a2/SHA256SUMS | cmp -s - "$mpr_bundle/SHA256SUMS" || fail "ZIP and extracted manifests differ"
  (cd "$mpr_bundle" && sha256sum -c SHA256SUMS)
  [[ "$(cat "$mpr_bundle/BASE_COMMIT.txt")" == "$mpr_base" ]] || fail "bundle base differs"
  mpr_tree="$(cat "$mpr_bundle/EXPECTED_TREE.txt")"
  [[ "$mpr_tree" =~ ^[0-9a-f]{40}$ ]] || fail "bundle expected tree is invalid"
  [[ -z "$(git status --porcelain)" ]] || fail "preserve or commit existing changes first"
  git show-ref --verify --quiet "refs/heads/$mpr_branch" || fail "apply/test section 1 first"
  [[ "$(git rev-parse "$mpr_branch^{tree}")" == "$mpr_tree" ]] || fail "correction tree differs"
  [[ "$(git rev-parse "$mpr_branch^")" == "$mpr_base" ]] || fail "correction parent differs"
  git switch "$mpr_branch"
  git push -u origin "$mpr_branch"
  git rev-parse HEAD
)
```

This updates [PR #35](https://github.com/SirBxss/MPR/pull/35). Give Claude the
pushed head, new Actions run link, `CLAUDE_REVIEW_PROMPT.md` and this ZIP
so the actual delivered bytes can be checked. Use the included replacement
PR description if desired. The 700-test CI on the old head does not verify a2.

## 3. After focused GO, new-head CI and merge

Return the new review and Actions link. Once a2 has focused GO and successful
Python 3.10/3.12 CI and is merged, issue one fresh counts-only private pilot on
the already registered recording. Use local scratch outside synchronisation
and backup jobs, with the unchanged 18.5-GiB initial/10-GiB runtime floors.
Do not repeat completed registration/inventory/decode checks or use the old
`audit` command. Preserve registered raw paths and all previous evidence.

The pilot measures SENSOR/H100, causal-input and sequence yield; it does not
construct numeric residuals. The next data consumer is generic numeric export
plus strict archive validation, followed by evidenced independent sessions and
locked splits before real fits. Actual yield and the required collection size
remain unknown. No additional download is needed for this pilot; raw retirement
retains its separate archive and exact-byte retrieval gates.
