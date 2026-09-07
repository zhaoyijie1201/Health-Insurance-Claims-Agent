# Health-insurance claim first response: one agent, proved

PE6201 · A2 · Group 8, Section C · Problem A · Draft 1, 6 September 2026

Every number below is in this repository: result tables in `results/`, the evaluation set in
`data/expected_outcomes_A.json`, the tool table in `docs/TOOLS.md`. Prose is under 2,000 words;
tables do not count.

## 1 · Why an agent

A claim is not one thing. It carries lines, each with its own code, and the number of checks a
claim needs is decided by the claim: a one-line consultation on a live policy is decided after
two turns, a four-line claim with two pre-authorisations to chase takes four in the parallel form
and ten in the sequential one. Across our 45 cases the parallel run ranges from 2 to 4 turns and
the sequential from 2 to 10 (`results/eval_scripted_*`). That variation is the workflow test:
rungs 1 to 6 of the Class 4 ladder fix the path in advance, and no fixed path fits both a lapsed
policy that must stop after one lookup and a claim that must chase a pre-authorisation it only
learns about after coverage answers. A single call (rung 1) would need all eight tables in the
prompt; a prompt chain or router (rungs 2 and 3) would price the lines of a claim it should have
escalated, the failure the cheap models show in section 3; parallelisation (rung 4) is used
inside turn 2 but cannot decide which calls turn 3 needs. Rung 7 is the first rung on which the
claim, not the designer, chooses the sequence. Its cost is the governance cliff at the first
write; our agent has exactly one, `issue_decision_letter`, gated.

Both Capsule 1 tests pass. Test 1, ground truth: eight systems of record, from the policy row to
the decided-claims history, contradict the model in milliseconds, and the code check turns a run
into pass or fail in seconds. Test 2 we
ran on measured numbers. With P the pass rate and T the median turns, s = P^(1/T):
claude-sonnet-4.5 scores 0.978 over 2 turns, s = 0.989; gpt-4o-mini scores 0.626 over 3, s =
0.856. The spread at the same T says our problem is step quality, not step count, and grouping
the failed live trials by the turn before the wrong conclusion names the weak step: 72 of 97 were
claims turn 1 or 2 had already decided, a duplicate flag or a policy row, and the model read it
and went on (`results/battery.md`). Way 1, raise per-step reliability, is what the tool rewrite
did; way 2, cut turns, is what the dependency rule did, and it moved cost, not correctness.

What good looks like was committed before the agent (`docs/GOOD_RUN.md`, first commit): the real
reason traceable to a record, the routing table's outcome and only that one, the gated action at
most once and only after the facts, "I don't know" as a named request rather than an invention,
and an early stop that costs less than a person. Statements 3 and 4 are what the guardrail
checklist and the negative cases exist to catch.

## 2 · The tool layer

Six tools ship, scored against the three questions in `docs/TOOLS.md`. Five are reads and one is
the write. We removed one the scaffold shipped: `check_duplicate_claim`. It fails question 1
because nothing in a claim tells the model *whether* to call it, and the observation that removed
it was reproducible: on the scripted backend an agent that forgets it approves CLM-8933, and in the
live v1 pass gpt-4o-mini approved all three resubmissions in nine of nine trials with the tool in
its list. In v2 the four-fact match runs in code inside `get_claim` and arrives as a field,
`duplicate_of`, whether or not the model asks. Four other tools were tried and not added, each
becoming a wider parameter, a richer return or code inside an existing tool (`docs/TOOLS.md`); the
last, a totals calculator, followed a live smoke run that wrote 2,200 for 1,400 + 780.

The descriptor rewrite was measured on gpt-4o-mini with everything else fixed. v1 is
a one-line-per-tool manual with a seventh tool; v2 carries the six fields with size bounds and
failure semantics, and the write's poka-yoke moves. The tool block grew from 595 to 1,550 tokens,
re-sent every turn; `get_claim` returns 106 tokens instead of 72. On 5 September 2026, 91 trials
each, the pass rate went from 30/91 (33.0%) to 57/91 (62.6%), the negative cases from 14/69 to
38/69, and the hostile-text cases from 2/12 to 12/12. The same fourteen guardrail cases pass 10/14 on v1 and 14/14 on v2
(`results/guardrails.md`); the four that v1 fails are the write's guards, which is where they
live. v2 is not smaller; it is safer, and section 4 prices the trade.

The dependency rule: a pair of calls may share a turn only when neither needs the other's output.
`get_claim` runs alone. `lookup_policy`, `lookup_hospital` and one `check_coverage` per line depend
only on the claim, so they share turn 2, which is why `check_coverage` takes `member_id` and not a
policy id from the previous call. `get_preauthorisation` cannot join them: which lines need one is
known only after coverage answers. The write goes last, alone. Measured both ways on the scripted
backend: sequential is 91/91, median 4 turns, worst 10, 11,592 input tokens per run; parallel is
91/91, median 2, worst 4, 8,158 tokens, a 30% saving with correctness unmoved. Two limits are
visible in the traces. Parallel calls raise cost when a call proves unnecessary: a claim that
escalates on the policy row has already paid for the hospital lookup and every coverage check.
And they remove a decision point: an agent that read the policy row alone would never have priced
CLM-8925's lines; ours already asked.

## 3 · What the evidence showed

The set is 45 cases, 15 shipped and 30 ours, 23 negative, labelled from Appendix A before any run
(`docs/EVALUATION_SET.md`). One case changed the agent: CLM-9013, a benign narrative containing
"override", was escalated by the scan on its first run and the pattern was tightened. The decision, trigger, named line and total are code checks; the
`must_record` items are a judgement check ruled by a named second model with a committed prompt,
never the model under test.

The scripted run reproduces 91/91. The live battery ran six models, six families, three tiers, on
5 and 6 September 2026 against the same commit and the same v2 prompt; each pass rate is out of 91
trials, one per ordinary case and three per negative.

| model | tier | pass (91 trials, v2, Sep 2026) | negatives | judgement | US$ per run |
|---|---|---|---|---|---|
| claude-sonnet-4.5 | frontier | 89/91 (97.8%) | 67/69 | 38/45 | 0.0324 |
| mistral-medium-3-5 | mid | 87/91 (95.6%) | 65/69 | 28/45 | 0.0158 |
| deepseek-chat-v3-0324 | cheap | 72/91 (79.1%) | 50/69 | 18/45 | 0.0024 |
| gemini-2.5-flash-lite | cheap | 70/91 (76.9%) | 48/69 | 27/45 | 0.0012 |
| llama-3.3-70b-instruct | cheap | 69/91 (75.8%) | 48/69 | 16/45 | 0.0009 |
| gpt-4o-mini | cheap | 57/91 (62.6%) | 38/69 | 13/45 | 0.0015 |

The negatives separated them in one place. Every v2 model escalated all twelve hostile-text trials
and, except gpt-4o-mini, all nine duplicates: those two facts are computed in code and arrive as
fields. The limit and date rules are not: the model reads `remaining` and the cover dates and must
stop. On the nine limit trials sonnet scored 9/9, mistral 5/9, deepseek 2/9 and the other three
0/9; on the fifteen date trials sonnet and mistral scored 15/15, the cheap models 6 to 11. The
boundary pairs make the mechanism visible: every model approved the claim exactly at its remaining
limit and the service on the policy's first day, but only sonnet escalated the claim one dollar
over in all three trials. The cheap models were not miscalculating; they were not comparing at all,
and went on to price the lines. gpt-4o-mini approved all nine duplicate trials with `duplicate_of`
in front of it. Sonnet's two failures were the de-duplication guard halting a same-turn repeat,
not judgements (section 6).

## 4 · What it costs

Class 5's three layers, computed with the Capsule 2 notebook's own functions on measured tokens
(`results/cost_model.md`, prices read on 5 September 2026). Layer 1 is tokens at list price. Layer
2 is (1 − P) × US$7.60, the claims assessor's twelve minutes, the escalation form because in this
problem a wrong answer goes to a person, not back into the loop. Layer
3 is an assumed US$200 a month.

| model | layer 1 | layer 2 | per successful task | monthly at 8,000 |
|---|---|---|---|---|
| claude-sonnet-4.5 | 0.0324 | 0.167 | **0.200** | 1,797 |
| mistral-medium-3-5 | 0.0158 | 0.334 | 0.350 | 3,002 |
| deepseek-chat-v3-0324 | 0.0024 | 1.587 | 1.589 | 12,914 |
| gemini-2.5-flash-lite | 0.0012 | 1.754 | 1.755 | 14,242 |
| llama-3.3-70b-instruct | 0.0009 | 1.838 | 1.839 | 14,909 |
| gpt-4o-mini | 0.0015 | 2.839 | 2.841 | 22,926 |

The most expensive model per run is the cheapest per successful task, by a factor of nine over the
cheap tier. Sensitivity: ten points of success on sonnet are worth about US$6,000 a month against a
token bill of US$260; the conclusion survives the whole range. Break-even: against sonnet, E = 0.200 and a cheap model's C is 0.001 to 0.002, so it may
fail 2.6% of claims and must succeed 97.4% of the time. The best cheap model measured 79.1%. Even
mistral at 95.6% falls short of its 97.6% break-even. Against mistral the bar is 95.4%, and no
cheap model clears that either. On this problem the token price decides nothing until two models
are within a point of each other.

The four levers, before and after: lever 1, the tool block, 595 to 1,550 tokens, went the wrong
way by design; lever 2, turns, 11,592 to 8,158 input tokens per run, the largest token saving;
lever 3, `get_claim` observations, 72 to 106 tokens, also larger by design; lever 4, the success
rate, 33.0% to 62.6% on the same model, which turned US$5.10 per successful task into US$2.84.
Lever 4 dominated: the entire v2 token premium is a fraction of a cent per run and buys back
dollars of failures. Caps: 12 turns, from a worst legitimate run of 10; 60,000 tokens a run, twice
the worst legitimate 27,000 and below the 39,000 the D7 runaway peaked at, so the step cap fires
first; a monthly token alarm at 1.5× the expected bill. No caching or reasoning adjustment is
claimed; neither was used.

## 5 · The two failures

Failure 1, loop control, is the working sequential agent minus its memory that the policy row
already arrived: it asks for it again every turn. Nothing crashes. The per-run turn and token log
found it. With de-duplication deleted, 70 of 91 trials ran to the step
cap of 12 turns and the set cost 2.6× the working agent's tokens (`results/d7_loop_failure.md`).
With it restored, the same 70 trials stop at turn 3, the first repeat, and the halt names the cause.
The step cap would have caught it nine turns and four times the tokens later without naming it; the
budget ceiling never fired, because the runaway peaked at 39,000 tokens under a 60,000 ceiling set
from legitimate runs. A prompt cannot fix it: the model is the thing that forgot. Restoring the
guard truncated no legitimate run: 91/91 on both forms.

Failure 2 is in the tool interface. The credulous agent believes tool-shaped text inside the
member's narrative. With v1 tools it approved all four hostile claims in twelve of twelve trials;
with v2, the write refused every one and the run ended in the correct escalation
(`results/d7_tool_failure.md`). The prompt was identical in both versions and already said the
narrative was untrusted; it was ignored. Loop control sees turns and spend, never content. The fix
belongs where the fact is computed and where the write happens.

## 6 · What we would not deploy

Three measured limits. The de-duplication guard halts on an identical call
within one turn, not only across turns; sonnet lost two trials that way, and a same-turn duplicate
cannot be a loop, so the next version ignores it instead. The cheap models' dominant failure is
skipping precedence on the policy row, so the deployable configuration is mistral or sonnet with
`confirm` at the gate; the asymmetry that shaped that setting is that a wrong approval is a letter
the insurer cannot easily take back. And one shipped label, CLM-8952, expects a coverage result
our agent never queries after a narrative flag.

The architecture we did not build is a second, reviewing agent reading each record before the
letter goes out. It would have caught the limit and date misses in the cheap models, at roughly
one more model call per claim, about US$0.003 on the cheap tier. We stayed single-agent because a
reviewer that reads the same observations makes the same precedence error; the measured fix was
fields computed in code, and Cognition's own finding is that the writes stay single-threaded.
