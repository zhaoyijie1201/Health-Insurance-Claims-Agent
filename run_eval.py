#!/usr/bin/env python
"""
PE6201 · A2 · Problem A — ENTRY POINT. THIS IS WHAT A MARKER RUNS.
====================================================================
    python run_eval.py                          every labelled case, scripted, graded (D5a)
    python run_eval.py CLM-8842                 one case, every turn shown
    python run_eval.py CLM-8941 --ask           a human at the gate
    python run_eval.py --prompt [--tools v1]    exactly what the model is told, and its size
    python run_eval.py --policy sequential      D2(c) "before": one call per turn
    python run_eval.py --tools v1               D2(b) baseline tool set
    python run_eval.py --policy repeats [--no-dedupe]           D7 failure 1
    python run_eval.py --policy credulous --tools v1|v2         D7 failure 2
    python run_eval.py --backend live --model openai/gpt-4o-mini --tier cheap     one D5(b) battery

No key, no network, no packages beyond the standard library on the scripted path.
Results land in results/eval_<label>.{json,md}; failed-run transcripts in results/transcripts/.
====================================================================
"""
import argparse
import json
import os
import sys

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("case_id", nargs="?", help="one claim id: verbose trace instead of the set")
ap.add_argument("--backend", default=None, help="scripted (default) | live")
ap.add_argument("--model", default=None, help="OpenRouter model id (live only)")
ap.add_argument("--tier", default=None, help="price tier for the cost column: cheap | mid | frontier")
ap.add_argument("--policy", default="careful", help="careful | sequential | repeats | credulous (scripted)")
ap.add_argument("--tools", default="v2", choices=["v1", "v2"], help="tool set + descriptors")
ap.add_argument("--mode", default=None, choices=["parallel", "sequential"], help="prompt rule; defaults from policy")
ap.add_argument("--autonomy", default=None, choices=["suggest", "confirm", "act"])
ap.add_argument("--cases", default=None, help="comma-separated claim ids; default every labelled case")
ap.add_argument("--trials", type=int, default=3, help="trials per negative case (default 3)")
ap.add_argument("--label", default=None, help="results file label")
ap.add_argument("--no-dedupe", action="store_true", help="delete the de-duplication guard (D7)")
ap.add_argument("--max-turns", type=int, default=None)
ap.add_argument("--max-tokens", type=int, default=None)
ap.add_argument("--write", action="store_true", help="append decisions to results/decisions.jsonl during the set")
ap.add_argument("--ask", action="store_true", help="single case: prompt a human at the gate")
ap.add_argument("--prompt", action="store_true", help="print the system prompt and stop")
ap.add_argument("-v", "--verbose", action="store_true")
a = ap.parse_args()

# the environment is read by config at import time, so set it first
if a.backend:
    os.environ["A2_BACKEND"] = a.backend
if a.model:
    os.environ["A2_MODEL"] = a.model
if a.tier:
    os.environ["A2_PRICE_TIER"] = a.tier

import config                                   # noqa: E402
import prompt                                   # noqa: E402
from agent import run_case                      # noqa: E402
from harness import code_check, load_key, prepare_judgement_check, run_set     # noqa: E402

print()
print(config.summary())
print("data: %s" % config.data_root())

if a.prompt:
    print()
    prompt.audit(a.tools, a.mode or "parallel")
    sys.exit(0)

dedupe = False if a.no_dedupe else None

# ---- one case, every turn ---------------------------------------------------------
if a.case_id:
    def operator(action, payload):
        if not a.ask:
            return True
        print("\n   GATE - proposed record for %s:" % payload.get("claim_id"))
        print(json.dumps({k: payload.get(k) for k in ("decision", "reason", "lines", "approved_total", "refused_total")},
                         indent=2, ensure_ascii=False))
        return input("   approve? [y/N] ").strip().lower() == "y"

    print("\n%s\n  %s - every turn\n%s" % ("-" * 68, a.case_id, "-" * 68))
    r = run_case(a.case_id, a.policy, a.tools, a.mode, approve=operator, verbose=True, write=True,
                 max_turns=a.max_turns, max_tokens=a.max_tokens, dedupe=dedupe, autonomy=a.autonomy)
    print("\n  DECISION RECORD")
    print(json.dumps({k: v for k, v in r.items() if k not in ("transcript", "tool_log", "raw_replies")},
                     indent=2, ensure_ascii=False, default=str))
    key = load_key()
    if a.case_id in key:
        passed, fails, checks = code_check(r, key[a.case_id])
        print("\n  CODE CHECK   %s   %s" % ("PASS" if passed else "FAIL", checks))
        for f in fails:
            print("      %s" % f)
        print("\n  JUDGEMENT CHECK - not automated here. Someone reads the reason and rules on each item:")
        for item in prepare_judgement_check(r, key[a.case_id])["must_record"]:
            print("      [ ] %s" % item)
        sys.exit(0 if passed else 1)
    print("\n  (no label in the answer key for %s - not graded)" % a.case_id)
    sys.exit(0)

# ---- the set ------------------------------------------------------------------------
run_set(cases=a.cases.split(",") if a.cases else None, policy=a.policy, version=a.tools, mode=a.mode,
        trials_negative=a.trials, verbose=a.verbose, write=a.write, label=a.label, dedupe=dedupe,
        max_turns=a.max_turns, max_tokens=a.max_tokens, autonomy=a.autonomy, backend=a.backend)
