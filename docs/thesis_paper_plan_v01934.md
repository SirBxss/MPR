# Thesis and paper completion roadmap, v0.19.34

## Current position

The six original matched configurations are trained and compared statistically.
Recorded spatial and short temporal planner response development replications
are complete and accepted. The next open claim is whether using a learned law
to choose planner settings helps on held recorded error sequences. Better
statistical forecasts alone do not answer that question. The v0.19.34 study
addresses it using the current transparent local recovery simulator.

There are four remaining work packages, not a promise of four more PRs.
The first two share one bounded experiment; writing starts in parallel.
A failed scientific result does not justify chasing complexity indefinitely.

| Package | Work and experiment | Completion decision |
| --- | --- | --- |
| 1. Planner parameter selection | Fixed nine candidate grid; training only risk selection with frozen laws; observed outer held error scoring | Accept positive, null or harmful results with all baselines and components |
| 2. Robustness and claim audit | Same run: 32/64 draw prefix and 5/10/20% nominal requirements; inspect outing heterogeneity, defaults, empirical comparisons, exceedances and retrospective regret | Decide practical benefit and exact claim; add another ablation only if necessary to support that claim |
| 3. Independent final validation | Establish clean independent recording groups and reference quality; freeze model/selector/protocol and recording roles; perform any required pooled training only fit, then one untouched final modelling and planner evaluation | Final evidence supports the frozen claim or clearly limits it; no tuning on final results |
| 4. Thesis and paper synthesis | Methods, figures, evidence table, limitations, reproducibility, supervisor feedback and confidentiality clearance | Every central claim maps to an experiment and its actual limits |

If independence or usable reference quality cannot be established, final
validation is not replaced by reusing development folds. State that limitation
and agree the thesis scope with supervisors. A stronger physical simulator or
vehicle planner validation may be needed for a claim about production planner
performance. The present simulator supports claims about local recovery under
recorded exogenous errors. It is not a reproduction of a named planner paper.
Reproducing another planner is a separate decision requiring its exact paper,
code, assumptions and interfaces. Complexity is not a completion criterion.

## Evidence and research questions

| Question | Existing evidence stage | Remaining evidence or limit |
| --- | --- | --- |
| How is error defined? | Frozen signed station residual and fusion pseudo reference, row clocks, splits and support | Discuss pseudo reference bias and unavailable true lane truth |
| Which conditional/statistical law is useful? | Matched six configuration modelling comparison | Independent final calibration/tails and practical cost; no general family optimality claim |
| Does spatial/temporal structure affect planner response? | Accepted spatial and short temporal development replications | Preserve subgroup reversals and support limits; final confirmation |
| Does modelling improve parameter selection? | v0.19.34 prospective implementation | Primary held loss contrast, nominal recovery and simpler baselines |
| Is it useful for a vehicle planner? | Transparent local simulator with exogenous errors | No physical replay, perception feedback, collision or production safety conclusion |

## Additional recordings

The owner reports nine additional long recordings. Before any numeric exposure,
retain one recording per ID file using the existing intake convention and
inventory provenance, route/time overlap, independent drive groups, available
reference signals, condition/speed coverage and sequence continuity. Verify
reference quality and compatible residual definitions. Long duration does not
imply long eligible sequences or independent scenarios. Keep immutable source
identities and assign roles prospectively. If sufficiently independent and
usable, they are particularly valuable as final external validation; using all
of them to tune models would remove that benefit. If extra training is
required, separate independent groups for training and final validation before
opening outcomes. This implementation admits none of them and adds no raw
intake work. Inventory and final design are the next separate data task.

## Manuscript structure and decision rules

Begin drafting now: problem and planning relevance; residual/reference and
split definition; baseline and learned laws; statistical validation; planner
adapter and local recovery assumptions; development experiments; frozen final
study; limitations and reproducibility. Maintain a claim/evidence/limitation
table. Prefer a concise contribution demonstrating when modelling structure
matters over a catalogue of advanced architectures. Keep negative results.
No statistically significant or safety improvement wording without supporting
analysis. Seven overlapping development folds are descriptive evidence, not
an independent population significance test. An expected quadratic objective
chiefly uses first and second moments; it cannot establish a unique heavy
tail advantage. Future tail sensitive or constrained planners would require a
separate prospective study.

Bogenberger target funnels remain a separate possible extension. A future
paper is feasible only if it supplies a distinct, testable planning question,
relevant comparison and independent evidence; a named technique alone does
not establish novelty. Do not add it to this completion path. BMW data,
figures and implementation details require the appropriate release decision
before public thesis or paper dissemination. The original thesis assignment
and supervisor requirements take priority over this provisional roadmap.
