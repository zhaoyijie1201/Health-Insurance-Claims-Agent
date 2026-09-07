#!/usr/bin/env python
"""
PE6201 · A2 · Problem A — WHICH CHECK EACH CASE USED  (D4)
====================================================================
    python checks.py                     -> results/checks_<label>.md, one per results file

The brief asks the results table to say, per case, which kind of check graded
it. run_eval.py writes the CODE check per trial (results/eval_*.md) and judge.py
writes the JUDGEMENT check per case (results/judge_*.md). This joins the two:
one row per case with both verdicts and a "checks used" column, for every
results file that has a judgement file beside it (and code-only rows for the
rest).
====================================================================
"""
import glob
import json
import os

import config


def main():
    written = []
    for path in sorted(glob.glob(os.path.join(config.RESULTS_DIR, "eval_*.json"))):
        stem = os.path.basename(path)[5:-5]
        if stem.startswith("d7_"):
            continue
        d = json.load(open(path, encoding="utf-8"))
        jpath = os.path.join(config.RESULTS_DIR, "judge_%s.json" % stem)
        judge = {r["case_id"]: r for r in json.load(open(jpath, encoding="utf-8"))["rows"]} if os.path.exists(jpath) else {}
        if not judge and d["summary"]["backend"] == "scripted" and stem != "scripted_careful_v2_parallel":
            continue                      # the scripted variants are code-checked only; one table is enough
        by_case = {}
        for x in d["runs"]:
            c = by_case.setdefault(x["case_id"], {"family": x["family"], "expected": x["expected"], "negative": x["negative"],
                                                 "trials": 0, "passed": 0, "got": x["got"], "checks": x["checks"]})
            c["trials"] += 1
            c["passed"] += 1 if x["pass"] else 0
        s = d["summary"]
        lines = ["# Checks used, case by case · %s" % s["label"], "",
                 "backend %s · model %s · tools %s · %s · %d trials. CODE = harness.code_check against the answer key "
                 "(decision, trigger, named line, approved_total, gated action once). JUDGEMENT = %s ruling on every "
                 "must_record item with the prompt in docs/JUDGE_PROMPT.md%s."
                 % (s["backend"], s["model"] or s["policy"], s["tool_version"], s["date"][:10], s["trials"],
                    (next(iter(judge.values()))["graded_by"] if judge else "not run"),
                    "" if judge else " (no judgement file for this run: rows below are code-checked only)"), "",
                 "| case | family | expected | checks used | code check (trials passed) | code fields checked | judgement (items met) | judgement misses |",
                 "|---|---|---|---|---|---|---|---|"]
        n_code = n_judge = n_both = 0
        for cid, c in by_case.items():
            j = judge.get(cid)
            used = "code + judgement" if j else "code"
            code = "%s %d/%d" % ("PASS" if c["passed"] == c["trials"] else "FAIL", c["passed"], c["trials"])
            fields = ", ".join(k for k in c["checks"])
            if j:
                jud = "%s %d/%d" % (j["verdict"], j["met"], j["total"])
                miss = "; ".join(v["item"] for v in j["items"] if not v["met"]).replace("|", "/")
                n_judge += j["verdict"] == "PASS"
                n_both += (c["passed"] == c["trials"]) and j["verdict"] == "PASS"
            else:
                jud, miss = "-", ""
            n_code += c["passed"] == c["trials"]
            lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (cid, c["family"], c["expected"], used, code, fields, jud, miss))
        lines += ["", "**%d/%d cases pass the code check on every trial%s.**" % (
            n_code, len(by_case),
            ("; %d/%d pass the judgement check; %d/%d pass both" % (n_judge, len(by_case), n_both, len(by_case))) if judge else ""), ""]
        out = os.path.join(config.RESULTS_DIR, "checks_%s.md" % stem)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        written.append((stem, len(by_case), n_code, n_judge if judge else None, n_both if judge else None))
    print("%-48s %5s %5s %6s %5s" % ("results file", "cases", "code", "judge", "both"))
    for stem, n, c, j, b in written:
        print("%-48s %5d %5d %6s %5s" % (stem, n, c, "-" if j is None else j, "-" if b is None else b))
    print("\nwrote %d files results/checks_*.md" % len(written))


if __name__ == "__main__":
    main()
