"""
PE6201 · A2 · Problem A — THE HARNESS  (D4, D5)
====================================================================
Load the answer key, run cases, grade them, report, save.

THE TWO KINDS OF CHECK
    code_check      compares the record with the answer key, joined on case_id:
                    decision · the single trigger · the named missing line ·
                    approved_total when the key states one · the gated action
                    fired exactly once (approve) or not at all (ask / escalate).
                    No model, no person, no opinion.
    judgement       `must_record` items are English. prepare_judgement_check builds
                    the queue; a person or a second model rules on each
                    (judge.py, when present, does the second and is named).

TRIALS: one per ordinary case, three per negative case (anything except the act),
fresh state per run. Every pass rate is saved beside its trial count.
====================================================================
"""
import json
import os
import re
import statistics
import traceback
from datetime import datetime

import config
import prompt
from agent import run_case

CODE_RE = re.compile(r"\b(\d{5})\b")
TOTAL_RE = re.compile(r"approved_total (\d+)")
STRIP = ("transcript", "tool_log", "raw_replies")


# ── loading ───────────────────────────────────────────────────────────────────
def load_key():
    with open(os.path.join(config.data_root(), "expected_outcomes_A.json"), encoding="utf-8") as fh:
        return {r["case_id"]: r for r in json.load(fh)}


def load_cases():
    with open(os.path.join(config.data_root(), "data_A", "claims.json"), encoding="utf-8") as fh:
        return [r["claim_id"] for r in json.load(fh)]


def is_negative(expected):
    return bool(expected) and expected.get("expected_decision") != "approve_in_principle"


# ── the code check ────────────────────────────────────────────────────────────
def code_check(record, expected):
    """Returns (passed, fails, checks). Checks the thing we care about, never a
    string that usually accompanies it."""
    checks, fails = {}, []
    want = expected["expected_decision"]
    checks["decision"] = record.get("decision") == want
    if not checks["decision"]:
        fails.append("decision %r, expected %r" % (record.get("decision"), want))
    if want == "escalate":
        checks["trigger"] = record.get("trigger") == expected.get("trigger")
        if not checks["trigger"]:
            fails.append("trigger %r, expected %r" % (record.get("trigger"), expected.get("trigger")))
    if want == "request_document":
        codes = CODE_RE.findall(expected.get("missing", ""))
        checks["missing_line"] = all(c in str(record.get("missing") or "") for c in codes)
        if not checks["missing_line"]:
            fails.append("missing %r does not name line %s" % (record.get("missing"), codes))
    if want == "approve_in_principle":
        m = next((TOTAL_RE.search(s) for s in expected.get("must_record", []) if TOTAL_RE.search(s)), None)
        if m:
            checks["approved_total"] = record.get("approved_total") == int(m.group(1))
            if not checks["approved_total"]:
                fails.append("approved_total %r, expected %s" % (record.get("approved_total"), m.group(1)))
    # the gated action: exactly once for an approve (or held under `suggest`), never otherwise
    writes = record.get("writes", 0)
    if want == "approve_in_principle":
        checks["gated_once"] = writes == 1 or str(record.get("gate", "")).startswith("suggest")
    else:
        checks["gated_once"] = writes == 0
    if not checks["gated_once"]:
        fails.append("gated action fired %d time(s) for a %s" % (writes, want))
    return all(checks.values()), fails, checks


def prepare_judgement_check(record, expected):
    return {"case_id": record["case_id"], "decision": record.get("decision"),
            "reason": record.get("reason", ""), "must_record": expected.get("must_record", []),
            "verdict": None, "graded_by": None}


def got_text(record):
    if record.get("decision") is None:
        return record.get("stopped_by") and "HALTED: %s" % record["stopped_by"] or "no decision"
    return record["decision"] + ("/%s" % record["trigger"] if record.get("trigger") else "") + \
        (" / %s" % record["missing"] if record.get("missing") else "")


# ── running the set ───────────────────────────────────────────────────────────
def run_set(cases=None, policy="careful", version="v2", mode=None, trials_negative=3, trials_ordinary=1,
            verbose=False, write=False, label=None, dedupe=None, max_turns=None, max_tokens=None,
            autonomy=None, approve=None, backend=None, quiet=False, save_results=True):
    backend = backend or config.BACKEND
    key = load_key()
    cases = cases or [c for c in load_cases() if c in key]
    unknown = [c for c in cases if c not in key]
    if unknown:
        raise SystemExit("no label in expected_outcomes_A.json for: %s (run data/check_my_data.py)" % ", ".join(unknown))
    mode_eff = mode or ("sequential" if policy in ("sequential", "repeats") else "parallel")
    label = label or "%s_%s_%s_%s" % (backend, policy if backend == "scripted" else config.MODEL, version, mode_eff)
    stem = re.sub(r"[^\w.-]+", "_", label)
    tdir = os.path.join(config.RESULTS_DIR, "transcripts", stem)

    runs, queue = [], []
    for cid in cases:
        exp = key[cid]
        n = trials_negative if is_negative(exp) else trials_ordinary
        for t in range(1, n + 1):
            try:
                r = run_case(cid, policy, version, mode, approve=approve, verbose=verbose, write=write,
                             max_turns=max_turns, max_tokens=max_tokens, dedupe=dedupe, autonomy=autonomy,
                             backend=backend)
            except Exception as e:                       # one live failure is a failed trial, not an abort
                r = {"case_id": cid, "decision": None, "reason": "run raised: %s" % e, "turns": 0,
                     "model_calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "writes": 0,
                     "evidence": [], "guardrails_fired": [], "stopped_by": "exception",
                     "transcript": [{"role": "error", "content": traceback.format_exc()}], "tool_log": []}
            passed, fails, checks = code_check(r, exp)
            if save_results and (not passed or r.get("stopped_by")):
                _save_transcript(tdir, cid, t, r)
            runs.append({"case_id": cid, "trial": t, "family": exp.get("family"), "negative": is_negative(exp),
                         "expected": exp["expected_decision"], "expected_trigger": exp.get("trigger"),
                         "expected_missing": exp.get("missing"), "got": got_text(r), "pass": passed,
                         "check": "code", "checks": checks, "fails": fails, "turns": r["turns"],
                         "model_calls": r.get("model_calls"), "tok_in": r["tokens_in"], "tok_out": r["tokens_out"],
                         "cost_usd": round(r["cost_usd"], 6), "stopped_by": r.get("stopped_by"),
                         "guardrails_fired": r.get("guardrails_fired"), "evidence": r.get("evidence"),
                         "tool_log": r.get("tool_log"),
                         "record": {k: v for k, v in r.items() if k not in STRIP}})
            if t == 1:
                queue.append(prepare_judgement_check(r, exp))

    summary = summarise(runs, label, backend, policy, version, mode_eff, autonomy, dedupe, max_turns, max_tokens)
    if not quiet:
        print_table(runs, summary)
    if save_results:
        save(summary, runs, queue, stem)
    return summary, runs, queue


def _save_transcript(tdir, cid, trial, r):
    os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(tdir, "%s_t%d.txt" % (cid, trial)), "w", encoding="utf-8") as fh:
        fh.write("case %s trial %d · decision %s · stopped_by %s\n\n" % (cid, trial, r.get("decision"), r.get("stopped_by")))
        for e in r.get("transcript", []):
            fh.write("[%s]\n%s\n\n" % (e["role"], e["content"]))
        if r.get("raw_replies"):
            fh.write("\n---- raw model replies ----\n")
            for i, raw in enumerate(r["raw_replies"], 1):
                fh.write("[%d]\n%s\n\n" % (i, raw))


# ── summary ───────────────────────────────────────────────────────────────────
def summarise(runs, label, backend, policy, version, mode, autonomy, dedupe, max_turns, max_tokens):
    total, passed = len(runs), sum(1 for x in runs if x["pass"])
    neg = [x for x in runs if x["negative"]]
    neg_pass = sum(1 for x in neg if x["pass"])
    turns = [x["turns"] for x in runs]
    tmed = statistics.median(turns) if turns else None
    P = passed / total if total else 0.0
    by_tool = {}
    for x in runs:
        for t in x.get("tool_log") or []:
            by_tool.setdefault(t["tool"], []).append(t["obs_tokens"])
    stops = {}
    for x in runs:
        if x["stopped_by"]:
            stops[x["stopped_by"]] = stops.get(x["stopped_by"], 0) + 1
    return {
        "label": label, "backend": backend, "model": config.MODEL if backend == "live" else None,
        "policy": policy if backend == "scripted" else None, "tool_version": version, "mode": mode,
        "autonomy": autonomy or config.AUTONOMY, "dedupe": config.DEDUPE if dedupe is None else dedupe,
        "max_turns": max_turns or config.MAX_TURNS, "max_tokens": max_tokens or config.MAX_TOKENS_PER_RUN,
        "date": datetime.now().isoformat(timespec="seconds"),
        "cases": len({x["case_id"] for x in runs}), "negative_cases": len({x["case_id"] for x in neg}),
        "trials": total, "passed": passed, "pass_rate": round(P, 4) if total else None,
        "negative_trials": len(neg), "negative_passed": neg_pass,
        "negative_pass_rate": round(neg_pass / len(neg), 4) if neg else None,
        "turns_median": tmed, "turns_max": max(turns) if turns else None,
        "model_calls_median": statistics.median([x["model_calls"] or 0 for x in runs]) if runs else None,
        "implied_step_reliability": round(P ** (1.0 / tmed), 4) if (tmed and P > 0) else None,
        "halted": stops, "cap_hits": sum(stops.values()),
        "tok_in_total": sum(x["tok_in"] for x in runs), "tok_out_total": sum(x["tok_out"] for x in runs),
        "tok_in_per_run": round(sum(x["tok_in"] for x in runs) / total, 1) if total else None,
        "tokens_measured": all(x["record"].get("tokens_measured") for x in runs) if runs else None,
        "cost_total_usd": round(sum(x["cost_usd"] for x in runs), 6),
        "cost_per_run_usd": round(sum(x["cost_usd"] for x in runs) / total, 6) if total else None,
        "price_in": config.PRICE_IN, "price_out": config.PRICE_OUT,
        "system_prompt_tokens": prompt.est_tokens(prompt.build_system_prompt(version, mode)),
        "tool_block_tokens": prompt.est_tokens(prompt.tool_block(version)),
        "obs_tokens_by_tool": {k: {"calls": len(v), "mean": round(sum(v) / len(v), 1)} for k, v in sorted(by_tool.items())},
    }


def print_table(runs, s):
    print("\n%-9s %-34s %-22s %-44s %5s %5s %9s  pass" % ("case", "family", "expected", "got", "turns", "calls", "cost"))
    print("-" * 140)
    seen = {}
    for x in runs:
        seen.setdefault(x["case_id"], []).append(x)
    for cid, xs in seen.items():
        lastx, p, n = xs[-1], sum(1 for x in xs if x["pass"]), len(xs)
        print("%-9s %-34s %-22s %-44s %5s %5s %9.5f  %d/%d%s%s" % (
            cid, (lastx["family"] or "")[:34], lastx["expected"], lastx["got"][:44], lastx["turns"],
            lastx["model_calls"], lastx["cost_usd"], p, n, " *" if lastx["negative"] else "",
            "" if p == n else "  <- FAIL"))
    print("-" * 140)
    print("%s  |  %d/%d trials passed = %.1f%%  |  negatives %d/%d  |  turns median %s max %s  |  halted %s"
          "  |  tokens in %s out %s (%s)  |  US$%.4f  |  implied s = %s"
          % (s["label"], s["passed"], s["trials"], 100 * (s["pass_rate"] or 0), s["negative_passed"],
             s["negative_trials"], s["turns_median"], s["turns_max"], s["halted"] or 0,
             format(s["tok_in_total"], ","), format(s["tok_out_total"], ","),
             "measured" if s["tokens_measured"] else "chars/4 estimate", s["cost_total_usd"],
             s["implied_step_reliability"]))
    print("   * = negative case, 3 trials. Every trial above is a CODE check; the judgement queue is in the JSON.")


def save(summary, runs, queue, stem):
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    with open(os.path.join(config.RESULTS_DIR, "eval_%s.json" % stem), "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "runs": runs, "judgement_queue": queue}, fh, indent=1,
                  ensure_ascii=False, default=str)
    lines = ["# %s" % summary["label"], "",
             "date %s · backend %s · model %s · policy %s · tools %s · mode %s · autonomy %s · dedupe %s · "
             "cap %s turns / %s tokens · prices %s/%s US$/M"
             % (summary["date"], summary["backend"], summary["model"], summary["policy"], summary["tool_version"],
                summary["mode"], summary["autonomy"], summary["dedupe"], summary["max_turns"], summary["max_tokens"],
                summary["price_in"], summary["price_out"]), "",
             "**%d/%d trials passed (%.1f%%)**, negatives %d/%d, turns median %s max %s, halted %s, "
             "tokens in %s out %s (%s), cost US$%.4f, implied per-step reliability s = %s"
             % (summary["passed"], summary["trials"], 100 * (summary["pass_rate"] or 0), summary["negative_passed"],
                summary["negative_trials"], summary["turns_median"], summary["turns_max"], summary["halted"] or 0,
                format(summary["tok_in_total"], ","), format(summary["tok_out_total"], ","),
                "measured" if summary["tokens_measured"] else "chars/4 estimate", summary["cost_total_usd"],
                summary["implied_step_reliability"]), "",
             "system prompt %s tokens, of which the tool block is %s. Observation tokens per call: %s" % (
                 summary["system_prompt_tokens"], summary["tool_block_tokens"],
                 ", ".join("%s %s (n=%d)" % (k, v["mean"], v["calls"]) for k, v in summary["obs_tokens_by_tool"].items())),
             "",
             "| case | family | expected | got | check | turns | calls | tok_in | tok_out | cost | pass |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in runs:
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %.5f | %s |" % (
            x["case_id"], x["family"], x["expected"], x["got"], x["check"], x["turns"], x["model_calls"],
            x["tok_in"], x["tok_out"], x["cost_usd"], "PASS" if x["pass"] else "FAIL"))
    with open(os.path.join(config.RESULTS_DIR, "eval_%s.md" % stem), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
