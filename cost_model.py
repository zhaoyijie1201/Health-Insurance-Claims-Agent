#!/usr/bin/env python
"""
PE6201 · A2 · Problem A — THE COST-TO-SERVE MODEL  (D6)
====================================================================
    python cost_model.py                    -> results/cost_model.md + .json
    python cost_model.py --fixed 250        a different layer-3 assumption

The calculator is the Class 5 Capsule 2 notebook's, reused as the brief asks: the
five functions below are copied from it (agent_input_tokens, variable_cost,
cost_per_successful_task, monthly, break_even_success_rate, sensitivity) and the
prices and labour rates are data in one block, dated. What is new is only the
input: MEASURED token counts and pass rates from results/eval_*.json.

    input tokens   ~ base*T + growth*T(T-1)/2     (the notebook's form; checked against measured)
    layer 1        = fresh_in*in + out*out                per task, linear
    layer 2        = (1 - success_rate) * failure_usd     per task, linear; the ESCALATION form
    cost per successful task = layer 1 + layer 2
    monthly        = cost per successful task * volume + layer 3

Failure is priced as an escalation (claims assessor, US$38/h x 12 min = US$7.60), not
as a retry, because in this problem a wrong outcome goes to a person and not back
into the loop. Baseline is list prices; no caching discount and no reasoning
surcharge are modelled because neither was measured.
====================================================================
"""
import argparse
import glob
import json
import os

import config

# ── PRICES and LABOUR: data, in one block, dated (notebook section 1) ─────────
PRICES = {tier: {"in": p[0], "out": p[1]} for tier, p in config.PRICES.items()}          # section-7 tiers
PRICES.update({m: {"in": p[0], "out": p[1]} for m, p in config.MODEL_PRICES.items()})    # list prices, 2026-09-05
LABOUR = {"claims_assessor": {"usd_per_hour": 38.0, "minutes_per_escalation": 12.0}}    # Appendix A
VOLUME = config.VOLUME_PER_MONTH


def escalation_cost(role):
    "Cost of one human fallback, in US dollars."
    r = LABOUR[role]
    return r["usd_per_hour"] * r["minutes_per_escalation"] / 60.0


# ── the notebook's functions, unchanged ───────────────────────────────────────
def agent_input_tokens(base, growth, turns):
    "Input tokens across a run: base*T + growth*T(T-1)/2. The API is stateless."
    return base * turns + growth * turns * (turns - 1) // 2


def variable_cost(tier, fresh_in=0, cached_in=0, out=0, retrieval_usd=0.0, tool_usd=0.0):
    "LAYER 1 - per-task variable cost, US dollars."
    p = PRICES[tier]
    assert fresh_in >= 0 and cached_in >= 0 and out >= 0, "token counts cannot be negative"
    return fresh_in / 1e6 * p["in"] + cached_in / 1e6 * p.get("cached_in", p["in"] * 0.1) + out / 1e6 * p["out"] + retrieval_usd + tool_usd


def cost_per_successful_task(var_usd, success_rate, failure_usd):
    "LAYER 1 + LAYER 2. The number to quote."
    assert 0.0 <= success_rate <= 1.0, "success rate is a probability, not a percentage"
    assert failure_usd >= 0, "a failure cannot cost less than nothing"
    return var_usd + (1.0 - success_rate) * failure_usd


def monthly(var_usd, success_rate, failure_usd, volume, fixed_monthly_usd=0.0):
    "Everything, for a month."
    return cost_per_successful_task(var_usd, success_rate, failure_usd) * volume + fixed_monthly_usd


def break_even_success_rate(cheap_var, dear_total, failure_usd):
    "The success rate the CHEAP option needs to match the expensive one."
    return 1.0 - (dear_total - cheap_var) / failure_usd


def sensitivity(var_usd, failure_usd, centre, spread=0.10, step=0.05):
    """Cost per successful task at centre +/- spread. A rate cannot exceed 100%, so a
    centre near the top is shown over the 2*spread below it instead of clipping."""
    pts = [centre + d for d in (-spread, -spread / 2, 0.0, spread / 2, spread)]
    if centre + spread > 1.0:
        pts = [centre - d for d in (2 * spread, 1.5 * spread, spread, spread / 2, 0.0)]
    return [{"pass_rate": round(min(1.0, max(0.0, p)), 3),
             "layer2": (1 - p) * failure_usd,
             "per_task": cost_per_successful_task(var_usd, p, failure_usd),
             "monthly": cost_per_successful_task(var_usd, p, failure_usd) * VOLUME} for p in pts]


# ── measured inputs ───────────────────────────────────────────────────────────
F = escalation_cost("claims_assessor")


def load_all():
    out = {}
    for path in sorted(glob.glob(os.path.join(config.RESULTS_DIR, "eval_*.json"))):
        stem = os.path.basename(path)[5:-5]
        if stem.startswith("d7_"):
            continue
        d = json.load(open(path, encoding="utf-8"))
        if d["summary"].get("trials"):
            out[stem] = d
    return out


def row_for(stem, d, fixed):
    s = d["summary"]
    tier = s["model"] if s["model"] in PRICES else config.PRICE_TIER
    tin = s["tok_in_total"] / s["trials"]
    tout = s["tok_out_total"] / s["trials"]
    P = s["pass_rate"]
    l1 = variable_cost(tier, fresh_in=tin, out=tout)
    per = cost_per_successful_task(l1, P, F)
    # the notebook's input formula, checked against the measured mean: base = the system
    # prompt plus the task line; growth = mean (reply + observation) per completed turn
    base = s["system_prompt_tokens"] + 20
    T = s["turns_median"] or 1
    growth = max(0.0, (tin - base * T) / max(1, T * (T - 1) / 2.0)) if T > 1 else 0.0
    return {"label": s["label"], "backend": s["backend"], "model": s["model"] or ("scripted:%s" % s["policy"]),
            "tools": s["tool_version"], "mode": s["mode"], "trials": s["trials"], "pass_rate": P,
            "tokens_in": round(tin), "tokens_out": round(tout), "measured": bool(s.get("tokens_measured")),
            "price_in": PRICES[tier]["in"], "price_out": PRICES[tier]["out"],
            "layer1": l1, "layer2": (1 - P) * F, "per_task": per, "fallback_share": (per - l1) / per if per else 0.0,
            "monthly": monthly(l1, P, F, VOLUME, fixed), "turns_median": s["turns_median"], "turns_max": s["turns_max"],
            "base": base, "growth": round(growth), "formula_in": agent_input_tokens(base, round(growth), int(round(T))),
            "date": s["date"][:10]}


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
    rows = {k: row_for(k, d, a.fixed) for k, d in S.items()}
    final = rows.get("scripted_careful_v2_parallel")
    live = [r for r in rows.values() if r["backend"] == "live"]

    lines = ["# D6 · The cost-to-serve model", "",
             "Computed with the Class 5 Capsule 2 notebook's functions (`variable_cost`, `cost_per_successful_task`, "
             "`monthly`, `break_even_success_rate`, `sensitivity`) on MEASURED inputs. Volume %d claims/month. Failure "
             "cost US$%.2f per escalated claim (`escalation_cost(\"claims_assessor\")`: US$38/h x 12 min), the escalation "
             "form because a wrong outcome goes to a person, not back into the loop. Layer 3 fixed monthly US$%.0f "
             "(assumption: a small VM for the harness, log storage, weekly eval re-runs, an hour of maintenance). "
             "Prices are OpenRouter list prices read on 2026-09-05; no caching discount and no reasoning surcharge are "
             "modelled because neither was measured. Scripted token counts are chars/4 estimates with the same shape as "
             "a live bill; live counts are the API's usage block." % (VOLUME, F, a.fixed), ""]

    # ---- 1 · every configuration -------------------------------------------------------
    lines += ["## 1 · Cost per successful task, every configuration measured", "",
              "| configuration | backend / model | tools | date | trials | pass rate | tokens in/run | tokens out/run | price in/out | layer 1 variable | layer 2 fallback | per successful task | fallback share | monthly |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows.values(), key=lambda r: (r["backend"] != "live", r["per_task"])):
        lines.append("| %s | %s | %s | %s | %d | %.1f%% | %s%s | %s | %.2f / %.2f | %s | %s | **%s** | %.0f%% | %s |" % (
            r["label"], r["model"], r["tools"], r["date"], r["trials"], 100 * r["pass_rate"],
            format(r["tokens_in"], ","), "" if r["measured"] else " (est.)", format(r["tokens_out"], ","),
            r["price_in"], r["price_out"], fmt(r["layer1"], 5), fmt(r["layer2"], 4), fmt(r["per_task"], 4),
            100 * r["fallback_share"], format(round(r["monthly"]), ",")))
    lines.append("")
    if live:
        best = min(live, key=lambda r: r["per_task"])
        lines += ["The fallback is %.0f%% to %.1f%% of cost per successful task across the live models (the notebook's "
                  "worked example: 81%% to 99.8%%). The cheapest model per successful task is **%s** at US$%s, the most "
                  "expensive per run." % (100 * min(r["fallback_share"] for r in live), 100 * max(r["fallback_share"] for r in live),
                                           best["model"], fmt(best["per_task"], 3)), ""]

    # ---- 2 · the input formula, checked ---------------------------------------------------
    lines += ["## 2 · The notebook's input formula against the measured bill", "",
              "`input ~ base*T + growth*T(T-1)/2` (the exact sum, Class 5's form). base is the system prompt plus the "
              "task line, growth the mean reply-plus-observation a completed turn adds, T the median turns. Shown for the "
              "shipped configuration both ways.", "",
              "| configuration | base | growth (derived) | T | formula input tokens | measured mean | turns max |", "|---|---|---|---|---|---|---|"]
    for k in ("scripted_careful_v2_parallel", "scripted_sequential_v2_sequential"):
        if k in rows:
            r = rows[k]
            lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (r["label"], format(r["base"], ","), format(r["growth"], ","),
                                                                   r["turns_median"], format(r["formula_in"], ","),
                                                                   format(r["tokens_in"], ","), r["turns_max"]))
    lines += ["", "Cutting turns from the sequential median to the parallel median attacks both terms; the prefix term "
              "(base*T) is the larger on our short loops, which is why lever 2 saved 30%% and not the 54%% of the brief's "
              "eight-to-four example.", ""]

    # ---- 3 · sensitivity -----------------------------------------------------------------
    focus = min(live, key=lambda r: r["per_task"]) if live else final
    if focus:
        sens = sensitivity(focus["layer1"], F, focus["pass_rate"])
        span = ("the 20 points below its measured %.1f%% (a rate cannot exceed 100%%)" % (100 * focus["pass_rate"])
                if focus["pass_rate"] + 0.10 > 1.0 else "+/-10 points of its measured %.1f%%" % (100 * focus["pass_rate"]))
        lines += ["## 3 · Sensitivity: %s over %s" % (focus["label"], span), "",
                  "| success rate | layer 2 | per successful task | monthly (before layer 3) |", "|---|---|---|---|"]
        for s_ in sens:
            mark = "  <- measured" if abs(s_["pass_rate"] - round(focus["pass_rate"], 3)) < 1e-6 else ""
            lines.append("| %.1f%%%s | %s | %s | %s |" % (100 * s_["pass_rate"], mark, fmt(s_["layer2"]), fmt(s_["per_task"]),
                                                          format(round(s_["monthly"]), ",")))
        lo, hi = sens[0], sens[-1]
        lines += ["", "Every 5 points of success are worth US$%s a month against a token bill of US$%s a month. The "
                  "conclusion that layer 2 dominates survives the whole range; the token price only decides anything "
                  "between two models whose failure rates are within a point of each other."
                  % (format(round((lo["monthly"] - hi["monthly"]) / (len(sens) - 1)), ","), format(round(focus["layer1"] * VOLUME), ",")), ""]

    # ---- 4 · break-even ------------------------------------------------------------------
    lines += ["## 4 · Break-even success rate", ""]
    pairs = []
    if len(live) >= 2:
        best = max(live, key=lambda r: (r["pass_rate"], -r["layer1"]))
        mids = [r for r in live if r is not best and 1.0 <= r["price_in"] < best["price_in"]]
        for exp in [best] + mids[:1]:
            for cheap in sorted(live, key=lambda r: r["layer1"]):
                if cheap is exp or cheap["layer1"] >= exp["layer1"] or cheap["tools"] != "v2":
                    continue
                be = break_even_success_rate(cheap["layer1"], exp["per_task"], F)
                pairs.append({"cheap": cheap["label"], "expensive": exp["label"], "E": exp["per_task"], "C": cheap["layer1"],
                              "failures_affordable": 1 - be, "break_even_success": be,
                              "cheap_measured_success": cheap["pass_rate"], "clears": cheap["pass_rate"] >= be})
        lines += ["Measured pairs (v2 tools, %d trials each). E is the expensive model's tokens plus its own measured "
                  "failures; C is the cheap model's tokens only; `break_even_success_rate(C, E, F)`." % best["trials"], ""]
    elif final:
        cheap = dict(final)
        for tier, P_assumed in (("mid", 0.92), ("frontier", 0.95)):
            l1 = variable_cost(tier, fresh_in=final["tokens_in"], out=final["tokens_out"])
            E = cost_per_successful_task(l1, P_assumed, F)
            be = break_even_success_rate(cheap["layer1"], E, F)
            pairs.append({"cheap": cheap["label"], "expensive": "%s @%s, %.0f%% assumed" % (cheap["label"], tier, 100 * P_assumed),
                          "E": E, "C": cheap["layer1"], "failures_affordable": 1 - be, "break_even_success": be,
                          "cheap_measured_success": cheap["pass_rate"], "clears": cheap["pass_rate"] >= be})
        lines += ["No live battery in results/ yet: the shipped agent's token shape priced at the section-7 tiers with "
                  "ASSUMED expensive-side success rates.", ""]
    lines += ["| cheap | expensive | E = expensive per successful task | C = cheap tokens only | failures the cheap model can afford | break-even success | cheap measured | clears? |",
              "|---|---|---|---|---|---|---|---|"]
    for b in pairs:
        lines.append("| %s | %s | %s | %s | %.1f%% | **%.1f%%** | %.1f%% | %s |" % (
            b["cheap"], b["expensive"], fmt(b["E"]), fmt(b["C"]), 100 * b["failures_affordable"],
            100 * b["break_even_success"], 100 * b["cheap_measured_success"], "yes" if b["clears"] else "no"))
    lines.append("")

    # ---- 5 · the four levers -----------------------------------------------------------------
    lines += ["## 5 · The four levers, measured before and after", ""]
    v1, v2 = rows.get("scripted_careful_v1_parallel"), rows.get("scripted_careful_v2_parallel")
    L1, L2 = rows.get("live_openai_gpt-4o-mini_v1_parallel"), rows.get("live_openai_gpt-4o-mini_v2_parallel")
    seq, par = rows.get("scripted_sequential_v2_sequential"), rows.get("scripted_careful_v2_parallel")
    S1, S2 = (S.get("scripted_careful_v1_parallel") or {}).get("summary"), (S.get("scripted_careful_v2_parallel") or {}).get("summary")
    lines += ["| lever | what it attacks | where built | before | after | what moved |", "|---|---|---|---|---|---|"]
    if S1 and S2:
        lines.append("| 1 · tool block size | base, linear in turns | D2(a)/(b): the tool set and its descriptors | v1: 7 tools, %s tokens | v2: 6 tools, %s tokens | v2 is LARGER: six fields with size bounds and failure semantics cost %s tokens per turn, paid for by lever 4 |" % (
            format(S1["tool_block_tokens"], ","), format(S2["tool_block_tokens"], ","), format(S2["tool_block_tokens"] - S1["tool_block_tokens"], ",")))
    if seq and par:
        lines.append("| 2 · turn count T | the quadratic term | D2(c): parallel calls | sequential: median %s, max %s, %s tokens in/run | parallel: median %s, max %s, %s tokens in/run | %.0f%% fewer input tokens, same pass rate (%d/%d both) |" % (
            seq["turns_median"], seq["turns_max"], format(seq["tokens_in"], ","), par["turns_median"], par["turns_max"],
            format(par["tokens_in"], ","), 100 * (1 - par["tokens_in"] / seq["tokens_in"]), round(par["trials"] * par["pass_rate"]), par["trials"]))
    if S1 and S2:
        g1 = S1["obs_tokens_by_tool"].get("get_claim", {}).get("mean")
        g2 = S2["obs_tokens_by_tool"].get("get_claim", {}).get("mean")
        lines.append("| 3 · observation size D | compounds: re-sent every later turn | D2(b): what get_claim returns | v1 get_claim %s tokens/call (raw row) | v2 get_claim %s tokens/call (+ duplicate_of, near_misses, narrative_flags) | bigger by design: facts computed in code replace a tool call and a model judgement |" % (g1, g2))
    if L1 and L2:
        lines.append("| 4 · success rate | layer 2, the biggest layer | D4 + the v2 tool layer, measured live on gpt-4o-mini | v1: %.1f%% -> US$%s per successful task | v2: %.1f%% -> US$%s | the v2 token premium (US$%s/run) buys back US$%s/task of failures |" % (
            100 * L1["pass_rate"], fmt(L1["per_task"], 3), 100 * L2["pass_rate"], fmt(L2["per_task"], 3),
            fmt(L2["layer1"] - L1["layer1"], 5), fmt(L1["layer2"] - L2["layer2"], 3)))
    elif v1 and v2:
        lines.append("| 4 · success rate | layer 2 | D4 + the v2 tool layer | v1: %.1f%% | v2: %.1f%% | scripted only so far |" % (100 * v1["pass_rate"], 100 * v2["pass_rate"]))
    lines += ["", "Which dominated: lever 4. Lever 2 is the largest token saving and moved nothing in correctness, which is "
              "what D2(c) asks to show; levers 1 and 3 went the other way on purpose. On this problem every failure is a "
              "US$%.2f escalation, so the cost per successful task ranks by pass rate and nothing else." % F, ""]

    # ---- 6 · the three caps ------------------------------------------------------------------
    per_run_cap = config.MAX_TOKENS_PER_RUN / 1e6 * (final["price_in"] if final else config.PRICE_IN)
    lines += ["## 6 · The three caps that ship", "",
              "| cap | value | where it comes from |", "|---|---|---|",
              "| step cap | %d turns | worst legitimate sequential run is 10 turns (CLM-9007); the parallel form never passes 4 |" % config.MAX_TURNS,
              "| budget ceiling | %s tokens per run (about US$%.4f at the cheap tier) | about 2x the worst legitimate run (~27k); the D7 runaway peaked at 39k, so the step cap fires first and the ceiling is the backstop |" % (format(config.MAX_TOKENS_PER_RUN, ","), per_run_cap),
              "| monthly token alarm per user | US$%s | 1.5x the expected monthly token bill of the shipped configuration at volume; an alarm, not a hard stop |" % (
                  format(round(1.5 * (final["layer1"] if final else 0) * VOLUME), ",")),
              ""]
    out = os.path.join(config.RESULTS_DIR, "cost_model.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    with open(os.path.join(config.RESULTS_DIR, "cost_model.json"), "w", encoding="utf-8") as fh:
        json.dump({"failure_cost": F, "volume": VOLUME, "fixed_monthly": a.fixed, "rows": rows,
                   "sensitivity": sensitivity(focus["layer1"], F, focus["pass_rate"]) if focus else None,
                   "break_even": pairs}, fh, indent=1)
    print("\n".join(lines))
    print("\nwrote %s" % out)


if __name__ == "__main__":
    main()
