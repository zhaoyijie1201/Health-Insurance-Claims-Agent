# D6 · The cost-to-serve model

Volume 8000 claims/month. Failure cost US$7.60 per escalated claim (claims assessor, US$38/h x 12 min). Layer 3 fixed monthly US$200 (assumption: a small VM for the harness, log storage, weekly eval re-runs, an hour of maintenance). Prices are list prices per million tokens at the date of each run; no caching discount and no reasoning surcharge are modelled because neither was measured. Scripted token counts are chars/4 estimates with the same shape as a live bill; live counts are the API's usage block, and the table says which.

## 1 · Cost per successful task, every configuration measured

| configuration | backend / model | tools | mode | trials | pass rate | tokens in/run | tokens out/run | price in/out | layer 1 variable | layer 2 fallback | per task | monthly |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scripted_careful_v2_parallel | scripted:careful | v2 | parallel | 91 | 100.0% | 7,883 (est.) | 245 | 0.10 / 0.40 | 0.00089 | 0.0000 | **0.0009** | 207 |
| scripted_credulous_v2_parallel | scripted:credulous | v2 | parallel | 91 | 100.0% | 8,061 (est.) | 249 | 0.10 / 0.40 | 0.00091 | 0.0000 | **0.0009** | 207 |
| scripted_sequential_v2_sequential | scripted:sequential | v2 | sequential | 91 | 100.0% | 11,289 (est.) | 242 | 0.10 / 0.40 | 0.00123 | 0.0000 | **0.0012** | 210 |
| scripted_credulous_v1_parallel | scripted:credulous | v1 | parallel | 91 | 86.8% | 5,504 (est.) | 298 | 0.10 / 0.40 | 0.00067 | 1.0024 | **1.0031** | 8,225 |
| scripted_careful_v1_parallel | scripted:careful | v1 | parallel | 91 | 86.8% | 5,633 (est.) | 310 | 0.10 / 0.40 | 0.00069 | 1.0024 | **1.0031** | 8,225 |
| scripted_repeats_v2_sequential | scripted:repeats | v2 | sequential | 91 | 23.1% | 6,538 (est.) | 98 | 0.10 / 0.40 | 0.00069 | 5.8459 | **5.8466** | 46,973 |
| scripted_repeats_nodedupe_v2_sequential | scripted:repeats | v2 | sequential | 91 | 23.1% | 30,459 (est.) | 306 | 0.10 / 0.40 | 0.00317 | 5.8459 | **5.8491** | 46,993 |

Layer 2 is the layer every naive model omits. On the shipped configuration at 100% scripted pass rate it is zero; at a live pass rate of 90% it is US$0.76 per task, which is 857 times the token bill of a cheap-tier run (US$0.0009). The token price only matters once the failures are cheap.

## 2 · Sensitivity: scripted_careful_v2_parallel over the 20 points below its measured 100% (a rate cannot exceed 100%)

| success rate | layer 2 | per task | monthly (before layer 3) |
|---|---|---|---|
| 80% | 1.5200 | 1.5209 | 12,167 |
| 85% | 1.1400 | 1.1409 | 9,127 |
| 90% | 0.7600 | 0.7609 | 6,087 |
| 95% | 0.3800 | 0.3809 | 3,047 |
| 100% | 0.0000 | 0.0009 | 7 |

Every 5 points of success are worth US$3,040 a month, against a token bill of US$7 a month. The conclusion that layer 2 dominates survives the whole range; the token price only decides anything between two models whose failure rates are within a point of each other.

## 3 · Break-even success rate

No live battery in results/ yet, so the shipped agent's measured token shape is priced at the three section-7 tiers and the expensive side's success rate is ASSUMED (92% mid, 95% frontier, the brief's illustration). Replace with measured pairs once the D5(b) files land.

| cheap | expensive | E = expensive per successful task | C = cheap tokens only | failures the cheap model can afford | break-even success | cheap measured | clears? |
|---|---|---|---|---|---|---|---|
| scripted_careful_v2_parallel | scripted_careful_v2_parallel @mid, 92% assumed | 0.6171 | 0.0009 | 8.1% | **91.9%** | 100.0% | yes |
| scripted_careful_v2_parallel | scripted_careful_v2_parallel @frontier, 95% assumed | 0.4255 | 0.0009 | 5.6% | **94.4%** | 100.0% | yes |

## 4 · The four levers, measured before and after

| lever | what it attacks | where built | before | after | what moved |
|---|---|---|---|---|---|
| 1 · tool block size | B, linear in turns | D2(a)/(b): the tool set and its descriptors | v1: 7 tools, 595 tokens | v2: 6 tools, 1,494 tokens | v2 is LARGER: the six-field descriptors with size bounds and failure semantics cost 899 tokens per turn, paid for by lever 4 |
| 2 · turn count T | the quadratic term | D2(c): parallel calls | sequential: median 4, max 10, 11,289 tokens in/run | parallel: median 2, max 4, 7,883 tokens in/run | 30% fewer input tokens, same pass rate (91/91 both) |
| 3 · observation size D | compounds: re-sent every later turn | D2(b): what get_claim returns | v1 get_claim 72.0 tokens/call (raw row) | v2 get_claim 106.5 tokens/call (+ duplicate_of, narrative_flags, claim_total) | bigger by design: two facts computed in code replace a tool call and a model judgement |
| 4 · success rate | layer 2, the biggest layer | D4 + the v2 tool layer | v1: 86.8% -> per successful task US$1.0031 | v2: 100.0% -> US$0.0009 | the whole v2 token premium (US$0.00020/task) buys back US$1.0024/task of failures |

Which dominated: lever 4. On the scripted set the v1 tool layer loses 12/91 of trials to hostile narratives and every one of those is a US$7.60 escalation; the v2 descriptors cost more tokens per turn and buy that back many times over. Lever 2 is the largest token saving and it moved nothing in correctness, which is what D2(c) asks to show.

## 5 · The three caps that ship

| cap | value | where it comes from |
|---|---|---|
| step cap | 12 turns | worst legitimate sequential run is 10 turns (CLM-9007); the parallel form never passes 4 |
| budget ceiling | 60,000 tokens per run (about US$0.0060 at the cheap tier) | about 2x the worst legitimate run (~27k); the D7 runaway peaked at 39k, so the step cap fires first and the ceiling is the backstop |
| monthly limit per user | US$11 | 1.5x the expected monthly token bill of the shipped configuration at volume; an alarm, not a hard stop, so a bad week is visible before it is expensive |
