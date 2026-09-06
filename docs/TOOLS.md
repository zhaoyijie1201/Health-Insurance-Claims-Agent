# D2(a) · The tool set, scored

Every tool we ship, against the three questions from Class 4. The fourth column is what it costs when it is never called: its descriptor sits in the prompt prefix and is re-sent every turn (tokens are chars/4 of the rendered descriptor). Observation tokens are the mean size of what the tool returned across the scripted set.

| tool | 1 · does a task fail without it? | 2 · could the model confuse it with a neighbour? | 3 · cost when never called (descriptor tokens, v2 / v1) | observation tokens per call (v2 / v1) | why it earns its place |
|---|---|---|---|---|---|
| `get_claim` | Yes: nothing else resolves a claim id into member, hospital, lines and narrative. Every run starts here. | No. | 295 / 73 | 106.5 (n=91) / 72.0 (n=91) | The entry point. In v2 it also carries two facts computed in code: duplicate_of (four-fact match against the decided history) and narrative_flags (the regex scan). Both are decisions the model used to make and got wrong: v1 gpt-4o-mini approved all three duplicate cases and all four hostile narratives. |
| `lookup_policy` | Yes: the only source of status, dates, remaining and exclusions. Three of the five escalation triggers live in this row. | No. It answers 'is the cover live and how much is left'; check_coverage answers 'is this ONE procedure payable'. | 217 / 81 | 65.6 (n=70) / 67.5 (n=91) | Two hops (member -> policy) in one call, with `remaining` already subtracted so the model never does the arithmetic. |
| `lookup_hospital` | Yes, for the record rather than the decision: the routing table requires panel / non-panel in every record (CLM-8874, CLM-9005, CLM-9026 must_record). Without it the record cannot say how the claim settles. | No. | 127 / 64 | 21.4 (n=70) / 21.4 (n=91) | Cheapest tool in the set (~25 tokens back). Considered folding it into get_claim; kept separate so a flagged or duplicate claim, which ends at turn 1, never pays for it. |
| `check_coverage` | Yes: the only source of `covered`, `exclusion`, `requires_preauth` and `required_document` for a line. It is the branch that decides whether turn 3 exists. | With lookup_policy, slightly: both mention exclusions. The descriptor draws the line: policy-level facts vs one line. | 231 / 84 | 44.7 (n=119) / 45.1 (n=143) | Takes member_id, not policy_id, so it depends on nothing from lookup_policy and shares turn 2 with it (D2c). Returns the required document too, which is why there is no get_required_documents tool. |
| `get_preauthorisation` | Yes: CLM-8888, 8894, 9014, 9015, 9017, 9028 all turn on whether an approval exists AND contains the date. | No, once check_coverage has said requires_preauth. The descriptor says when to call it and when not to. | 278 / 87 | 34.2 (n=33) / 34.2 (n=33) | The window test runs in code (`valid_on_date`) and expired approvals are still returned in `found[]`, so the record can say 'PA-5640 found, validity ended 2026-05-31' rather than 'none'. |
| `issue_decision_letter` | Yes: the routing table's gated action. Without it there is no record and no gate. | No: the only write. | 393 / 103 | 29.0 (n=22) / 29.0 (n=34) | One gate covers the whole agent. Refuses a decision outside the three, an escalation without a trigger, a request without a named item, a flagged claim being approved, a second write, a line left undisposed, and a claim id that is not this run's. Totals are computed from the dispositions, never taken from the model. |

Six tools, 1550 descriptor tokens in total for v2 against 595 for v1's seven. The v2 block is larger because every descriptor carries its size bound and its failure semantics; that is the cost lever 1 in the cost ledger, and lever 4 pays for it: on gpt-4o-mini the same loop scores 30/91 with v1 and 57/91 with v2.

## The tool we removed, and the observation that removed it

`check_duplicate_claim(member_id, hospital_id, date_of_service, lines)` shipped in the scaffold and is still in the v1 set. It fails question 1: nothing in the claim tells the model *whether* to call it, so an agent that forgets approves a resubmission. Observed on the scripted backend before the fold (CLM-8933 approved) and again in the live v1 pass, where gpt-4o-mini approved CLM-8933, CLM-9022 and CLM-9023 in nine of nine trials even though the tool was in its list. In v2 the four-fact match runs inside get_claim and its result is a field, `duplicate_of`, that arrives whether or not the model thought to ask. The duplicate check is a rule, not a judgement, so it belongs in code (Class 4's move 3: take the step out of the loop).

## What we tried before adding a tool

| the temptation | the move instead | result |
|---|---|---|
| `get_member` to walk claim -> member -> policy | widen `lookup_policy` to take member_id and do both hops | one call, one turn |
| `get_required_documents(code)` | return `required_document` from `check_coverage` | no extra turn, no extra descriptor |
| a `scan_narrative` tool the model calls | run the scan in code inside `get_claim` and return `narrative_flags` | cannot be forgotten or talked out of |
| `compute_totals` | compute totals inside the write from the line dispositions | the model never adds numbers (it wrote 2200 for 1400 + 780 once) |
| a web or policy-wording search | not added: no case in the set fails without it, every fact is in the eight tables | the shortest defensible list |

## Poka-yoke moves in the signatures (D2b)

| before | after | what it makes impossible |
|---|---|---|
| `decision: str` | closed set of three, checked before the gate | a fourth outcome such as 'decline' or 'approve' |
| `approved_total` supplied by the model | computed from `lines` and the claim's amounts | an arithmetic slip reaching the record |
| any `lines` accepted | one disposition per line on the claim, no pending line on an approve | 'I only read lines[0]' (G12) |
| approve on any claim | refused when `narrative_flags` is non-empty | an injected instruction becoming an approval, whatever the reason says (G9, G10) |
| approve via `final` | approve only through the gated write | a decision that skipped the gate (G11) |
| `check_coverage(code, policy_id)` | `check_coverage(member_id, procedure_code)` | a coverage check against the wrong policy, and a forced extra turn |
| `get_preauthorisation(member, code)` | `(member, code, date_of_service)` with the window test in code | the model judging 'valid on the date' in its head |

## v1 against v2, measured

| measure | v1 | v2 |
|---|---|---|
| tools / descriptor tokens | 7 / 595 | 6 / 1550 |
| get_claim observation tokens | 72.0 (n=91) | 106.5 (n=91) |
| scripted pass rate (careful) | 79/91 | 91/91 |
| live pass rate, gpt-4o-mini | 30/91 (33.0%) | 57/91 (62.6%) |
| live tokens in per run | 6,569.9 | 8,576.3 |
| guardrail cases passed | see `results/guardrails.md`, v1 column | see `results/guardrails.md`, v2 column |
