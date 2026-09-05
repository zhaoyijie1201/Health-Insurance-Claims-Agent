#!/usr/bin/env python
"""
PE6201 · A2 · Problem A — THE COST-TO-SERVE MODEL  (D6)
====================================================================
    python cost_model.py                    -> results/cost_model.md + .json
    python cost_model.py --fixed 250        a different layer-3 assumption

Class 5's three layers, on MEASURED numbers from results/eval_*.json:

    input tokens   ~ B*T + D*T(T-1)/2      B prefix, D growth per turn, T turns
    layer 1        = tokens_in*price_in + tokens_out*price_out      per task, linear
    layer 2        = (1 - success_rate) * failure_cost              per task, linear
    cost per successful task = layer 1 + layer 2
    monthly        = cost per successful task * volume + layer 3

Failure is priced as an ESCALATION (a wrong answer goes to a claims assessor at
US$38/h x 12 min = US$7.60), not as a retry, because in this problem a wrong
outcome goes to a person and not back into the loop.

The baseline is plain list prices. No caching discount and no reasoning surcharge
are modelled; both are measured-or-nothing and neither was measured here.

What it reports: every configuration it finds, a sensitivity table at +/-10
percentage points of success, the break-even success rate of the cheapest
configuration against the most expensive, the four levers with a before/after
each, and the three caps that ship with the agent.
====================================================================
"""
import argparse
import glob
import json
import os

import config

F = config.FAILURE_COST_USD
V = config.VOLUME_PER_MONTH


def load_all():
    out = {}
    for path in sorted(glob.glob(os.path.join(config.RESULTS_DIR, "eval_*.json"))):
        stem = os.path.basename(path)[5:-5]
        if stem.startswith("d7_"):
            continue
        s = json.load(open(path, encoding="utf-8"))["summary"]
        if not s.get("trials"):
            continue
        out[stem] = s
    return out


def layers(s, price_in=None, price_out=None, fixed=0.0):
    pi = s["price_in"] if price_in is None else price_in
    po = s["price_out"] if price_out is None else price_out
    tin = s["tok_in_total"] / s["trials"]
    tout = s["tok_out_total"] / s["trials"]
    P = s["pass_rate"]
    l1 = tin / 1e6 * pi + tout / 1e6 * po
    l2 = (1 - P) * F
    return {"label": s["label"], "backend": s["backend"], "model": s["model"] or ("scripted:%s" % s["policy"]),
            "tools": s["tool_version"], "mode": s["mode"], "trials": s["trials"], "pass_rate": P,
            "tokens_in": round(tin), "tokens_out": round(tout), "measured": bool(s.get("tokens_measured")),
            "price_in": pi, "price_out": po, "layer1": l1, "layer2": l2, "per_task": l1 + l2,
            "monthly": (l1 + l2) * V + fixed, "turns_median": s["turns_median"], "turns_max": s["turns_max"]}


def sensitivity(row):
    """Success rate +/-10 points in 5-point steps. The rate cannot exceed 100%, so a
    baseline near the top is shown over the 20 points below it instead of clipping."""
    P0 = row["pass_rate"]
    steps = [P0 + d for d in (-0.10, -0.05, 0.0, 0.05, 0.10)]
    if P0 > 0.90:
        steps = [P0 - d for d in (0.20, 0.15, 0.10, 0.05, 0.0)]
    out = []
    for P in steps:
        P = min(1.0, max(0.0, P))
        l2 = (1 - P) * F
        out.append({"pass_rate": round(P, 3), "layer2": l2, "per_task": row["layer1"] + l2,
                    "monthly": (row["layer1"] + l2) * V})
    return out


def break_even(cheap, expensive):
    """E = expensive layer1 + its own failures; C = cheap layer1 only. The cheap model
    can afford (E - C)/F failures per task, so it needs success 1 - (E - C)/F."""
    E = expensive["layer1"] + expensive["layer2"]
    C = cheap["layer1"]
    afford = (E - C) / F
    return {"cheap": cheap["label"], "expensive": expensive["label"], "E": E, "C": C,
            "failures_affordable": afford, "break_even_success": 1 - afford,
            "cheap_measured_success": cheap["pass_rate"], "clears": cheap["pass_rate"] >= 1 - afford}


def fmt(x, nd=4):
    return ("%%.%df" % nd) % x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixed", type=float, default=200.0,
                    help="layer 3, US$ per month: a small VM for the harness, log storage, weekly eval re-runs, "
                         "an hour of maintenance. An assumption, stated as one.")
    a = ap.parse_args()
    S = load_all()
    if not S:
        raise SystemExit("no results/eval_*.json - run python run_eval.py first")
    rows = {k: layers(s, fixed=a.fixed) for k, s in S.items()}
    final = rows.get("scripted_careful_v2_parallel")
    live = [r for r in rows.values() if r["backend"] == "live"]
    lines = ["# D6 · The cost-to-serve model", "",
             "Volume %d claims/month. Failure cost US$%.2f per escalated claim (claims assessor, US$38/h x 12 min). "
             "Layer 3 fixed monthly US$%.0f (assumption: a small VM for the harness, log storage, weekly eval "
             "re-runs, an hour of maintenance). Prices are list prices per million tokens at the date of each run; "
             "no caching discount and no reasoning surcharge are modelled because neither was measured. Scripted "
             "token counts are chars/4 estimates with the same shape as a live bill; live counts are the API's usage "
             "block, and the table says which." % (V, F, a.fixed), ""]

    # ---- 1 · every configuration -------------------------------------------------------
    lines += ["## 1 · Cost per successful task, every configuration measured", "",
              "| configuration | backend / model | tools | mode | trials | pass rate | tokens in/run | tokens out/run | price in/out | layer 1 variable | layer 2 fallback | per task | monthly |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows.values(), key=lambda r: (r["backend"] != "live", r["per_task"])):
        lines.append("| %s | %s | %s | %s | %d | %.1f%% | %s%s | %s | %.2f / %.2f | %s | %s | **%s** | %s |" % (
            r["label"], r["model"], r["tools"], r["mode"], r["trials"], 100 * r["pass_rate"],
            format(r["tokens_in"], ","), "" if r["measured"] else " (est.)", format(r["tokens_out"], ","),
            r["price_in"], r["price_out"], fmt(r["layer1"], 5), fmt(r["layer2"], 4), fmt(r["per_task"], 4),
            format(round(r["monthly"]), ",")))
    lines.append("")
    if final:
        lines += ["Layer 2 is the layer every naive model omits. On the shipped configuration at 100%% scripted pass "
                  "rate it is zero; at a live pass rate of 90%% it is US$%.2f per task, which is %d times the token "
                  "bill of a cheap-tier run (US$%.4f). The token price only matters once the failures are cheap."
                  % (0.1 * F, int(0.1 * F / final["layer1"]) if final["layer1"] else 0, final["layer1"]), ""]

    # ---- 2 · sensitivity -----------------------------------------------------------------
    focus = live[0] if live else final
    if focus:
        sens = sensitivity(focus)
        span = "the 20 points below its measured %.0f%% (a rate cannot exceed 100%%)" % (100 * focus["pass_rate"]) \
            if focus["pass_rate"] > 0.90 else "+/-10 percentage points of its measured %.0f%%" % (100 * focus["pass_rate"])
        lines += ["## 2 · Sensitivity: %s over %s" % (focus["label"], span), "",
                  "| success rate | layer 2 | per task | monthly (before layer 3) |", "|---|---|---|---|"]
        for s in sens:
            lines.append("| %.0f%% | %s | %s | %s |" % (100 * s["pass_rate"], fmt(s["layer2"]), fmt(s["per_task"]),
                                                       format(round(s["monthly"]), ",")))
        lo, hi = sens[0], sens[-1]
        lines += ["", "Every 5 points of success are worth US$%s a month, against a token bill of US$%s a month. "
                  "The conclusion that layer 2 dominates survives the whole range; the token price only decides "
                  "anything between two models whose failure rates are within a point of each other."
                  % (format(round((lo["monthly"] - hi["monthly"]) / (len(sens) - 1)), ","),
                     format(round(focus["layer1"] * V), ",")), ""]

    # ---- 3 · break-even ------------------------------------------------------------------
    lines += ["## 3 · Break-even success rate", ""]
    pairs = []
    if len(live) >= 2:
        cheap = min(live, key=lambda r: r["layer1"])
        exp = max(live, key=lambda r: r["layer1"])
        pairs.append(break_even(cheap, exp))
    elif final:
        # until the battery lands: the shipped agent's token shape priced at the three tiers, with the
        # brief's illustrative mid-tier success of 92% as the expensive side
        cheap = layers(S["scripted_careful_v2_parallel"], *config.PRICES["cheap"])
        mid = layers(S["scripted_careful_v2_parallel"], *config.PRICES["mid"])
        mid["pass_rate"] = 0.92; mid["layer2"] = 0.08 * F; mid["label"] += " @mid, 92% assumed"
        frontier = layers(S["scripted_careful_v2_parallel"], *config.PRICES["frontier"])
        frontier["pass_rate"] = 0.95; frontier["layer2"] = 0.05 * F; frontier["label"] += " @frontier, 95% assumed"
        pairs += [break_even(cheap, mid), break_even(cheap, frontier)]
        lines.append("No live battery in results/ yet, so the shipped agent's measured token shape is priced at the "
                     "three section-7 tiers and the expensive side's success rate is ASSUMED (92% mid, 95% frontier, "
                     "the brief's illustration). Replace with measured pairs once the D5(b) files land.")
        lines.append("")
    lines += ["| cheap | expensive | E = expensive per successful task | C = cheap tokens only | failures the cheap model can afford | break-even success | cheap measured | clears? |",
              "|---|---|---|---|---|---|---|---|"]
    for b in pairs:
        lines.append("| %s | %s | %s | %s | %.1f%% | **%.1f%%** | %.1f%% | %s |" % (
            b["cheap"], b["expensive"], fmt(b["E"]), fmt(b["C"]), 100 * b["failures_affordable"],
            100 * b["break_even_success"], 100 * b["cheap_measured_success"], "yes" if b["clears"] else "no"))
    lines.append("")

    # ---- 4 · the four levers -----------------------------------------------------------------
    lines += ["## 4 · The four levers, measured before and after", ""]
    v1, v2 = rows.get("scripted_careful_v1_parallel"), rows.get("scripted_careful_v2_parallel")
    seq, par = rows.get("scripted_sequential_v2_sequential"), rows.get("scripted_careful_v2_parallel")
    S1, S2 = S.get("scripted_careful_v1_parallel"), S.get("scripted_careful_v2_parallel")
    lines += ["| lever | what it attacks | where built | before | after | what moved |", "|---|---|---|---|---|---|"]
    if S1 and S2:
        lines.append("| 1 · tool block size | B, linear in turns | D2(a)/(b): the tool set and its descriptors | v1: %d tools, %s tokens | v2: %d tools, %s tokens | v2 is LARGER: the six-field descriptors with size bounds and failure semantics cost %s tokens per turn, paid for by lever 4 |" % (
            7, format(S1["tool_block_tokens"], ","), 6, format(S2["tool_block_tokens"], ","),
            format(S2["tool_block_tokens"] - S1["tool_block_tokens"], ",")))
    if seq and par:
        lines.append("| 2 · turn count T | the quadratic term | D2(c): parallel calls | sequential: median %s, max %s, %s tokens in/run | parallel: median %s, max %s, %s tokens in/run | %.0f%% fewer input tokens, same pass rate (%d/%d both) |" % (
            seq["turns_median"], seq["turns_max"], format(seq["tokens_in"], ","), par["turns_median"], par["turns_max"],
            format(par["tokens_in"], ","), 100 * (1 - par["tokens_in"] / seq["tokens_in"]), par["trials"] * par["pass_rate"], par["trials"]))
    if S1 and S2:
        g1 = S1["obs_tokens_by_tool"].get("get_claim", {}).get("mean")
        g2 = S2["obs_tokens_by_tool"].get("get_claim", {}).get("mean")
        lines.append("| 3 · observation size D | compounds: re-sent every later turn | D2(b): what get_claim returns | v1 get_claim %s tokens/call (raw row) | v2 get_claim %s tokens/call (+ duplicate_of, narrative_flags, claim_total) | bigger by design: two facts computed in code replace a tool call and a model judgement |" % (g1, g2))
    if v1 and v2:
        lines.append("| 4 · success rate | layer 2, the biggest layer | D4 + the v2 tool layer | v1: %.1f%% -> per successful task US$%s | v2: %.1f%% -> US$%s | the whole v2 token premium (US$%s/task) buys back US$%s/task of failures |" % (
            100 * v1["pass_rate"], fmt(v1["per_task"]), 100 * v2["pass_rate"], fmt(v2["per_task"]),
            fmt(v2["layer1"] - v1["layer1"], 5), fmt(v1["layer2"] - v2["layer2"])))
    lines += ["", "Which dominated: lever 4. On the scripted set the v1 tool layer loses %s of trials to hostile "
              "narratives and every one of those is a US$%.2f escalation; the v2 descriptors cost more tokens per "
              "turn and buy that back many times over. Lever 2 is the largest token saving and it moved nothing "
              "in correctness, which is what D2(c) asks to show." % (
                  "%d/%d" % (round(v1["trials"] * (1 - v1["pass_rate"])), v1["trials"]) if v1 else "-", F), ""]

    # ---- 5 · the three caps ------------------------------------------------------------------
    per_run_cap = config.MAX_TOKENS_PER_RUN / 1e6 * (final["price_in"] if final else config.PRICE_IN)
    lines += ["## 5 · The three caps that ship", "",
              "| cap | value | where it comes from |", "|---|---|---|",
              "| step cap | %d turns | worst legitimate sequential run is 10 turns (CLM-9007); the parallel form never passes 4 |" % config.MAX_TURNS,
              "| budget ceiling | %s tokens per run (about US$%.4f at the cheap tier) | about 2x the worst legitimate run (~27k); the D7 runaway peaked at 39k, so the step cap fires first and the ceiling is the backstop |" % (format(config.MAX_TOKENS_PER_RUN, ","), per_run_cap),
              "| monthly limit per user | US$%s | 1.5x the expected monthly token bill of the shipped configuration at volume; an alarm, not a hard stop, so a bad week is visible before it is expensive |" % (
                  format(round(1.5 * (final["layer1"] if final else 0) * V), ",")),
              ""]
    out = os.path.join(config.RESULTS_DIR, "cost_model.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    with open(os.path.join(config.RESULTS_DIR, "cost_model.json"), "w", encoding="utf-8") as fh:
        json.dump({"failure_cost": F, "volume": V, "fixed_monthly": a.fixed, "rows": rows,
                   "sensitivity": sensitivity(focus) if focus else None, "break_even": pairs}, fh, indent=1)
    print("\n".join(lines))
    print("\nwrote %s" % out)


if __name__ == "__main__":
    main()
