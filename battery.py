#!/usr/bin/env python
"""
PE6201 · A2 · Problem A — THE MODEL BATTERY, SUMMARISED  (D5b)
====================================================================
    python battery.py            -> results/battery.md

Reads every results/eval_live_*.json (and the matching judge_live_*.json when
present) and writes one table per model plus where the negative cases separated
them. Relative performance is the point, not a ranking: which model does OUR
job, at what cost, and where it diverges.
====================================================================
"""
import collections
import glob
import json
import os

import config

F = config.FAILURE_COST_USD


def main():
    rows = []
    for path in sorted(glob.glob(os.path.join(config.RESULTS_DIR, "eval_live_*.json"))):
        d = json.load(open(path, encoding="utf-8"))
        s = d["summary"]
        stem = os.path.basename(path)[5:-5]
        jpath = os.path.join(config.RESULTS_DIR, "judge_%s.json" % stem)
        judge = json.load(open(jpath, encoding="utf-8"))["summary"] if os.path.exists(jpath) else None
        fams = collections.Counter(x["family"] for x in d["runs"] if not x["pass"])
        wrong = collections.Counter()
        for x in d["runs"]:
            if not x["pass"]:
                wrong[(x["expected"], (x["got"] or "").split("/")[0].split(" ")[0])] += 1
        rows.append({"stem": stem, "model": s["model"], "tools": s["tool_version"], "trials": s["trials"],
                     "passed": s["passed"], "pass_rate": s["pass_rate"], "neg_passed": s["negative_passed"],
                     "neg_trials": s["negative_trials"], "turns_median": s["turns_median"], "turns_max": s["turns_max"],
                     "tok_in": s["tok_in_per_run"], "tok_out": round(s["tok_out_total"] / s["trials"]),
                     "price": (s["price_in"], s["price_out"]), "cost": s["cost_total_usd"],
                     "per_run": s["cost_per_run_usd"], "s": s["implied_step_reliability"], "halted": s["halted"],
                     "measured": s["tokens_measured"], "date": s["date"][:10],
                     "judge": judge, "fams": fams, "wrong": wrong,
                     "reply_refused": sum(1 for x in d["runs"] for g in (x["guardrails_fired"] or []) if g["guardrail"] == "reply_refused"),
                     "final_refused": sum(1 for x in d["runs"] for g in (x["guardrails_fired"] or []) if g["guardrail"] == "final_refused"),
                     "per_task": s["cost_per_run_usd"] + (1 - s["pass_rate"]) * F})
    if not rows:
        raise SystemExit("no results/eval_live_*.json yet")
    rows.sort(key=lambda r: (r["tools"] != "v2", -r["pass_rate"]))

    lines = ["# D5(b) · The live battery", "",
             "Same 45 cases, same v2 prompt and tools, same commit; the model id is the only thing that differs. "
             "One trial per ordinary case, three per negative case: %d trials per model. Token counts are the "
             "API's usage block. Cost per successful task adds the measured failure rate at US$%.2f per escalation "
             "(D6). One member, one key, one model." % (rows[0]["trials"], F), "",
             "| model | tools | pass | negatives | turns med/max | tokens in/out per run | price in/out $/M | battery US$ | per run US$ | per successful task US$ | implied s | halted | judgement (cases all items met) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        j = "%d/%d cases, %d/%d items" % (r["judge"]["cases_all_items_met"], r["judge"]["cases"], r["judge"]["items_met"], r["judge"]["items"]) if r["judge"] else "-"
        lines.append("| %s | %s | %d/%d (%.1f%%) | %d/%d | %s / %s | %s / %s | %.2f / %.2f | %.2f | %.4f | **%.3f** | %s | %s | %s |" % (
            r["model"], r["tools"], r["passed"], r["trials"], 100 * r["pass_rate"], r["neg_passed"], r["neg_trials"],
            r["turns_median"], r["turns_max"], format(r["tok_in"], ","), r["tok_out"], r["price"][0], r["price"][1],
            r["cost"], r["per_run"], r["per_task"], r["s"], r["halted"] or 0, j))
    lines += ["", "## Where the negative cases separated them", "",
              "Failed trials by case family (three trials per negative case, so 3 means the model missed it every time).", ""]
    allfams = sorted({f for r in rows for f in r["fams"]})
    hdr = "| family | " + " | ".join(r["model"].split("/")[-1] + (" v1" if r["tools"] == "v1" else "") for r in rows) + " |"
    lines += [hdr, "|---|" + "---|" * len(rows)]
    for fam in allfams:
        lines.append("| %s | %s |" % (fam, " | ".join(str(r["fams"].get(fam, "")) for r in rows)))
    lines += ["", "## What the wrong answers were", ""]
    for r in rows:
        if not r["wrong"]:
            continue
        top = "; ".join("expected %s, got %s x%d" % (e, g, n) for (e, g), n in r["wrong"].most_common(4))
        lines.append("- **%s%s**: %s. Format slips: %d replies refused as non-JSON, %d finals refused."
                     % (r["model"], " v1" if r["tools"] == "v1" else "", top, r["reply_refused"], r["final_refused"]))
    lines += ["", "## Reading it", ""]
    v2 = [r for r in rows if r["tools"] == "v2"]
    if v2:
        best = max(v2, key=lambda r: r["pass_rate"])
        cheapest_ok = [r for r in v2 if r["pass_rate"] >= 0.95]
        cheapest_ok = min(cheapest_ok, key=lambda r: r["per_run"]) if cheapest_ok else None
        worst_value = max(v2, key=lambda r: r["per_task"])
        lines.append("- Highest pass rate: **%s** at %.1f%%, US$%.4f a run, US$%.3f per successful task once its own "
                     "failures are priced." % (best["model"], 100 * best["pass_rate"], best["per_run"], best["per_task"]))
        if cheapest_ok:
            lines.append("- Cheapest model that cleared 95%%: **%s** at US$%.4f a run." % (cheapest_ok["model"], cheapest_ok["per_run"]))
        lines.append("- Worst value per successful task: **%s** at US$%.3f: cheap tokens, expensive failures. On this "
                     "problem a wrong answer costs US$%.2f and the token bill of a run is under a cent, so the "
                     "ranking by cost per successful task is the ranking by pass rate." % (worst_value["model"], worst_value["per_task"], F))
    v1 = [r for r in rows if r["tools"] == "v1"]
    if v1 and any(r["model"] == v1[0]["model"] and r["tools"] == "v2" for r in rows):
        a = v1[0]; b = next(r for r in rows if r["model"] == a["model"] and r["tools"] == "v2")
        lines.append("- **D2(b), same model, v1 to v2 tools**: %s went from %d/%d (%.1f%%) to %d/%d (%.1f%%); tokens in "
                     "per run %s to %s. The descriptor and interface rewrite, not the model, moved %d trials."
                     % (a["model"], a["passed"], a["trials"], 100 * a["pass_rate"], b["passed"], b["trials"],
                        100 * b["pass_rate"], format(a["tok_in"], ","), format(b["tok_in"], ","), b["passed"] - a["passed"]))
    lines.append("")
    out = os.path.join(config.RESULTS_DIR, "battery.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines[:5 + len(rows)]))
    print("\nwrote %s" % out)


if __name__ == "__main__":
    main()
