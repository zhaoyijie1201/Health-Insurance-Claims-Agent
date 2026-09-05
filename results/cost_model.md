# D6 · The cost-to-serve model

Volume 8000 claims/month. Failure cost US$7.60 per escalated claim (claims assessor, US$38/h x 12 min). Layer 3 fixed monthly US$200 (assumption: a small VM for the harness, log storage, weekly eval re-runs, an hour of maintenance). Prices are list prices per million tokens at the date of each run; no caching discount and no reasoning surcharge are modelled because neither was measured. Scripted token counts are chars/4 estimates with the same shape as a live bill; live counts are the API's usage block, and the table says which.

## 1 · Cost per successful task, every configuration measured

| configuration | backend / model | tools | mode | trials | pass rate | tokens in/run | tokens out/run | price in/out | layer 1 variable | layer 2 fallback | per task | monthly |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| live_anthropic/claude-sonnet-4.5_v2_parallel | anthropic/claude-sonnet-4.5 | v2 | parallel | 91 | 97.8% | 8,844 | 389 | 3.00 / 15.00 | 0.03237 | 0.1672 | **0.1996** | 1,797 |
| live_mistralai/mistral-medium-3-5_v2_parallel | mistralai/mistral-medium-3-5 | v2 | parallel | 91 | 95.6% | 8,598 | 393 | 1.50 / 7.50 | 0.01585 | 0.3344 | **0.3502** | 3,002 |
| live_deepseek/deepseek-chat-v3-0324_v2_parallel | deepseek/deepseek-chat-v3-0324 | v2 | parallel | 91 | 79.1% | 8,486 | 271 | 0.25 / 1.00 | 0.00239 | 1.5869 | **1.5893** | 12,914 |
| live_google/gemini-2.5-flash-lite_v2_parallel | google/gemini-2.5-flash-lite | v2 | parallel | 91 | 76.9% | 9,213 | 603 | 0.10 / 0.40 | 0.00116 | 1.7541 | **1.7552** | 14,242 |
| live_openai/gpt-4o-mini_v2_parallel | openai/gpt-4o-mini | v2 | parallel | 91 | 62.6% | 8,576 | 274 | 0.15 / 0.60 | 0.00145 | 2.8394 | **2.8408** | 22,926 |
| live_openai/gpt-4o-mini_v1_parallel | openai/gpt-4o-mini | v1 | parallel | 91 | 33.0% | 6,570 | 302 | 0.15 / 0.60 | 0.00117 | 5.0943 | **5.0954** | 40,964 |
| scripted_careful_v2_parallel | scripted:careful | v2 | parallel | 91 | 100.0% | 8,158 (est.) | 245 | 0.10 / 0.40 | 0.00091 | 0.0000 | **0.0009** | 207 |
| scripted_credulous_v2_parallel | scripted:credulous | v2 | parallel | 91 | 100.0% | 8,270 (est.) | 249 | 0.10 / 0.40 | 0.00093 | 0.0000 | **0.0009** | 207 |
| scripted_sequential_v2_sequential | scripted:sequential | v2 | sequential | 91 | 100.0% | 11,591 (est.) | 242 | 0.10 / 0.40 | 0.00126 | 0.0000 | **0.0013** | 210 |
| scripted_credulous_v1_parallel | scripted:credulous | v1 | parallel | 91 | 86.8% | 5,543 (est.) | 298 | 0.10 / 0.40 | 0.00067 | 1.0024 | **1.0031** | 8,225 |
| scripted_careful_v1_parallel | scripted:careful | v1 | parallel | 91 | 86.8% | 5,672 (est.) | 310 | 0.10 / 0.40 | 0.00069 | 1.0024 | **1.0031** | 8,225 |
| scripted_repeats_v2_sequential | scripted:repeats | v2 | sequential | 91 | 23.1% | 6,723 (est.) | 98 | 0.10 / 0.40 | 0.00071 | 5.8459 | **5.8466** | 46,973 |
| scripted_repeats_nodedupe_v2_sequential | scripted:repeats | v2 | sequential | 91 | 23.1% | 31,160 (est.) | 306 | 0.10 / 0.40 | 0.00324 | 5.8459 | **5.8492** | 46,993 |

Layer 2 is the layer every naive model omits. On the shipped configuration at 100% scripted pass rate it is zero; at a live pass rate of 90% it is US$0.76 per task, which is 831 times the token bill of a cheap-tier run (US$0.0009). The token price only matters once the failures are cheap.

## 2 · Sensitivity: live_anthropic/claude-sonnet-4.5_v2_parallel over the 20 points below its measured 98% (a rate cannot exceed 100%)

| success rate | layer 2 | per task | monthly (before layer 3) |
|---|---|---|---|
| 78% | 1.6872 | 1.7196 | 13,757 |
| 83% | 1.3072 | 1.3396 | 10,717 |
| 88% | 0.9272 | 0.9596 | 7,677 |
| 93% | 0.5472 | 0.5796 | 4,637 |
| 98% | 0.1672 | 0.1996 | 1,597 |

Every 5 points of success are worth US$3,040 a month, against a token bill of US$259 a month. The conclusion that layer 2 dominates survives the whole range; the token price only decides anything between two models whose failure rates are within a point of each other.

## 3 · Break-even success rate

Measured pairs from the live battery (v2 tools, 91 trials each). E is the expensive model's tokens plus its own measured failures; C is the cheap model's tokens only.

| cheap | expensive | E = expensive per successful task | C = cheap tokens only | failures the cheap model can afford | break-even success | cheap measured | clears? |
|---|---|---|---|---|---|---|---|
| live_google/gemini-2.5-flash-lite_v2_parallel | live_anthropic/claude-sonnet-4.5_v2_parallel | 0.1996 | 0.0012 | 2.6% | **97.4%** | 76.9% | no |
| live_openai/gpt-4o-mini_v2_parallel | live_anthropic/claude-sonnet-4.5_v2_parallel | 0.1996 | 0.0015 | 2.6% | **97.4%** | 62.6% | no |
| live_deepseek/deepseek-chat-v3-0324_v2_parallel | live_anthropic/claude-sonnet-4.5_v2_parallel | 0.1996 | 0.0024 | 2.6% | **97.4%** | 79.1% | no |
| live_mistralai/mistral-medium-3-5_v2_parallel | live_anthropic/claude-sonnet-4.5_v2_parallel | 0.1996 | 0.0158 | 2.4% | **97.6%** | 95.6% | no |
| live_google/gemini-2.5-flash-lite_v2_parallel | live_mistralai/mistral-medium-3-5_v2_parallel | 0.3502 | 0.0012 | 4.6% | **95.4%** | 76.9% | no |
| live_openai/gpt-4o-mini_v2_parallel | live_mistralai/mistral-medium-3-5_v2_parallel | 0.3502 | 0.0015 | 4.6% | **95.4%** | 62.6% | no |
| live_deepseek/deepseek-chat-v3-0324_v2_parallel | live_mistralai/mistral-medium-3-5_v2_parallel | 0.3502 | 0.0024 | 4.6% | **95.4%** | 79.1% | no |

## 4 · The four levers, measured before and after

| lever | what it attacks | where built | before | after | what moved |
|---|---|---|---|---|---|
| 1 · tool block size | B, linear in turns | D2(a)/(b): the tool set and its descriptors | v1: 7 tools, 595 tokens | v2: 6 tools, 1,550 tokens | v2 is LARGER: the six-field descriptors with size bounds and failure semantics cost 955 tokens per turn, paid for by lever 4 |
| 2 · turn count T | the quadratic term | D2(c): parallel calls | sequential: median 4, max 10, 11,591 tokens in/run | parallel: median 2, max 4, 8,158 tokens in/run | 30% fewer input tokens, same pass rate (91/91 both) |
| 3 · observation size D | compounds: re-sent every later turn | D2(b): what get_claim returns | v1 get_claim 72.0 tokens/call (raw row) | v2 get_claim 106.5 tokens/call (+ duplicate_of, narrative_flags, claim_total) | bigger by design: two facts computed in code replace a tool call and a model judgement |
| 4 · success rate | layer 2, the biggest layer | D4 + the v2 tool layer | v1: 86.8% -> per successful task US$1.0031 | v2: 100.0% -> US$0.0009 | the whole v2 token premium (US$0.00022/task) buys back US$1.0024/task of failures |

Which dominated: lever 4. On the scripted set the v1 tool layer loses 12/91 of trials to hostile narratives and every one of those is a US$7.60 escalation; the v2 descriptors cost more tokens per turn and buy that back many times over. Lever 2 is the largest token saving and it moved nothing in correctness, which is what D2(c) asks to show.

## 5 · The three caps that ship

| cap | value | where it comes from |
|---|---|---|
| step cap | 12 turns | worst legitimate sequential run is 10 turns (CLM-9007); the parallel form never passes 4 |
| budget ceiling | 60,000 tokens per run (about US$0.0060 at the cheap tier) | about 2x the worst legitimate run (~27k); the D7 runaway peaked at 39k, so the step cap fires first and the ceiling is the backstop |
| monthly limit per user | US$11 | 1.5x the expected monthly token bill of the shipped configuration at volume; an alarm, not a hard stop, so a bad week is visible before it is expensive |
