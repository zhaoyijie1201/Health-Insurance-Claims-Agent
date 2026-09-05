#!/usr/bin/env python
"""
PE6201 · A2 · Problem A — D7 FAILURE 1: the loop-control failure
====================================================================
    python demo_loop_failure.py            -> results/d7_loop_failure.md

"The working agent, minus X." Two deletions are shown, and only one is the fix.

    the behaviour   `repeats` is the sequential agent with ONE guard deleted from
                    the decision-maker: it never notices the policy row has
                    already arrived, so it asks for it again every turn. A model
                    with no memory of its own actions. Nothing crashes.
    the fix         action de-duplication, in the CODE layer (guardrails.py).
                    Delete it (`--no-dedupe`) and the same agent runs to the
                    step cap on 24 of 33 trials at 2.3x the set's tokens (4.5x on the case).

Four things reported, as the brief asks: the instrumentation that found it, the
turn distribution across the whole set, which guard caught it and why the other
two would not have, and the before/after table. Everything here is scripted,
free, and reproduces for a marker.
====================================================================
"""
import os

import config
from agent import run_case
from harness import run_set

OUT = os.path.join(config.RESULTS_DIR, "d7_loop_failure.md")


def one(cid, **kw):
    r = run_case(cid, write=False, **kw)
    return "turns %2d · calls %2d · tokens %6d · US$%.5f · decision %-20s · stopped_by %s" % (
        r["turns"], len(r["evidence"]), r["tokens_in"] + r["tokens_out"], r["cost_usd"],
        r["decision"], r["stopped_by"])


def main():
    print()
    print(config.summary())
    print("\nONE CASE, CLM-8842, three ways")
    print("  working agent (sequential)      ", one("CLM-8842", policy="sequential"))
    print("  minus the memory (repeats)       ", one("CLM-8842", policy="repeats"))
    print("  minus memory AND de-duplication  ", one("CLM-8842", policy="repeats", dedupe=False))

    print("\nTHE WHOLE SET, the same three ways (33 trials each)")
    base, _, _ = run_set(policy="sequential", quiet=True, label="d7_before_sequential")
    caught, _, _ = run_set(policy="repeats", quiet=True, label="d7_repeats_dedupe_on")
    runaway, _, _ = run_set(policy="repeats", dedupe=False, quiet=True, label="d7_repeats_dedupe_off")
    par, _, _ = run_set(policy="careful", quiet=True, label="d7_after_parallel")

    rows = [("working agent, sequential (before)", base),
            ("minus the memory, de-duplication ON (caught)", caught),
            ("minus the memory, de-duplication OFF (runaway)", runaway),
            ("working agent, parallel (shipped)", par)]
    hdr = "| configuration | pass | turns median | turns max | halted | tokens in | cost US$ | tokens vs before |"
    lines = ["# D7 · failure 1 · the loop-control failure", "",
             "Scripted backend, %d cases, 3 trials per negative case. Tokens are chars/4 estimates with the same "
             "shape as a live bill (prefix re-sent every turn)." % base["cases"], "", hdr, "|---|---|---|---|---|---|---|---|"]
    for name, s in rows:
        lines.append("| %s | %d/%d | %s | %s | %s | %s | %.4f | %.2fx |" % (
            name, s["passed"], s["trials"], s["turns_median"], s["turns_max"], s["halted"] or 0,
            format(s["tok_in_total"], ","), s["cost_total_usd"], s["tok_in_total"] / base["tok_in_total"]))
    lines += ["",
              "## 1 · The instrumentation that found it",
              "Turns, model calls, tokens and cost are logged per run (agent.py). With de-duplication deleted, "
              "nothing raised an exception: %d of %d trials ran to the step cap of %d turns and the set cost %.2fx "
              "the working agent's tokens. The runs that did not loop are the escalations that end before the "
              "policy row is needed twice." % (runaway["halted"].get("step_cap", 0), runaway["trials"],
                                               config.MAX_TURNS, runaway["tok_in_total"] / base["tok_in_total"]),
              "",
              "## 2 · The turn distribution",
              "Working agent: median %s, worst legitimate run %s (CLM-8960, four lines, sequential). Runaway: median %s, "
              "max %s, %d trials at the cap. Caught: median %s, every looping trial stopped at turn 3."
              % (base["turns_median"], base["turns_max"], runaway["turns_median"], runaway["turns_max"],
                 runaway["halted"].get("step_cap", 0), caught["turns_median"]),
              "",
              "## 3 · The fix, in the code layer, and why the other two guards were the wrong place",
              "Action de-duplication caught it at turn 3, the first repeat, and named the cause "
              "(`duplicate_action: lookup_policy called again with identical arguments`). The step cap only fires at "
              "turn %d, seven turns and about four times the tokens later, and says nothing about why. The budget "
              "ceiling (%d tokens) never fired: the runaway peaked below it, so a ceiling set from the legitimate "
              "worst case bounds the damage but does not detect the fault. A prompt fix cannot be relied on: the model "
              "is the thing that forgot; only the code layer remembers." % (config.MAX_TURNS, config.MAX_TOKENS_PER_RUN),
              "",
              "## 4 · Before and after",
              "Restoring the guard truncates no legitimate run: the working agent passes %d/%d with the guard on, its "
              "worst legitimate run (%s turns) is inside the cap of %d, and no correct run ever repeats an action. "
              "The parallel form of the same agent passes %d/%d at %.0f%% of the sequential tokens (D2c)."
              % (base["passed"], base["trials"], base["turns_max"], config.MAX_TURNS, par["passed"], par["trials"],
                 100.0 * par["tok_in_total"] / base["tok_in_total"]),
              ""]
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines[4:4 + 2 + len(rows)]))
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()
