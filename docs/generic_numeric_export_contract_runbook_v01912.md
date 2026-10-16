# v0.19.12 contract patch and focused review runbook

Status: documentation-only candidate on merged main `7e4a06b`.
PR #36 is already merged. This is a **new PR**, not another PR #36 correction.
Read the [completed result](new_development_readiness_result_20261016.md)
and [prospective numeric-consumer contract](generic_numeric_export_v01912_contract.md).
No raw command, numeric implementation or fit is included in this patch batch.

## Apply from any clean branch

Download `mpr_v01912_numeric_export_contract_a1.zip` to `~/Downloads/MPR`.
Run the whole block. It checks the actual merged base and deliberately creates
the documentation branch, so starting on main cannot trigger the earlier
"documentation branch is not checked out" problem.

```bash
set -euo pipefail
stop() { printf '%s\n' "$*" >&2; exit 1; }
cd "$HOME/Downloads/MPR"
if test ! -d mpr_v01912_numeric_export_contract_a1; then
  test ! -e mpr_v01912_numeric_export_contract_a1 || stop 'Extraction target exists and is not a directory.'
  unzip mpr_v01912_numeric_export_contract_a1.zip
fi
cd mpr_v01912_numeric_export_contract_a1
sha256sum -c SHA256SUMS
test -d "$HOME/PycharmProjects/MPR/.git" -o -f "$HOME/PycharmProjects/MPR/.git" || stop 'Expected MPR repository is absent.'
cd "$HOME/PycharmProjects/MPR"
test -z "$(git status --porcelain)" || stop 'MPR has local changes; preserve them before switching.'
if git show-ref --verify --quiet refs/heads/docs/v0.19.12-numeric-export-contract; then
  stop 'Branch already exists; preserve it and inspect before applying again.'
fi
git switch main
git pull --ff-only
test "$(git rev-parse HEAD)" = 7e4a06bbcd8443529f806108d7d84f33714d1a16 || stop 'Main changed from the reviewed base; return its new commit for reconciliation.'
git switch -c docs/v0.19.12-numeric-export-contract
git am "$HOME/Downloads/MPR/mpr_v01912_numeric_export_contract_a1/"[0-9][0-9][0-9][0-9]-*.patch
git diff --check 7e4a06b..HEAD
test -z "$(git diff --name-only 7e4a06b..HEAD -- src tests pyproject.toml config scripts .github)" || stop 'Unexpected implementation change in documentation-only batch.'
git status --short --branch
git log -3 --oneline
```

The three numbered patches also carry forward the previously local acceptance
and post-merge continuity checkpoints; the final current checkpoint supersedes
their awaiting-result text. Preserve every private file in the bundle outside
Git. Only numbered patches are applied. Do not copy `evidence/`, private result
analysis, manifests or reconciliation output into the repository.

## Verify, push and request focused review

Using the project's existing virtual environment, run the normal checks:

```bash
cd "$HOME/PycharmProjects/MPR"
.venv/bin/python -m compileall -q src tests
env PYTHONPATH=src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpr-matplotlib \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  .venv/bin/python -m unittest discover -s tests -t .
git diff --check 7e4a06b..HEAD
git push -u origin docs/v0.19.12-numeric-export-contract
```

Expected unchanged baseline: 718 tests run, 716 passing and two expected opt-in
skips with the full project/MCAP extras. Do not install/change dependencies just
to suppress unexpected failures; return the failing output for assessment.
Normal GitHub Python 3.10/3.12 CI must cover the pushed head.

Open a new PR titled **docs: reconcile pilot and specify generic numeric export**.
Describe the result closure, explicit prospective consumer schema policy,
separate geometry/condition populations, U48 provenance, strict archive checking
and resource/failure contract. State clearly that implementation is next.
Attach this actual ZIP to Claude privately; a link to the public PR alone does
not contain the private returned result or descriptor evidence.

Focused review should check the measured-result interpretation and contract
completeness, especially whether numeric admission is supported by the existing
interface evidence/explicit assumption, all readiness fields are preserved,
and the proposed archive/validator/resources can be implemented without
historical behavior changes or leakage. Use `REVIEWER_PROMPT.md` from the bundle.

## After the contract decision

Implement exporter and standalone validator together in a new code change;
do not add another counts-only stage. The accepted contract will remain the
explicit boundary. Review/code CI/merge precede a new privately pinned numeric
export using the existing raw and reports. No new private command is issued by
this documentation runbook. Preserve all attempts, raw paths and old data.

Validated numeric archives are followed by reviewed generic evidenced-session/
cohort/split integration and matched real-model training/evaluation. The current
pilot does not close those gates. Source identities and cache-state catalogue
automation can follow the core archive path, with retirement only after durable
outputs and tested exact-byte retrieval. Do not bulk-download the collection.
