# Contributions

Team Group 8 · Section C · Problem A. The ownership below follows the team declaration filed on
4 September 2026. Commits were made from one machine, so the commit history shows one committer;
the strands, the cases and the live models are the per-member record.

| Member | Owns (declaration) | What landed |
|---|---|---|
| ZHAO YIJIE | loop and tools (D1, D2a, D2c); descriptors and guardrails with WANG HAO (D2b, D3); repository | `agent.py`, `backends.py`, `tools.py`, `prompt.py`, `config.py`; the parallel/sequential measurement; the totals-in-code and task-line fixes found by the live smoke runs; cases CLM-9002 to CLM-9006; live model `openai/gpt-4o-mini` (v2 57/91) and the D2(b) v1 pass on the same model (30/91) |
| DING XIANGFENG | loop and tools (D1, D2a, D2c) | `docs/TOOLS.md` (the three-question table, the removed tool, the poka-yoke moves); cases CLM-9027 to CLM-9031; live model `mistralai/mistral-medium-3-5` (87/91) |
| WANG HAO | descriptors, v1 to v2 rewrite, guardrail layer (D2b, D3) | v1 and v2 descriptor sets in `tools.py`; `guardrails.py`; `run_guardrails.py` and `results/guardrails.md` (14 cases on both tool sets); cases CLM-9007 to CLM-9011; live model `google/gemini-2.5-flash-lite` (70/91) |
| FU SHUYI | evaluation harness and the scripted run (D4, D5a) | `harness.py`, `run_eval.py`, the code check and the results tables; `judge.py` and `docs/JUDGE_PROMPT.md`; cases CLM-9012 to CLM-9016; live model `anthropic/claude-sonnet-4.5` (89/91) |
| TRIXIE GRACE MOK | evaluation harness and the scripted run (D4, D5a) | the generator additions in `data/make_fixtures_A.py` and the answer-key labels; `docs/EVALUATION_SET.md`, `docs/CASES.md`; `demo_loop_failure.py` and `demo_tool_failure.py` (D7); cases CLM-9017 to CLM-9021; live model `deepseek/deepseek-chat-v3-0324` (72/91) |
| ZHANG YIMING | cost model, ledger, sensitivity (D6) | `cost_model.py` and `results/cost_model.md`; `battery.py` and `results/battery.md`; cases CLM-9022 to CLM-9026; live model `meta-llama/llama-3.3-70b-instruct` (69/91) |
| everyone | evaluation cases (five each), one live model each (D5b) | 30 cases, six models, six families, three tiers, one key per member |

Every pass rate above is out of 91 trials on the 45-case set (one trial per ordinary case, three per
negative case), same commit, same v2 prompt. The full tables are in `results/battery.md`.
