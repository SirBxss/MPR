# Project architecture

The separately reviewed v0.19.2 extractor has four small modules named
`exploratory_residuals`. Domain code reuses native alignment and speed arithmetic,
checks recorded input chronology, constructs file-local sequence layouts and
builds arrays. I/O adds disk-backed odometry/feature metadata and exact parity
against every preserved count and timing diagnostic before residual construction.
Workflow code validates both immutable reports and raw bytes, coordinates four
recordings and publishes a complete archive/audit with hashes; the CLI applies
the existing process cap before heavy imports. The old indexed reader gains an
optional topic-limit mapping, and its count pass an optional scalar-identity
observer. Their defaults and the frozen intake import graph remain unchanged.
No model or planner module is invoked. See the new predeclaration and output
contract for the geometric/complete-feature population distinction.

The v0.19.1 extension is explicitly selected by `--preserved-feasibility-report`
on the same CLI. `io.reference_diagnostics` maps exceptions to static labels;
it is imported only by the opted-in iterator, preserving the frozen intake
module graph. An optional static stage observer in the road converter never
changes the validity/selection rules. `domain.recording_pair_diagnostics`
aggregates scalar pair outcomes and exact integer delta summaries. The existing
spool/count pass feeds this observer while returning the original counts.
The workflow checks the exact preserved report and rejects any count drift.
The separate output contract and review boundary are documented in
`docs/recording_pair_diagnostics_predeclaration.md`.

The reviewed batch02 `recording_pair_feasibility` consumer reuses the canonical
intake's extracted streaming geometry converter and existing H100 projection
helper. Its I/O layer owns indexed MCAP reading, resource guards and a private
temporary SQLite geometry spool; its workflow validates exact administrative
and raw-byte lineage and writes one counts-only JSON. Its CLI enforces the
process allocation cap. It assigns no physical-session identities or cohort
roles and does not call feature, residual, model or planner computations.
The historical intake retains its list-collecting wrapper and unchanged rules.
See `docs/recording_pair_feasibility_predeclaration.md` for its fixed scope and
`docs/recording_pair_feasibility_batch02_result.md` for the completed pilot.

MPR keeps the accepted diagnostics frozen, restores native projection as the
explicit v0.5.2 exact-manifest workflow, retains v0.5.1 as a separate
odometry-compensated sensitivity audit, and provides the v0.6.0 canonical
residual/Gaussian workflow, v0.6.1 Gaussian adequacy diagnostics, the v0.7.2
conditional-feature audit, and the v0.8.0 frozen-cohort conditional Gaussian
comparison. v0.9.0 establishes MPR as the canonical thesis implementation and
adds the common gap-aware sequence contract used by the conditional Gaussian,
AIOHMM, and RC-GAN. v0.10.0 implements the Gaussian temporal null and common
sample metrics on that contract. v0.11.0 implements the fixed-development
AIOHMM without changing the data or split contract. LEEM is reference-only.
The v0.12.2 topology-semantics audit is a read-only consumer of the accepted
v0.5.2 alignment batch and exact v0.12.1 inventory lineage. It cannot change
the SENSOR_TOPOLOGY validation gate or pair eligibility.
The v0.13.0 expanded sequence workflow is the next pre-model layer: it joins
those immutable inputs to the frozen v0.9 six-feature definition, applies the
fixed geometric validity gate, and groups only adjacent eligible observations
under physical-drive sequence IDs while retaining original recording IDs.
The separate v0.13.1 workflow consumes v0.13.0 as an immutable tensor-parity
baseline. Its domain layer owns boundary admission, IO owns odometry schema and
live-hash evidence, and workflow code may replace only a missing recording-local
50 ms speed with accepted previous-MCAP odometry context. No other feature or
geometry crosses the boundary.
The v0.14.0 modeling boundary strictly converts the frame-major v0.13.1 archive
to padded sequences, preserves per-frame recording/MCAP provenance, assigns
only the four clean sensor recording groups to leave-one-group-out primary
folds, and fits every standardizer on fold-training groups. These four groups
are portions of one same-day outing, so the folds do not estimate independent-
journey generalization. Mixed-source fragments remain
supplementary. The unconditional and conditional Gaussian nulls then share the
same rows, transforms, seeds, and metrics.
The categorization separates scientific arithmetic, orchestration, I/O, plots,
and command adapters.

The v0.17.0 intake is a separate pre-model layer. Its domain module owns the
strict manifest, technical eligibility arithmetic, content-only fingerprints,
and deterministic cohort assignment. Its I/O module performs strict-JSON and
raw MCAP inspection while retaining only eligibility states and counts. The
workflow owns exact coverage, prior-lock reconciliation, gap-aware sequence
counting, and transactional four-file serialization; the CLI only maps
arguments, logging, and exit codes. These modules do not directly import
modeling, sampling, planner, evaluation, or visualization code and never
serialize the numeric six-feature values computed transiently for availability
checks. The original v0.17 root package initializer eagerly loaded unrelated
definitions; v0.18 replaces it with the verified lazy compatibility facade
described below. The intake test suite freezes the current transitive module
graph and verifies the preserved public API.

Topology auditing follows that categorization: domain code reconciles raw
protobuf values with descriptor enum names, IO verifies and packages immutable
inventory/alignment lineage, workflow code joins every EDP message to existing
pair evidence and constructs physical-session transitions, and visualization
renders one diagnostic. It writes no residuals, features, sequences, or models.

The expanded-sequence domain owns profile eligibility and boundary predicates;
IO owns prerequisite reconciliation and deterministic archives; workflow code
extracts recording-local v0.9 conditions and creates audits; visualization and
CLI remain adapters. The workflow creates no train/validation/test assignment
and invokes no Gaussian, AIOHMM, or RC-GAN code.

```text
src/lane_residuals/
├── cli/                 parsers, logging setup, main(), and exit-code mapping
├── workflows/           end-to-end diagnostic orchestration
├── domain/              current scientific calculations and data structures
├── io/                  MCAP decoding and generic report serialization
├── visualization/       current diagnostic plotting
├── modeling/            Gaussian, AIOHMM, inference, and shared model utilities
├── legacy/              v0.3.x, withdrawn, and superseded implementations
├── __init__.py          compatibility exports
└── *_cli.py, *.py       tiny compatibility facades for public import/module paths
scripts/
├── inspection/          one-off, non-package inspection helpers
└── private_data_extraction/  local BMW-data extraction helpers
config/
├── examples/            tracked placeholder-only templates
└── private/             ignored local configuration
data/
├── raw/mcap/            ignored, byte-preserved source recordings
└── intermediate/        optional ignored intermediates
outputs/diagnostics/
├── frozen/              checksum-protected accepted baselines
├── validation/          new comparison runs
├── modeling/            model adequacy and calibration diagnostics
└── archive/             preserved historical runs
outputs/models/           ignored private model runs and residual vectors
outputs/datasets/         ignored private sequence datasets and split manifests
outputs/planner/          ignored planner-input and residual-sample exchanges
tests/
├── domain/              scientific invariants
├── workflows/           orchestration and output behavior
├── io/                  decoding and serialization
├── cli/                 command-adapter tests
├── modeling/            statistical utilities
├── legacy/              withdrawn/v0.3.x compatibility
└── compatibility/       v0.4.5 public and packaging contracts
```

Package responsibilities:

- `cli` parses arguments, configures logging, calls one workflow, and maps
  errors or results to the established exit codes.
- `workflows` coordinates decoding, domain calculations, plots, and report
  writing for a complete command.
- `domain` contains current deterministic scientific rules, including temporal
  pairing, EDP reconstruction, RLMB chaining, odometry interpolation, rear-axle
  SE(2) transforms, fixed cohorts, reference diagnostics, and the immutable
  H100 residual-vector contract.
- `io` owns MCAP message decoding and reusable CSV/strict-JSON serialization.
  Prediction-time vehicle speed is decoded here with its source timestamp and
  qualifier; interpolation remains a domain rule.
- `visualization` renders diagnostic figures from already prepared data.
- `modeling` contains the Gaussian distribution and likelihood/calibration
  primitives. The v0.6.0 workflow uses them only after the domain contract has
  accepted a complete exact-manifest H100 dataset. The v0.6.1 workflow
  recomputes aligned leave-one-drive-out predictions and compares their
  marginal and Mahalanobis behavior with Gaussian reference distributions.
  The v0.8.0 conditional model adds a fold-standardized linear mean while
  retaining one condition-invariant 21-dimensional covariance.
- `domain.sequence_dataset` splits frames at recording, missing-pair, and
  source-time gaps; owns padded conditions/residuals, masks, lengths, and
  train-drive-only standardization.
- `modeling.base` defines the shared fit, sample, log-probability, save, and
  load lifecycle. Model-specific code must not redefine the dataset or split.
- `modeling.sequence_gaussian` adapts the linear conditional Gaussian to that
  lifecycle while declaring temporal dependency order zero.
- `modeling.sequence_unconditional_gaussian` supplies the condition-free
  reference needed to measure whether the six-feature mean helps under the
  same expanded-data folds.
- `modeling.aiohmm_inference` owns exact log-domain forward-backward inference
  and input-conditioned transition probabilities without a SciPy dependency.
- `modeling.aiohmm` owns the fixed-state generalized-EM estimator, deterministic
  state-label canonicalization, teacher-forced likelihood, free-running
  generation, and strict model persistence.
- `modeling.sequence_evaluation` owns physical-unit sample-mean RMSE, energy
  score, marginal interval coverage, and lag-one dependence diagnostics. These
  metrics are reused unchanged by likelihood-free models.
- `domain.conditional_features` owns recording-local direct-speed
  interpolation, fixed-interval unsigned odometry-speed derivation, EDP
  native-to-ego station translation, fixed H100 curvature summaries, and exact
  confidence-bucket coverage rules.
- `domain.alignment_contract` is the single acceptance boundary for historical
  v0.5.0 and current v0.5.2 native projection metadata; it rejects v0.5.1
  motion-compensated outputs for downstream modeling.
- `legacy` preserves v0.3.x association/preprocessing, withdrawn provisional
  residual behavior, and its synthetic plotting without presenting it as the
  current scientific pipeline.

The intended dependency direction is:

```text
cli -> workflows -> domain / io / visualization
```

Domain modules must not import CLI or workflows. I/O modules must not import
CLI or workflows. A workflow must never import another CLI. Compatibility
facades may forward names but must not own implementation logic.

Current diagnostics quantify EDP–RLMB or candidate-to-candidate disagreement.
The historical v0.5.0 and current v0.5.2 native projection outputs may supply
the v0.6.0 model vectors; the v0.5.1 odometry workflow remains optional because
DPE does not publish its exact
geometry epoch. The model workflow accepts exactly `0, 5, ..., 100 m`, requires
one fixed H100 cohort, and evaluates by physical drive before fitting the final
all-data model. The adequacy workflow accepts only a reconciled v0.6.0 output,
never an available-case station profile. The feature workflow additionally
requires the exact accepted alignment manifest and raw MCAP basename set. It
retains one audit row per residual vector and fits no model. The v0.8.0
workflow consumes that immutable audit, selects complete rows without looking
at residual values, and evaluates conditional and unconditional models on
identical drive-held-out folds. Legacy/withdrawn
code is retained only for reproducibility and compatibility. The v0.9.0
workflow consumes the frozen v0.8.0 cohort, performs no model fitting, and
writes leave-one-physical-drive-out development folds. It explicitly does not
create an untouched final test from the present two-drive corpus.
The v0.10.0 workflow reproduces those folds, verifies their transforms from
the training rows, and establishes the Gaussian independent-emission result
against which the AIOHMM temporal state is evaluated.
The v0.11.0 workflow imports the model-independent v0.9.0 verifier from
`workflows.sequence_contract`, fits deterministic same-architecture restarts
using training likelihood only, evaluates each held-out physical drive once,
and writes separate common-metric, posterior-state, transition, AR, convergence,
and restart-stability evidence. It does not perform held-out state-count or
hyperparameter selection.
The v0.14.0 workflow accepts only the hash-reconciled v0.13.1 directory. Its
four clean-drive folds are the common development protocol for all expanded
models; the mixed cohort cannot enter training or primary model comparison.
The v0.15.0 workflow consumes both that source and the exact v0.14.0 result
directory. It adds no data transformation or feature path: it reuses the fold
standardizers and evaluates a fixed two-state AIOHMM with training-only restart
selection. State-specific AR emissions exclude sequence reset rows, and the
generalized-EM update uses occupancy-safe likelihood backtracking.
The v0.15.1 workflow reuses that same autoregressive evaluation engine with one
component. `io.model_evaluation` first reconciles the complete v0.15 result and
its fold models, then the workflow permits only the predeclared state-count and
trivial-transition differences. A dedicated visualization omits meaningless
single-state occupancy/transition claims and compares the Gaussian, one-state
AR, and two-state AIOHMM directly.
The v0.15.2 workflow is a third contract around the shared autoregressive
engine. `io.model_evaluation` first reconciles the complete v0.15.0 and
v0.15.1 artifacts, including exact output hashes and fold models. The workflow
then permits only the fixed convergence-criterion and tolerance changes,
re-fits the two-state model, and reports old/new stopping behavior plus paired
comparisons with both frozen autoregressive models. Its dedicated CLI and
visualization remain in their categorized layers; no model-specific IO is
placed back at the package root.

The v0.15.3 workflow remains orchestration rather than a new model layer.
`io.model_evaluation` reconciles the complete corrected v0.15.2 artifact and
its transitive v0.14--v0.15.1 lineage. The workflow reuses the reviewed 0.98
one-state artifact, invokes the shared autoregressive engine only for the three
predeclared higher ceilings, and consolidates both Gaussian baselines,
corrected K=2, and all K=1 candidates. Candidate outputs remain in named
subdirectories; cross-candidate tables and the dedicated plot live at the
audit root.

The v0.15.4 freeze is also orchestration, with one small model-facing facade.
`workflows.development_model_freeze` verifies the complete v0.15.1 and v0.15.3
hash trees, proves the higher-ceiling all-clean fits are identical except for
their configured caps, and bundles the fixed 0.99 model without refitting.
`modeling.development_residual.DevelopmentResidualModel` owns the only planner-
facing statistical API: physical conditions are standardized, sampled through
the existing free-running AIOHMM implementation, and converted back to signed
H100 offsets in metres. `workflows.development_residual_sampling` serializes
those offsets but deliberately contains no BMW path or planner dependency.

For v0.16, `domain.reference_planner` owns left-normal perturbation, signed
origin curvature, and the pure-NumPy affine LQ error-state step.
`workflows.reference_planner_scenarios` joins accepted immutable artifacts.
`workflows.reference_planner_sensitivity` owns time shuffling, propagated
A0/A1/A2 execution, paired metrics, lineage, and serialization. The two
`cli.reference_planner_*` modules remain adapters. No BMW API is introduced.

For v0.16.1, `workflows.unconditional_gaussian_residual_sampling` validates the
complete v0.13.1/v0.14 lineage, reconstructs the stored descriptive Gaussian,
checks exact physical-standardizer equality with v0.15.4, and writes the A3
sample plus pre-planner marginal diagnostics. `workflows.gaussian_planner_transfer`
loads accepted v0.16 metrics read-only, invokes the existing planner sequence
primitive only for A3, and owns the two-sample interval and reporting contract.
`workflows.gaussian_planner_transfer_contract` is the single hard-pinned real-
artifact boundary. The two v0.16.1 CLI modules remain argument and exit-code
adapters; no model is refitted and no BMW API is introduced.

For v0.16.2, `domain.spatial_structure` contains only float64 population
cross-station moment arithmetic. `workflows.spatial_structure_audit_contract`
pins the four accepted A2/A3 source hashes and fixed dimensions, while
`workflows.spatial_structure_audit` owns exact file/schema/summary validation,
pooled and per-sequence orchestration, and the five-file numeric report.
`cli.spatial_structure_audit` is an argument and exit-code adapter. The layer
does not import a sampler or planner, so it cannot refit, resample, or execute
an earlier experimental component.

For v0.17.0 and its reviewed v0.17.1 compatibility amendment,
`domain.independent_outing_intake` owns the exact acquisition-
manifest and salted content-hash rules. `io.independent_outing_intake` reuses
the accepted raw-inventory, H100 geometry, topology, and 50 ms odometry-speed
primitives without creating a residual vector. Descriptor-generation identity
is derived only from `message.DESCRIPTOR.file.serialized_pb`: legacy remains
structural with explicit-true Boolean field 8, while flag absence is accepted
only for the one pinned v2 descriptor. `workflows.independent_outing_intake`
combines those fixed states at the declared physical-outing unit, writes only
counts/provenance/roles, and enforces first-lock, reviewed supersession, or
exact failed-audit amendment lineage before creating output.
`cli.independent_outing_intake` remains the sole entry adapter. No final-outing
outcome is exposed by this layer.
`scripts/inspection/verify_v017_intake_bundle.py` is deliberately outside the
package dependency graph. Using only the Python standard library, it rehashes
an initial manifest, raw MCAP byte streams, lock outputs, and an optionally
supplied preserved failed audit. It independently recomputes identity, cohort
assignment, and additive amendment lineage. It never imports the implementation
being checked, decodes MCAP messages, writes a file, or handles an unreviewed
supersession.

One deliberate follow-up remains: `domain.geometry_validation` currently uses
the legacy polyline-projection primitive to preserve byte-for-byte scientific
behavior. Moving that arithmetic into a neutral domain geometry utility should
only be attempted with dedicated numerical characterization tests.

The v0.18 sensor-topology feasibility contract received focused review `GO`
and its implementation follows this ownership:
`domain.sensor_topology_feasibility` for strict camera-midpoint chains,
orientation-invariant 100 m span, and source-time-pairing states;
`io.sensor_topology_feasibility` for descriptor inventory, strict message
decoding, and independent RLMB readiness; `workflows.sensor_topology_feasibility` for preserved-v0.17.1
lineage and orchestration, and `cli.sensor_topology_feasibility` for the public
adapter. It may reuse characterized neutral road/RLMB primitives, but it may
not compare LTSB and RLMB coordinates or import `legacy.preprocessing`,
residual construction, conditions, sequences, modeling, sampling, planner,
evaluation, or visualization. The package root and historical CLI facade now
resolve compatibility exports lazily so importing the v0.18 adapter does not
transitively load those prohibited layers. The exact import graph is frozen by
a subprocess test that includes the runtime MCAP decoder. v0.18.0 implementation
review returned `GO`; its one private run exposed only an exact RLMB segment-ID
descriptor mismatch. v0.18.1 corrects `int64` to the observed `uint64`; both
corrective and real-output reviews are complete, and PR #20 is merged.
The accepted closed-batch result remains negative. No ownership, geometry,
timing or privacy boundary changes. The next source/acquisition inquiry is
a documentation step and introduces no additional module or adapter.
