# PR #34 a3: canonical application and review runbook

Date: 2026-10-13. These are the complete delivered README commands, public
so the reviewer can inspect them in this PR. This document implements no
scientific CLI. a2 has NO-GO only for R1; a3 is a proposed documentation correction.
Read [the amendment record](generic_recording_readiness_v01910_a3_review.md) and
[the binding draft](generic_recording_readiness_v01910_draft.md).

## 1. Scope and review state

The correction completes EDP/RLMB consumer-required descriptor paths, requires
explicit RLMB ego direct-drive-path geometry and classifies malformed declared
entries before payload science. EDP generation and a2 B2–B5 policies stay fixed.
No implementation, private run, numeric export, real fit or raw retirement.

Codex verified [a2 CI](https://github.com/SirBxss/MPR/actions/runs/38409957807):
Python 3.10/3.12 each 650 run/648 pass/two skips, both checking merge `9f6e5ac`
(parents `12ddee6` + `8d5c19e`, exact reviewed tree). That is not a3 CI or GO.
Apply this bundle to the **same PR #34 branch**, not main. Preserve prior inputs
and results. Only the numbered Markdown patch enters Git; review/delivery files
and result ZIPs stay outside Git.

## 2. Apply and test

Save `mpr_pr34_bounded_readiness_contract_a3.zip` in `~/Downloads/MPR/`.
The bundle's checksum manifest covers its numbered patch, exact base and expected
tree. Snapshot-specific tree/patch hashes are not hard-coded in this runbook:
they would depend on the runbook's own committed bytes. The block validates
that metadata, exact PR parent, clean state and documentation-only boundaries.
It reuses an extracted bundle or already applied matching correction, selects
the PR branch and stops on unrelated changes without resetting them.

```bash
(
  set -euo pipefail
  mpr_downloads="$HOME/Downloads/MPR"
  mpr_zip="$mpr_downloads/mpr_pr34_bounded_readiness_contract_a3.zip"
  mpr_bundle="$mpr_downloads/mpr_pr34_bounded_readiness_contract_a3"
  mpr_repo="$HOME/PycharmProjects/MPR"
  mpr_branch="docs/v0.19.10-bounded-readiness-contract"
  mpr_base="8d5c19e05b037a25f94e1a99e55ee9a5afd6cb9a"
  mpr_tree=""
  fail() { printf 'Stop: %s\n' "$1" >&2; exit 1; }
  [[ -d "$mpr_repo/.git" ]] || fail "repository directory is missing"
  [[ -f "$mpr_repo/.venv/bin/activate" ]] || fail "virtual environment is missing"
  if [[ ! -e "$mpr_bundle" ]]; then
    [[ -f "$mpr_zip" && ! -L "$mpr_zip" ]] || fail "downloaded ZIP is missing or a symlink"
    unzip "$mpr_zip" -d "$mpr_downloads"
  fi
  [[ -d "$mpr_bundle" && ! -L "$mpr_bundle" ]] || fail "bundle directory is invalid"
  cd "$mpr_bundle"
  sha256sum -c SHA256SUMS
  [[ "$(cat BASE_COMMIT.txt)" == "$mpr_base" ]] || fail "bundle base differs"
  mpr_tree="$(cat EXPECTED_TREE.txt)"
  [[ "$mpr_tree" =~ ^[0-9a-f]{40}$ ]] || fail "bundle expected tree is invalid"
  [[ -f patches/0001-complete-consumer-required-binding-contract.patch ]] || fail "numbered correction patch is missing"
  cd "$mpr_repo"
  [[ -z "$(git status --porcelain)" ]] || fail "preserve or commit existing changes first"
  git fetch origin
  if git show-ref --verify --quiet "refs/heads/$mpr_branch"; then
    git switch "$mpr_branch"
  else
    git switch --track -c "$mpr_branch" "origin/$mpr_branch"
  fi
  if [[ "$(git rev-parse HEAD^{tree})" == "$mpr_tree" && "$(git rev-parse HEAD^)" == "$mpr_base" ]]; then
    printf 'Matching correction already applied; verifying it again.\n'
  else
    git pull --ff-only origin "$mpr_branch"
    [[ "$(git rev-parse HEAD)" == "$mpr_base" ]] || fail "PR branch differs from the reviewed head; preserve the output"
    git am "$mpr_bundle/patches/0001-complete-consumer-required-binding-contract.patch"
  fi
  [[ "$(git rev-parse HEAD^{tree})" == "$mpr_tree" ]] || fail "corrected tree differs"
  [[ "$(git rev-parse HEAD^)" == "$mpr_base" ]] || fail "corrected parent differs"
  while IFS= read -r mpr_changed; do
    [[ "$mpr_changed" == *.md ]] || fail "correction changes a non-Markdown file"
  done < <(git diff --name-only "$mpr_base" HEAD)
  git diff --quiet "$mpr_base" HEAD -- src tests config scripts examples .github pyproject.toml docs/output_contracts.md docs/generic_recording_ingestion_v0196.md docs/generic_recording_decode_check_v0199.md docs/independent_outing_schema_v2_amendment.md || fail "scientific code or historical contract changed"
  source .venv/bin/activate
  python -m pip install -e '.[test,mcap]'
  git diff --check "$mpr_base" HEAD
  python -m compileall -q src tests
  python - <<'PYTHON'
import sys, unittest
result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests', top_level_dir='.'))
if not result.wasSuccessful() or result.testsRun != 650 or len(result.skipped) != 2:
    sys.exit('Stop: expected 650 successful tests with exactly two existing skips')
PYTHON
  [[ -z "$(git status --porcelain)" ]] || fail "working tree changed during verification"
  [[ "$(git branch --show-current)" == "$mpr_branch" ]] || fail "branch changed during verification"
  printf 'Correction applied and tests passed. Next: section 3.\n'
)
```

If anything stops, preserve the output and changes; do not reset or force push.

## 3. Push to the same PR

Run only after section 2 prints its success message. It selects the correct
branch even if you returned to main between steps.

```bash
(
  set -euo pipefail
  cd "$HOME/PycharmProjects/MPR"
  mpr_branch="docs/v0.19.10-bounded-readiness-contract"
  mpr_base="8d5c19e05b037a25f94e1a99e55ee9a5afd6cb9a"
  mpr_bundle="$HOME/Downloads/MPR/mpr_pr34_bounded_readiness_contract_a3"
  mpr_tree=""
  fail() { printf 'Stop: %s\n' "$1" >&2; exit 1; }
  [[ -d "$mpr_bundle" && ! -L "$mpr_bundle" ]] || fail "apply and test section 2 first"
  (cd "$mpr_bundle" && sha256sum -c SHA256SUMS)
  [[ "$(cat "$mpr_bundle/BASE_COMMIT.txt")" == "$mpr_base" ]] || fail "bundle base differs"
  mpr_tree="$(cat "$mpr_bundle/EXPECTED_TREE.txt")"
  [[ "$mpr_tree" =~ ^[0-9a-f]{40}$ ]] || fail "bundle expected tree is invalid"
  [[ -z "$(git status --porcelain)" ]] || fail "preserve or commit existing changes first"
  git show-ref --verify --quiet "refs/heads/$mpr_branch" || fail "apply and test section 2 first"
  [[ "$(git rev-parse "$mpr_branch^{tree}")" == "$mpr_tree" ]] || fail "corrected tree differs"
  [[ "$(git rev-parse "$mpr_branch^")" == "$mpr_base" ]] || fail "corrected parent differs"
  git switch "$mpr_branch"
  git push -u origin "$mpr_branch"
)
```

This updates [PR #34](https://github.com/SirBxss/MPR/pull/34); do not open another
PR. Use the delivered PR_DESCRIPTION.md to update its description. Give Claude
the delivered CLAUDE_REREVIEW_PROMPT.md, the original a2 review and the PR link.
The full application text is now in this public runbook; a separate README
attachment is optional because the delivered README has identical contents.
Include the new exact head from `git rev-parse HEAD` and its Actions run link.
Focused R1/runbook delta GO and new-head Python 3.10/3.12 CI precede merge or
implementation. Return the review and PR link for independent verification.

## 4. Implementation remains after contract acceptance

After contract GO/CI/merge: implement/test/review/CI and merge the implementation,
then issue one counts-only private pilot command with fresh output/scratch paths.
The current registered raw file and all old reports remain unchanged. Generic
numeric archives/validation, private session catalogue, orchestration and verified
raw retirement are later consumers. No collection-wide download or real fit now.
