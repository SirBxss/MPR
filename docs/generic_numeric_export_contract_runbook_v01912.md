# PR #37 a3: contract correction on the existing branch

Status: documentation-only delta on reviewed owner head `cc5acdb` (tree `a1f4c0c`).
PR #37 is open; **update that PR**, not a new one. Do not reapply the a1/a2
patch batches or reopen merged PR #36. Read
[the review evaluation](generic_numeric_export_v01912_a3_review.md) and
[the revised contract](generic_numeric_export_v01912_contract.md).
This fifth commit adds no production code, model or private-data command.

## Apply from main or the existing feature branch

Save `mpr_v01912_numeric_export_contract_a3.zip` in `~/Downloads/MPR` and run the
whole block. An already extracted bundle is reused only after manifest checks.
Local changes, a different PR head or repeat application stop without overwriting
work. The branch is explicitly selected before the expected-head check.

```bash
set -euo pipefail
stop() { printf '%s\n' "$*" >&2; exit 1; }
cd "$HOME/Downloads/MPR"
if test ! -d mpr_v01912_numeric_export_contract_a3; then
  test ! -e mpr_v01912_numeric_export_contract_a3 || stop 'Extraction target exists and is not a directory.'
  unzip mpr_v01912_numeric_export_contract_a3.zip
fi
cd mpr_v01912_numeric_export_contract_a3
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
test "$(git rev-parse HEAD)" = cc5acdbe07c7923ff4dbf52b93cfaaff031e72ea || stop 'PR branch differs from reviewed a2; preserve it and return its current commit.'
test "$(git rev-parse HEAD^{tree})" = a1f4c0ce61ff4da790a2980caa7e9b9e2b6f0e3a || stop 'Reviewed a2 tree mismatch.'
git am "$HOME/Downloads/MPR/mpr_v01912_numeric_export_contract_a3/"[0-9][0-9][0-9][0-9]-*.patch
git diff --check cc5acdb..HEAD
test -z "$(git diff --name-only cc5acdb..HEAD -- src tests pyproject.toml config scripts .github)" || stop 'Unexpected implementation change in documentation-only delta.'
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
git diff --check cc5acdb..HEAD
git push origin docs/v0.19.12-numeric-export-contract
```

Expected baseline remains 718 tests run, 716 passing and two expected opt-in
skips with the existing full dependencies. PR #37 already has a description; update it for a3
using `PR_DESCRIPTION.md` from the bundle if needed. Attach the actual a3 ZIP to Claude
privately and use `REVIEWER_PROMPT.md` for R-1/C-3/C-4 delta review.
The accepted a2 sections need not be reopened in full. New-head Python 3.10/3.12
CI and focused a3 GO precede owner merge. Verified a2 CI is historical evidence,
not a3 CI. Do not treat the reviewer's optional future-runner notice as proof
of current Python incompatibility or change the runner in this scope.

## Implementation and newer data after the contract decision

The next code change implements exporter and validator together, with the exact
unchanged-sink/scalar-observer/staged-pass mechanism and explicit assumptions.
After code review, CI and merge, choose a small explicitly authorized development
selection from the newer, better manually screened set once its own prerequisites
pass. The retained pilot can also serve as a numeric engineering regression;
it is not a mandatory hurdle before newer data. New files get new registrations/
reports; old
successful stages are not repeated. The old pilot is not the new collection's
yield estimate, and its support need not improve to progress.

Keep prospective final outings unexposed. Do not create an authorization during
this documentation step. The future command requires an owner-supplied immutable
file explicitly reserving the exact raw set and linked outings for development;
the universal pipeline purpose is not that authorization. Counts-only screening
has no such file. Reservation and actual numeric publication remain distinct,
but both exclude linked outings from final selection under the a3 contract.
Validated
archives, reviewed generic session/split lineage and model integration precede
real training; both flow modes remain synthetic-only until their fit gate is
explicitly satisfied. No private raw command is issued by this documentation
delta. Preserve current raw paths/attempts and old data until validated durable
outputs and tested exact-byte retrieval justify a separately authorized cleanup.
