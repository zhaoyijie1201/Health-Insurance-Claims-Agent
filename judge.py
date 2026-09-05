#!/usr/bin/env python
"""
PE6201 · A2 · Problem A — THE JUDGEMENT CHECK  (D4)
====================================================================
    python judge.py                                   grade results/eval_scripted_careful_v2_parallel.json
    python judge.py --results results/eval_live_....json --judge-model google/gemini-2.5-flash
    python judge.py --human --grader "Zhao Yijie"     a person rules on each item at the keyboard
    python judge.py --dry-run                         print the prompts, call nothing

The code check (harness.code_check) compares values from a fixed list: the decision,
the trigger, the named line, the total. It cannot tell whether the `reason` is a
reason. That is the judgement check: someone reads the record and rules on each
`must_record` item. Here that someone is either a person (--human) or a SECOND MODEL
that is named, prompted with the committed docs/JUDGE_PROMPT.md, and never the model
that produced the record.

Output: results/judge_<stem>.json and .md - one row per case, one verdict per item,
the grader named on every row, the judge's own token spend at the bottom.
====================================================================
"""
import argparse
import json
import os
import re
import sys

import config
from backends import _live_call

PROMPT_PATH = os.path.join(config.HERE, "docs", "JUDGE_PROMPT.md")
RECORD_FIELDS = ("case_id", "decision", "trigger", "escalate_to", "missing", "reason", "lines",
                 "approved_total", "refused_total", "evidence", "gate", "turns")


def load_prompt():
    text = open(PROMPT_PATH, encoding="utf-8").read()
    m = re.search(r"```\n(.*?)\n```", text, re.S)
    if not m:
        raise SystemExit("docs/JUDGE_PROMPT.md has no fenced prompt block")
    return m.group(1)


def items_from(data):
    """One judgement item per case, from trial 1: the record the code check saw plus
    the must_record list the answer key carries."""
    must = {q["case_id"]: q["must_record"] for q in data.get("judgement_queue", [])}
    out = []
    for x in data["runs"]:
        if x["trial"] != 1:
            continue
        rec = {k: x["record"].get(k) for k in RECORD_FIELDS}
        out.append({"case_id": x["case_id"], "family": x["family"], "record": rec,
                    "must_record": must.get(x["case_id"], []), "code_check": x["pass"]})
    return out


def build_prompt(template, item):
    return template.replace("{record}", json.dumps(item["record"], indent=1, ensure_ascii=False)) \
                   .replace("{items}", "\n".join("- " + m for m in item["must_record"]))


def _extract_json(text):
    s = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text or "", flags=re.S).strip()
    try:
        return json.loads(s)
    except ValueError:
        start = s.find("{")
        if start >= 0:
            try:
                return json.JSONDecoder().raw_decode(s[start:])[0]
            except ValueError:
                pass
    return None


def ask_model(template, item, judge_model):
    text, usage = _live_call([{"role": "user", "content": build_prompt(template, item)}],
                             model=judge_model, max_tokens=900)
    obj = _extract_json(text)
    verdicts = []
    if isinstance(obj, dict) and isinstance(obj.get("items"), list):
        by_text = {str(v.get("item", "")).strip(): v for v in obj["items"] if isinstance(v, dict)}
        for i, m in enumerate(item["must_record"]):
            v = by_text.get(m) or (obj["items"][i] if i < len(obj["items"]) else {})
            verdicts.append({"item": m, "met": bool(v.get("met")), "why": str(v.get("why", ""))[:200]})
    else:
        verdicts = [{"item": m, "met": False, "why": "judge reply unparseable: " + (text or "")[:80]}
                    for m in item["must_record"]]
    return verdicts, usage or (0, 0), text


def ask_human(item, grader):
    print("\n" + "=" * 70)
    print("  %s  (%s)   code check: %s" % (item["case_id"], item["family"], "PASS" if item["code_check"] else "FAIL"))
    print(json.dumps(item["record"], indent=1, ensure_ascii=False))
    verdicts = []
    for m in item["must_record"]:
        ans = input("  [%s] met? [y/n] " % m).strip().lower()
        verdicts.append({"item": m, "met": ans == "y", "why": "ruled by %s" % grader})
    return verdicts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default=os.path.join(config.RESULTS_DIR, "eval_scripted_careful_v2_parallel.json"))
    ap.add_argument("--judge-model", default="google/gemini-2.5-flash",
                    help="OpenRouter id of the grader; must differ from the graded model")
    ap.add_argument("--human", action="store_true", help="a person rules instead of a model")
    ap.add_argument("--grader", default="", help="the person's name for --human")
    ap.add_argument("--cases", default=None, help="comma-separated case ids; default all")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    data = json.load(open(a.results, encoding="utf-8"))
    graded_model = data["summary"].get("model") or "scripted:%s" % data["summary"].get("policy")
    if not a.human and a.judge_model == graded_model:
        raise SystemExit("the judge must not be the model being graded (%s)" % graded_model)
    grader = "person: %s" % (a.grader or "unnamed") if a.human else "model: %s" % a.judge_model
    template = load_prompt()
    items = items_from(data)
    if a.cases:
        want = set(a.cases.split(","))
        items = [i for i in items if i["case_id"] in want]
    print("\njudging %d cases from %s\n  graded: %s\n  grader: %s" % (len(items), os.path.basename(a.results), graded_model, grader))

    rows, tok_in, tok_out = [], 0, 0
    for it in items:
        if a.dry_run:
            print("\n" + build_prompt(template, it))
            continue
        if a.human:
            verdicts = ask_human(it, a.grader)
        else:
            verdicts, (ti, to), _ = ask_model(template, it, a.judge_model)
            tok_in += ti; tok_out += to
        met = sum(1 for v in verdicts if v["met"])
        rows.append({"case_id": it["case_id"], "family": it["family"], "decision": it["record"]["decision"],
                     "code_check": it["code_check"], "items": verdicts, "met": met, "total": len(verdicts),
                     "verdict": "PASS" if met == len(verdicts) else "FAIL", "graded_by": grader})
        print("  %-9s %s  %d/%d  %s" % (it["case_id"], rows[-1]["verdict"], met, len(verdicts),
                                         "; ".join(v["why"] for v in verdicts if not v["met"])[:90]))
    if a.dry_run:
        return
    stem = os.path.basename(a.results)[len("eval_"):-len(".json")]
    passed = sum(1 for r in rows if r["verdict"] == "PASS")
    items_total = sum(r["total"] for r in rows)
    items_met = sum(r["met"] for r in rows)
    summary = {"results_file": os.path.basename(a.results), "graded_model": graded_model, "grader": grader,
               "prompt": "docs/JUDGE_PROMPT.md", "cases": len(rows), "cases_all_items_met": passed,
               "items": items_total, "items_met": items_met,
               "judge_tokens_in": tok_in, "judge_tokens_out": tok_out}
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    with open(os.path.join(config.RESULTS_DIR, "judge_%s.json" % stem), "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "rows": rows}, fh, indent=1, ensure_ascii=False)
    lines = ["# Judgement check · %s" % stem, "",
             "graded: **%s** · grader: **%s** · prompt: `docs/JUDGE_PROMPT.md` · judge spend: %s in / %s out tokens"
             % (graded_model, grader, tok_in, tok_out), "",
             "**%d/%d cases carry every must_record item; %d/%d items met.** The code check is the pass rate; "
             "this table is the other half." % (passed, len(rows), items_met, items_total), "",
             "| case | family | decision | code check | items met | verdict | items not met |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        misses = "; ".join("%s (%s)" % (v["item"], v["why"]) for v in r["items"] if not v["met"]).replace("|", "/")
        lines.append("| %s | %s | %s | %s | %d/%d | %s | %s |" % (
            r["case_id"], r["family"], r["decision"], "PASS" if r["code_check"] else "FAIL", r["met"], r["total"],
            r["verdict"], misses))
    with open(os.path.join(config.RESULTS_DIR, "judge_%s.md" % stem), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n  %d/%d cases, %d/%d items · wrote results/judge_%s.{json,md}" % (passed, len(rows), items_met, items_total, stem))


if __name__ == "__main__":
    sys.exit(main())
