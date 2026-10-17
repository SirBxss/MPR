# PR #37 a2: contract correction on the existing branch

Status: documentation-only delta on reviewed owner head `4c99b7b` (tree `1a7fc6d`).
PR #37 is open; **update that PR**, not a new one. Do not reapply the old three
patches or reopen merged PR #36. Read
[the review evaluation](generic_numeric_export_v01912_a2_review.md) and
[the revised contract](generic_numeric_export_v01912_contract.md).
This fourth commit adds no production code, model or private-data command.

## Apply from main or the existing feature branch

Save `mpr_v01912_numeric_export_contract_a2.zip` in `~/Downloads/MPR` and run the
whole block. An already extracted bundle is reused only after manifest checks.
Local changes, a different PR head or repeat application stop without overwriting
work. The branch is explicitly selected before the expected-head check.

```bash
set -euo pipefail
stop() { printf '%s\n' "$*" >&2; exit 1; }
cd "$HOME/Downloads/MPR"
if test ! -d mpr_v01912_numeric_export_contract_a2; then
  test ! -e mpr_v01912_numeric_export_contract_a2 || stop 'Extraction target exists and is not a directory.'
  unzip mpr_v01912_numeric_export_contract_a2.zip
fi
cd mpr_v01912_numeric_export_contract_a2
sha256sum -c SHA256SUMS
cd "$HOME/PycharmProjects/MPR"
test -z "$(git status --porcelain)" || stop 'MPR has local changes; preserve them before switching.'
git fetch origin refs/heads/docs/v0.19.12-numeric-export-contract:refs/remotes/origin/docs/v0.19.12-numeric-export-contract
if git show-ref --verify --quiet refs/heads/docs/v0.19.12-numeric-export-contract; then
  git switch docs/v0.19.12-numeric-export-contract
else
  git switch --track -c docs/v0.19.12-numeric-export-contract origin/docs/v0.19.12-numeric-export-contract
fi
git pull --ff-only origin docs/v0.19.12-numeric-export-contract
test "$(git rev-parse HEAD)" = 4c99b7b2034ec3ae192918f576dc06bbc8767ae8 || stop 'PR branch differs from reviewed a1; preserve it and return its current commit.'
test "$(git rev-parse HEAD^{tree})" = 1a7fc6d5758b15ad400b8ab4cc231bd202d39e0c || stop 'Reviewed a1 tree mismatch.'
git am "$HOME/Downloads/MPR/mpr_v01912_numeric_export_contract_a2/"[0-9][0-9][0-9][0-9]-*.patch
git diff --check 4c99b7b..HEAD
test -z "$(git diff --name-only 4c99b7b..HEAD -- src tests pyproject.toml config scripts .github)" || stop 'Unexpected implementation change in documentation-only delta.'
git status --short --branch
git log -1 --oneline
```

Only the numbered patch belongs in Git. All private review/evidence/verification
files in the bundle stay outside Git. No new declaration or download is needed
for this contract correction.

## Test, push to the same PR, request focused delta review

```bash
cd "$HOME/PycharmProjects/MPR"
.venv/bin/python -m compileall -q src tests
env PYTHONPATH=src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpr-matplotlib \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  .venv/bin/python -m unittest discover -s tests -t .
git diff --check 4c99b7b..HEAD
git push origin docs/v0.19.12-numeric-export-contract
```

Expected baseline remains 718 tests run, 716 passing and two expected opt-in
skips with the existing full dependencies. Update PR #37's empty description
with `PR_DESCRIPTION.md` from the bundle. Attach the actual a2 ZIP to Claude
privately and use `REVIEWER_PROMPT.md` for B-1/B-2/B-3/C-1/C-2 delta review.
The uploaded a1 review need not be reopened in full. New-head Python 3.10/3.12
CI and focused a2 GO precede owner merge. Verified a1 CI is historical evidence,
not a2 CI. Do not treat the reviewer's optional future-runner notice as proof
of current Python incompatibility or change the runner in this scope.

## Implementation and newer data after the contract decision

The next code change implements exporter and validator together, with the exact
unchanged-sink/scalar-observer/staged-pass mechanism and explicit assumptions.
After code review, CI and merge, use a new versioned output on retained declared
engineering data, then a small declared-development selection from the newer,
better manually screened set. New files get new registrations/reports; old
successful stages are not repeated. The old pilot is not the new collection's
yield estimate, and its support need not improve to progress.

Keep prospective final outings unexposed. Complete numeric exports permanently
mark their recordings and linked physical outings development-only. Validated
archives, reviewed generic session/split lineage and model integration precede
real training; both flow modes remain synthetic-only until their fit gate is
explicitly satisfied. No private raw command is issued by this documentation
delta. Preserve current raw paths/attempts and old data until validated durable
outputs and tested exact-byte retrieval justify a separately authorized cleanup.
