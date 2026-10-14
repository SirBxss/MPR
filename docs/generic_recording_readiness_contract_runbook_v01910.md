# PR #34 a4: canonical application and review runbook

Date: 2026-10-14. These are the complete delivered README commands, public
so the reviewer can inspect them in this PR. This document implements no
scientific CLI. a3 has NO-GO only for R1-C; a4 is a proposed documentation correction.
Read [the amendment record](generic_recording_readiness_v01910_a4_review.md) and
[the binding draft](generic_recording_readiness_v01910_draft.md).

## 1. Scope and review state

The correction requires the confidence declaration used by three fixed causal
features: missing binding is unsupported; invalid values on a bound field remain
data. It excludes maps from repeated-message bindings and hardens these commands.
EDP generation, other accepted a3 bindings and a2 B2–B5 policies stay fixed.
No implementation, private run, numeric export, real fit or raw retirement.

Codex verified [a3 CI](https://github.com/SirBxss/MPR/actions/runs/38427830200):
Python 3.10/3.12 each 650 run/648 pass/two skips, both checking merge `6a2dc0b`
(parents `12ddee6` + `1548382`, exact reviewed tree). That is not a4 CI or GO.
Apply this bundle to the **same PR #34 branch**, not main. Preserve prior inputs
and results. Only the numbered Markdown patch enters Git; review/delivery files
and result ZIPs stay outside Git.

## 2. Apply and test

Save `mpr_pr34_bounded_readiness_contract_a4.zip` in `~/Downloads/MPR/`.
The bundle's checksum manifest covers its numbered patch, exact base and expected
tree. Snapshot-specific tree/patch hashes are not hard-coded in this runbook:
they would depend on the runbook's own committed bytes. The block validates
that metadata, exact PR parent, clean state and exact allowed Markdown paths.
It compares the downloaded ZIP manifest with any extracted directory before
reuse, accepts an already applied correction before or after a fast-forward,
selects the PR branch and stops on unrelated changes without resetting them.

```bash
(
  set -euo pipefail
  mpr_downloads="$HOME/Downloads/MPR"
  mpr_zip="$mpr_downloads/mpr_pr34_bounded_readiness_contract_a4.zip"
  mpr_bundle="$mpr_downloads/mpr_pr34_bounded_readiness_contract_a4"
  mpr_repo="$HOME/PycharmProjects/MPR"
  mpr_branch="docs/v0.19.10-bounded-readiness-contract"
  mpr_base="1548382fe8c6b5dcc228441ac82ec16ed0e1fb2f"
  mpr_tree=""
  fail() { printf 'Stop: %s\n' "$1" >&2; exit 1; }
  [[ -d "$mpr_repo/.git" ]] || fail "repository directory is missing"
  [[ -f "$mpr_repo/.venv/bin/activate" ]] || fail "virtual environment is missing"
  [[ -f "$mpr_zip" && ! -L "$mpr_zip" ]] || fail "downloaded ZIP is missing or a symlink"
  if [[ ! -e "$mpr_bundle" ]]; then
    unzip "$mpr_zip" -d "$mpr_downloads"
  fi
  [[ -d "$mpr_bundle" && ! -L "$mpr_bundle" ]] || fail "bundle directory is invalid"
  unzip -p "$mpr_zip" mpr_pr34_bounded_readiness_contract_a4/SHA256SUMS | cmp -s - "$mpr_bundle/SHA256SUMS" || fail "ZIP and extracted manifests differ; preserve both copies"
  cd "$mpr_bundle"
  sha256sum -c SHA256SUMS
  [[ "$(cat BASE_COMMIT.txt)" == "$mpr_base" ]] || fail "bundle base differs"
  mpr_tree="$(cat EXPECTED_TREE.txt)"
  [[ "$mpr_tree" =~ ^[0-9a-f]{40}$ ]] || fail "bundle expected tree is invalid"
  [[ -f patches/0001-require-confidence-binding-and-harden-runbook.patch ]] || fail "numbered correction patch is missing"
  cd "$mpr_repo"
  [[ -z "$(git status --porcelain)" ]] || fail "preserve or commit existing changes first"
  git fetch origin
  if git show-ref --verify --quiet "refs/heads/$mpr_branch"; then
    git switch "$mpr_branch"
  else
    git switch --track -c "$mpr_branch" "origin/$mpr_branch"
  fi
  mpr_matches() {
    [[ "$(git rev-parse HEAD^{tree})" == "$mpr_tree" && "$(git rev-parse HEAD^)" == "$mpr_base" ]]
  }
  if mpr_matches; then
    printf 'Matching correction already applied; verifying it again.\n'
  else
    git pull --ff-only origin "$mpr_branch"
    if mpr_matches; then
      printf 'Matching correction obtained by fast-forward; verifying it.\n'
    else
      [[ "$(git rev-parse HEAD)" == "$mpr_base" ]] || fail "PR branch differs from the reviewed head; preserve the output"
      git am "$mpr_bundle/patches/0001-require-confidence-binding-and-harden-runbook.patch"
    fi
  fi
  [[ "$(git rev-parse HEAD^{tree})" == "$mpr_tree" ]] || fail "corrected tree differs"
  [[ "$(git rev-parse HEAD^)" == "$mpr_base" ]] || fail "corrected parent differs"
  while IFS= read -r mpr_changed; do
    case "$mpr_changed" in
      AGENTS.md|README.md|docs/architecture.md|docs/commands.md|docs/current_status.md|docs/modeling_plan.md|docs/development_recording_decode_followup_20261013.md|docs/generic_recording_readiness_v01910_draft.md|docs/generic_recording_readiness_contract_runbook_v01910.md|docs/generic_recording_readiness_v01910_a4_review.md) ;;
      *) fail "correction changes an unapproved path: $mpr_changed" ;;
    esac
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

If anything stops, preserve the output and changes. If `git am` specifically
reports patch application failure, run `git am --abort` from the repository to
restore the pre-apply state, then return the failure output. For a ZIP/extracted
manifest mismatch, preserve/rename the extracted folder before trying the
intended ZIP again. Do not reset or force push.

## 3. Push to the same PR

Run only after section 2 prints its success message. It selects the correct
branch even if you returned to main between steps.

```bash
(
  set -euo pipefail
  cd "$HOME/PycharmProjects/MPR"
  mpr_branch="docs/v0.19.10-bounded-readiness-contract"
  mpr_base="1548382fe8c6b5dcc228441ac82ec16ed0e1fb2f"
  mpr_bundle="$HOME/Downloads/MPR/mpr_pr34_bounded_readiness_contract_a4"
  mpr_zip="$HOME/Downloads/MPR/mpr_pr34_bounded_readiness_contract_a4.zip"
  mpr_tree=""
  fail() { printf 'Stop: %s\n' "$1" >&2; exit 1; }
  [[ -d "$mpr_bundle" && ! -L "$mpr_bundle" ]] || fail "apply and test section 2 first"
  [[ -f "$mpr_zip" && ! -L "$mpr_zip" ]] || fail "downloaded ZIP is missing or a symlink"
  unzip -p "$mpr_zip" mpr_pr34_bounded_readiness_contract_a4/SHA256SUMS | cmp -s - "$mpr_bundle/SHA256SUMS" || fail "ZIP and extracted manifests differ; preserve both copies"
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
the delivered CLAUDE_REREVIEW_PROMPT.md, the original a3 review and the PR link.
The full application text is now in this public runbook; a separate README
attachment is optional because the delivered README has identical contents.
Include the new exact head from `git rev-parse HEAD` and its Actions run link.
Focused R1-C/map-clarification/runbook delta GO and new-head Python 3.10/3.12 CI precede merge or
implementation. Return the review and PR link for independent verification.

## 4. Implementation remains after contract acceptance

After contract GO/CI/merge: implement/test/review/CI and merge the implementation,
then issue one counts-only private pilot command with fresh output/scratch paths.
The current registered raw file and all old reports remain unchanged. Generic
numeric archives/validation, private session catalogue, orchestration and verified
raw retirement are later consumers. No collection-wide download or real fit now.
