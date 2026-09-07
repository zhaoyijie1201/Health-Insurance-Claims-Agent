# D6 · The cost-to-serve model

Computed with the Class 5 Capsule 2 notebook's functions (`variable_cost`, `cost_per_successful_task`, `monthly`, `break_even_success_rate`, `sensitivity`) on MEASURED inputs. Volume 8000 claims/month. Failure cost US$7.60 per escalated claim (`escalation_cost("claims_assessor")`: US$38/h x 12 min), the escalation form because a wrong outcome goes to a person, not back into the loop. Layer 3 fixed monthly US$200 (assumption: a small VM for the harness, log storage, weekly eval re-runs, an hour of maintenance). Prices are OpenRouter list prices read on 2026-09-05; no caching discount and no reasoning surcharge are modelled because neither was measured. Scripted token counts are chars/4 estimates with the same shape as a live bill; live counts are the API's usage block.

## 1 · Cost per successful task, every configuration measured

| configuration | backend / model | tools | date | trials | pass rate | tokens in/run | tokens out/run | price in/out | layer 1 variable | layer 2 fallback | per successful task | fallback share | monthly |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| live_anthropic/claude-sonnet-4.5_v2_parallel | anthropic/claude-sonnet-4.5 | v2 | 2026-09-05 | 91 | 97.8% | 8,844 | 389 | 3.00 / 15.00 | 0.03237 | 0.1672 | **0.1996** | 84% | 1,797 |
| live_mistralai/mistral-medium-3-5_v2_parallel | mistralai/mistral-medium-3-5 | v2 | 2026-09-05 | 91 | 95.6% | 8,598 | 393 | 1.50 / 7.50 | 0.01585 | 0.3344 | **0.3502** | 95% | 3,002 |
| live_deepseek/deepseek-chat-v3-0324_v2_parallel | deepseek/deepseek-chat-v3-0324 | v2 | 2026-09-05 | 91 | 79.1% | 8,486 | 271 | 0.25 / 1.00 | 0.00239 | 1.5869 | **1.5893** | 100% | 12,914 |
| live_google/gemini-2.5-flash-lite_v2_parallel | google/gemini-2.5-flash-lite | v2 | 2026-09-05 | 91 | 76.9% | 9,213 | 603 | 0.10 / 0.40 | 0.00116 | 1.7541 | **1.7552** | 100% | 14,242 |
| live_meta-llama/llama-3.3-70b-instruct_v2_parallel | meta-llama/llama-3.3-70b-instruct | v2 | 2026-09-06 | 91 | 75.8% | 8,203 | 255 | 0.10 / 0.32 | 0.00090 | 1.8377 | **1.8386** | 100% | 14,909 |
| live_openai/gpt-4o-mini_v2_parallel | openai/gpt-4o-mini | v2 | 2026-09-05 | 91 | 62.6% | 8,576 | 274 | 0.15 / 0.60 | 0.00145 | 2.8394 | **2.8408** | 100% | 22,926 |
| live_openai/gpt-4o-mini_v1_parallel | openai/gpt-4o-mini | v1 | 2026-09-05 | 91 | 33.0% | 6,570 | 302 | 0.15 / 0.60 | 0.00117 | 5.0943 | **5.0954** | 100% | 40,964 |
| scripted_careful_v2_parallel | scripted:careful | v2 | 2026-09-07 | 91 | 100.0% | 8,158 (est.) | 245 | 0.10 / 0.40 | 0.00091 | 0.0000 | **0.0009** | 0% | 207 |
| scripted_credulous_v2_parallel | scripted:credulous | v2 | 2026-09-07 | 91 | 100.0% | 8,342 (est.) | 249 | 0.10 / 0.40 | 0.00093 | 0.0000 | **0.0009** | 0% | 207 |
| scripted_sequential_v2_sequential | scripted:sequential | v2 | 2026-09-07 | 91 | 100.0% | 11,695 (est.) | 242 | 0.10 / 0.40 | 0.00127 | 0.0000 | **0.0013** | 0% | 210 |
| scripted_credulous_v1_parallel | scripted:credulous | v1 | 2026-09-07 | 91 | 86.8% | 5,617 (est.) | 298 | 0.10 / 0.40 | 0.00068 | 1.0024 | **1.0031** | 100% | 8,225 |
| scripted_careful_v1_parallel | scripted:careful | v1 | 2026-09-07 | 91 | 86.8% | 5,748 (est.) | 310 | 0.10 / 0.40 | 0.00070 | 1.0024 | **1.0031** | 100% | 8,225 |
| scripted_repeats_v2_sequential | scripted:repeats | v2 | 2026-09-07 | 91 | 23.1% | 6,787 (est.) | 98 | 0.10 / 0.40 | 0.00072 | 5.8459 | **5.8466** | 100% | 46,973 |
| scripted_repeats_nodedupe_v2_sequential | scripted:repeats | v2 | 2026-09-07 | 91 | 23.1% | 31,401 (est.) | 306 | 0.10 / 0.40 | 0.00326 | 5.8459 | **5.8492** | 100% | 46,993 |

The fallback is 84% to 100.0% of cost per successful task across the live models (the notebook's worked example: 81% to 99.8%). The cheapest model per successful task is **anthropic/claude-sonnet-4.5** at US$0.200, the most expensive per run.

## 2 · The notebook's input formula against the measured bill

`input ~ base*T + growth*T(T-1)/2` (the exact sum, Class 5's form). base is the system prompt plus the task line, growth the mean reply-plus-observation a completed turn adds, T the median turns. Shown for the shipped configuration both ways.

| configuration | base | growth (derived) | T | formula input tokens | measured mean | turns max |
|---|---|---|---|---|---|---|
| scripted_careful_v2_parallel | 2,433 | 3,292 | 2 | 8,158 | 8,158 | 4 |
| scripted_sequential_v2_sequential | 2,317 | 405 | 4 | 11,698 | 11,695 | 10 |

Cutting turns from the sequential median to the parallel median attacks both terms; the prefix term (base*T) is the larger on our short loops, which is why lever 2 saved 30%% and not the 54%% of the brief's eight-to-four example.

## 3 · Sensitivity: live_anthropic/claude-sonnet-4.5_v2_parallel over the 20 points below its measured 97.8% (a rate cannot exceed 100%)

| success rate | layer 2 | per successful task | monthly (before layer 3) |
|---|---|---|---|
| 77.8% | 1.6872 | 1.7196 | 13,757 |
| 82.8% | 1.3072 | 1.3396 | 10,717 |
| 87.8% | 0.9272 | 0.9596 | 7,677 |
| 92.8% | 0.5472 | 0.5796 | 4,637 |
| 97.8%  <- measured | 0.1672 | 0.1996 | 1,597 |

Every 5 points of success are worth US$3,040 a month against a token bill of US$259 a month. The conclusion that layer 2 dominates survives the whole range; the token price only decides anything between two models whose failure rates are within a point of each other.

## 4 · Break-even success rate

Measured pairs (v2 tools, 91 trials each). E is the expensive model's tokens plus its own measured failures; C is the cheap model's tokens only; `break_even_success_rate(C, E, F)`.

| cheap | expensive | E = expensive per successful task | C = cheap tokens only | failures the cheap model can afford | break-even success | cheap measured | clears? |
|---|---|---|---|---|---|---|---|
| live_meta-llama/llama-3.3-70b-instruct_v2_parallel | live_anthropic/claude-sonnet-4.5_v2_parallel | 0.1996 | 0.0009 | 2.6% | **97.4%** | 75.8% | no |
| live_google/gemini-2.5-flash-lite_v2_parallel | live_anthropic/claude-sonnet-4.5_v2_parallel | 0.1996 | 0.0012 | 2.6% | **97.4%** | 76.9% | no |
| live_openai/gpt-4o-mini_v2_parallel | live_anthropic/claude-sonnet-4.5_v2_parallel | 0.1996 | 0.0015 | 2.6% | **97.4%** | 62.6% | no |
| live_deepseek/deepseek-chat-v3-0324_v2_parallel | live_anthropic/claude-sonnet-4.5_v2_parallel | 0.1996 | 0.0024 | 2.6% | **97.4%** | 79.1% | no |
| live_mistralai/mistral-medium-3-5_v2_parallel | live_anthropic/claude-sonnet-4.5_v2_parallel | 0.1996 | 0.0158 | 2.4% | **97.6%** | 95.6% | no |
| live_meta-llama/llama-3.3-70b-instruct_v2_parallel | live_mistralai/mistral-medium-3-5_v2_parallel | 0.3502 | 0.0009 | 4.6% | **95.4%** | 75.8% | no |
| live_google/gemini-2.5-flash-lite_v2_parallel | live_mistralai/mistral-medium-3-5_v2_parallel | 0.3502 | 0.0012 | 4.6% | **95.4%** | 76.9% | no |
| live_openai/gpt-4o-mini_v2_parallel | live_mistralai/mistral-medium-3-5_v2_parallel | 0.3502 | 0.0015 | 4.6% | **95.4%** | 62.6% | no |
| live_deepseek/deepseek-chat-v3-0324_v2_parallel | live_mistralai/mistral-medium-3-5_v2_parallel | 0.3502 | 0.0024 | 4.6% | **95.4%** | 79.1% | no |

## 5 · The four levers, measured before and after

| lever | what it attacks | where built | before | after | what moved |
|---|---|---|---|---|---|
| 1 · tool block size | base, linear in turns | D2(a)/(b): the tool set and its descriptors | v1: 7 tools, 595 tokens | v2: 6 tools, 1,550 tokens | v2 is LARGER: six fields with size bounds and failure semantics cost 955 tokens per turn, paid for by lever 4 |
| 2 · turn count T | the quadratic term | D2(c): parallel calls | sequential: median 4, max 10, 11,695 tokens in/run | parallel: median 2, max 4, 8,158 tokens in/run | 30% fewer input tokens, same pass rate (91/91 both) |
| 3 · observation size D | compounds: re-sent every later turn | D2(b): what get_claim returns | v1 get_claim 72.0 tokens/call (raw row) | v2 get_claim 106.5 tokens/call (+ duplicate_of, near_misses, narrative_flags) | bigger by design: facts computed in code replace a tool call and a model judgement |
| 4 · success rate | layer 2, the biggest layer | D4 + the v2 tool layer, measured live on gpt-4o-mini | v1: 33.0% -> US$5.095 per successful task | v2: 62.6% -> US$2.841 | the v2 token premium (US$0.00028/run) buys back US$2.255/task of failures |

Which dominated: lever 4. Lever 2 is the largest token saving and moved nothing in correctness, which is what D2(c) asks to show; levers 1 and 3 went the other way on purpose. On this problem every failure is a US$7.60 escalation, so the cost per successful task ranks by pass rate and nothing else.

## 6 · The three caps that ship

| cap | value | where it comes from |
|---|---|---|
| step cap | 12 turns | worst legitimate sequential run is 10 turns (CLM-9007); the parallel form never passes 4 |
| budget ceiling | 60,000 tokens per run (about US$0.0060 at the cheap tier) | about 2x the worst legitimate run (~27k); the D7 runaway peaked at 39k, so the step cap fires first and the ceiling is the backstop |
| monthly token alarm per user | US$11 | 1.5x the expected monthly token bill of the shipped configuration at volume; an alarm, not a hard stop |
