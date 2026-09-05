"""
PE6201 · A2 · Problem A — THE AGENT LOOP  (D1)
====================================================================
    thought -> action(s) -> observation(s) -> repeat -> conclude

One ReAct agent, hand-rolled. Read run_case() once and you have read the agent.

Per model call:  ASK the backend for a move -> METER tokens -> BUDGET check ->
either CONCLUDE (a `final`, validated) or ACT (one or more calls in one turn;
each call passes the de-duplication guard, the gated action passes validation
and the autonomy gate) -> APPEND every observation -> repeat.

TURNS are tool-calling turns, the convention Appendix A uses (CLM-8842 is
"turns": 4 with eight tool calls; CLM-8925 is "turns": 2). A concluding `final`
is metered and counted in `model_calls` but is not a turn. The step cap bounds
turns; an iteration guard (MAX_TURNS + 2 model calls) bounds a model that never
calls a tool at all.

Guardrails are code (guardrails.py) and every stop is LOUD: a halted run has
decision None and names the guard in `stopped_by`.

INSTRUMENTATION IS NOT OPTIONAL: every run records turns, model calls, tokens
in/out, cost, every tool call with the size of what it returned, every guardrail
event, and the transcript. D6 and D7 both read these.
====================================================================
"""
import json
import time

import config
import prompt
import tools
from backends import make_backend
from guardrails import Guardrails, GuardrailStop


def _short(value, n=110):
    s = json.dumps(value, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n - 1] + "…"


def run_case(case_id, policy="careful", version="v2", mode=None, approve=None, verbose=False,
             write=True, max_turns=None, max_tokens=None, dedupe=None, autonomy=None,
             script=None, backend=None):
    """Run ONE case from a clean state and return the decision record.

    ISOLATION (D4): everything this function needs is created inside it. No case
    depends on a previous one having run.

    policy    scripted decision-maker: careful | sequential | repeats | credulous (inert live)
    version   tool set + descriptors: "v2" (shipped) | "v1" (D2b baseline)
    mode      "parallel" | "sequential" - what the prompt allows per turn; defaults from policy
    approve   callable(action, payload) -> bool consulted when autonomy == "confirm".
              The harness auto-approves; `run_eval.py CASE --ask` puts a human there.
    write     False keeps the gated action from appending to results/decisions.jsonl
    script    an explicit list of moves to replay instead of the policy (guardrail cases, D7)
    """
    started = time.time()
    backend = backend or config.BACKEND
    mode = mode or ("sequential" if policy in ("sequential", "repeats") else "parallel")
    max_turns = max_turns or config.MAX_TURNS
    max_tokens = max_tokens or config.MAX_TOKENS_PER_RUN
    dedupe = config.DEDUPE if dedupe is None else dedupe
    autonomy = autonomy or config.AUTONOMY
    approve = approve or (lambda action, payload: True)
    price_in, price_out = config.price_for()

    system_prompt = prompt.build_system_prompt(version, mode)
    guards = Guardrails(max_turns, max_tokens, autonomy, dedupe)
    be = make_backend(case_id, system_prompt, policy, version, mode, script, backend)
    model_label = config.MODEL if be.name == "live" else "scripted:%s" % policy

    # The task line: the ONE thing the model is told about this run. Everything else it
    # must fetch. (Its absence sent every live model to the descriptor's example id.)
    transcript = [{"role": "user", "content": "Task: decide claim %s and record the first response. "
                                              "Start with get_claim(\"%s\")." % (case_id, case_id)}]
    evidence, tool_log = [], []
    turns = model_calls = tokens_in = tokens_out = 0
    stopped_by, record = None, None
    ctx = {"evidence": evidence, "autonomy": autonomy, "write": write, "backend": be.name,
           "model": model_label, "decided": False, "record": None, "writes": 0}
    ctx.update(tools.TOOL_RULES[version])

    def usd():
        return tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out

    def meter_ctx():
        ctx.update(turn=turns, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=round(usd(), 6))

    try:
        while True:
            # ---- ASK + METER ----------------------------------------------------
            model_calls += 1
            if model_calls > max_turns + 2:
                guards.fired.append({"guardrail": "step_cap", "detail": "%d model calls without a decision" % (model_calls - 1)})
                raise GuardrailStop("step_cap", "%d model calls without a decision" % (model_calls - 1))
            move = be.next_move(transcript)
            ti, to = be.usage()
            tokens_in, tokens_out = tokens_in + ti, tokens_out + to
            guards.check_budget(tokens_in + tokens_out)
            if verbose:
                label = "conclude" if "final" in move else "turn %d" % (turns + 1)
                print("  %-9s · %s" % (label, str(move.get("thought", ""))[:100]))

            # ---- a move the loop cannot act on ------------------------------------
            if "final" not in move and not move.get("calls"):
                obs = {"error": move.get("invalid", "no calls and no final in the reply") +
                       ". Reply with {\"thought\", \"calls\": [...]} or {\"thought\", \"final\": {...}}."}
                guards.fired.append({"guardrail": "reply_refused", "detail": obs["error"][:80]})
                transcript.append({"role": "assistant", "content": json.dumps(move, ensure_ascii=False)})
                transcript.append({"role": "user", "content": json.dumps([{"tool": None, "args": {}, "observation": obs}])})
                if verbose:
                    print("       refused -> %s" % _short(obs))
                continue

            # ---- CONCLUDE: escalate / request_document / nothing ------------------
            if "final" in move:
                fin = dict(move.get("final") or {})
                fin.setdefault("claim_id", case_id)
                decision = fin.get("decision")
                if fin["claim_id"] != case_id and decision is not None:
                    obs = {"error": "this run decides %s, not %s" % (case_id, fin["claim_id"])}
                    guards.fired.append({"guardrail": "final_refused", "detail": obs["error"]})
                    transcript.append({"role": "assistant", "content": json.dumps(move, ensure_ascii=False)})
                    transcript.append({"role": "user", "content": json.dumps([{"tool": None, "args": {}, "observation": obs}])})
                    if verbose:
                        print("       refused -> %s" % _short(obs))
                    continue
                if decision is None:
                    record = {"case_id": case_id, "decision": None, "reason": fin.get("reason", ""),
                              "gate": "no decision - nothing recorded"}
                    transcript.append({"role": "assistant", "content": json.dumps(move, ensure_ascii=False)})
                    break
                problem = ("approve_in_principle must go through issue_decision_letter; nothing was recorded"
                           if decision == "approve_in_principle" else tools.validate_final(fin))
                if problem:
                    obs = {"error": problem}
                    guards.fired.append({"guardrail": "final_refused", "detail": problem[:80]})
                    transcript.append({"role": "assistant", "content": json.dumps(move, ensure_ascii=False)})
                    transcript.append({"role": "user", "content": json.dumps([{"tool": None, "args": {}, "observation": obs}])})
                    if verbose:
                        print("       refused -> %s" % _short(obs))
                    continue
                meter_ctx()
                ctx["gate"] = "issue_decision_letter not called - %s path taken before the gate" % decision
                record = tools.build_record(fin, ctx)
                if write:
                    tools.append_log(record)
                transcript.append({"role": "assistant", "content": json.dumps(move, ensure_ascii=False)})
                break

            # ---- ACT: one turn may carry SEVERAL calls -----------------------------
            guards.check_turns(turns + 1)          # the cap is on turns, not on this one
            turns += 1
            observations, concluded = [], False
            for name, args in move["calls"]:
                args = dict(args or {})
                guards.check_duplicate(name, args)
                if name == tools.GATED_ACTION:
                    # validation BEFORE the gate: a human is never asked to approve an invalid record
                    problem = tools.validate_decision(args, ctx["narrative_guard"], ctx["compute_totals"])
                    if not problem and args.get("claim_id") != case_id:
                        problem = "this run decides %s, not %s" % (case_id, args.get("claim_id"))
                    if problem:
                        result = {"error": problem}
                    elif ctx["decided"]:
                        result = {"error": "BLOCKED: a decision already exists for this claim in this run"}
                    else:
                        meter_ctx()
                        ok, gate_text = guards.gate(name, dict(args, _turn=turns), approve)
                        ctx["gate"] = gate_text
                        if not ok and autonomy == "suggest":
                            record = tools.build_record(args, ctx)
                            ctx["record"], ctx["decided"] = record, True
                            result = {"recorded": False, "gate": gate_text}
                            concluded = True
                        elif not ok:
                            raise GuardrailStop("gate_held", "%s: %s" % (name, gate_text))
                        else:
                            try:
                                result = tools.issue_decision_letter(_ctx=ctx, **args)
                            except TypeError as e:
                                result = {"error": "bad arguments: %s" % e}
                            if result.get("recorded"):
                                record, concluded = ctx["record"], True
                else:
                    try:
                        result = tools.call(version, name, args)
                    except (KeyError, TypeError) as e:          # a tool that fails is still an observation
                        result = {"error": str(e)}
                evidence.append(name)
                obs_text = json.dumps(result, ensure_ascii=False, default=str)
                tool_log.append({"turn": turns, "tool": name, "args": args, "obs_tokens": max(1, len(obs_text) // 4)})
                observations.append({"tool": name, "args": args, "observation": result})
                if verbose:
                    print("       %-22s -> %s" % (name, _short(result)))
            transcript.append({"role": "assistant", "content": json.dumps(move, ensure_ascii=False)})
            transcript.append({"role": "user", "content": json.dumps(observations, ensure_ascii=False, default=str)})
            if verbose:
                print("       [%s in · %s out · running US$%.5f]" % (ti, to, usd()))
            if concluded:
                break

    except GuardrailStop as stop:
        stopped_by = stop.reason
        record = {"case_id": case_id, "decision": None, "gate": None,
                  "reason": "halted by the %s guardrail - %s" % (stop.reason, stop.detail)}
        if verbose:
            print("  [STOP] %s: %s" % (stop.reason, stop.detail))

    record = dict(record or {"case_id": case_id, "decision": None, "reason": "no record"})
    record.update({
        "case_id": case_id, "evidence": list(evidence), "turns": turns, "model_calls": model_calls,
        "tokens_in": tokens_in, "tokens_out": tokens_out, "tokens_measured": be.measured,
        "cost_usd": round(usd(), 6), "seconds": round(time.time() - started, 3),
        "guardrails_fired": guards.fired, "stopped_by": stopped_by, "writes": ctx["writes"],
        "backend": be.name, "model": model_label, "policy": policy if be.name == "scripted" else None,
        "tool_version": version, "mode": mode, "autonomy": autonomy,
        "system_prompt_tokens": prompt.est_tokens(system_prompt), "tool_log": tool_log,
        "transcript": transcript, "raw_replies": getattr(be, "raw", None),
    })
    return record
