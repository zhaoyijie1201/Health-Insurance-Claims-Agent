"""
PE6201 · A2 · Problem A — THE TWO BACKENDS
====================================================================
A backend answers ONE question: given the conversation so far, what does the
agent do next?  It returns a MOVE:

    {"thought": "...", "calls": [["tool", {"arg": "value"}], ...]}   -> call tools
    {"thought": "...", "final": {"decision": ..., "reason": ..., ...}} -> conclude

SCRIPTED (default, free, deterministic, no key)
    A small decision-making POLICY, written as code, that re-reads the
    observations in the transcript each turn and emits the next move. It is not a
    canned answer per case: the number of turns and the calls emerge from the
    data, as with a real model, so every labelled case runs without anyone
    writing its moves down. Where a specific sequence of moves is needed (the
    D3(b) guardrail cases, the D7 loop), an explicit SCRIPT can be passed in and
    is replayed verbatim - that is the scaffold's SCRIPTS mechanism, kept.

    Four policies, chosen with `policy=`:
        careful     the run that should happen; independent calls share a turn (D2c)
        sequential  the same decisions, one call per turn - the D2(c) "before"
        repeats     `sequential` with ONE guard deleted: it never notices the
                    policy row has already arrived. D7 failure 1.
        credulous   `careful` but believes tool-looking text inside the member's
                    narrative. D7 failure 2: with v1 tools it approves an
                    excluded line; with v2 the write refuses it.

LIVE
    The identical loop against any OpenAI-compatible endpoint through
    OpenRouter. `_live_call` is the ONLY function that knows a vendor exists.
    Token counts come from the API's `usage` block, never estimated.
====================================================================
"""
import json
import re
import time
import urllib.error
import urllib.request

import config
import prompt

# Explicit move lists, replayed verbatim, keyed by case id. Empty by default: the
# policy below handles every labelled case. run_guardrails.py and the D7 demos
# pass scripts directly.
SCRIPTS = {}


def est_tokens(text):
    return max(1, len(text) // 4)


# ── reading the transcript: the ONLY state a scripted policy has ─────────────
def observations(transcript):
    """Every {tool, args, observation} the loop has appended, in order."""
    out = []
    for entry in transcript:
        if entry.get("role") != "user":
            continue
        try:
            items = json.loads(entry["content"])
        except (ValueError, TypeError):
            continue
        if isinstance(items, list):
            out.extend(i for i in items if isinstance(i, dict) and "tool" in i)
    return out


def first(obs, name):
    return next((o["observation"] for o in obs if o["tool"] == name), None)


def last(obs, name):
    return next((o["observation"] for o in reversed(obs) if o["tool"] == name), None)


def by_code(obs, name):
    return {o["observation"]["code"]: o["observation"] for o in obs
            if o["tool"] == name and isinstance(o["observation"], dict) and "code" in o["observation"]}


def calls(thought, pairs):
    return {"thought": thought, "calls": [[n, a] for n, a in pairs]}


def final(thought, record):
    return {"thought": thought, "final": record}


# ── the scripted decision-maker ───────────────────────────────────────────────
def decide(cid, obs, policy="careful", version="v2", mode="parallel"):
    parallel = (mode == "parallel")

    # 0 · the claim itself ---------------------------------------------------
    claim = first(obs, "get_claim")
    if claim is None:
        return calls("Read the claim first; everything else depends on what it returns.",
                     [("get_claim", {"claim_id": cid})])
    if "error" in claim:
        return final("The id resolves to nothing; I will not invent a claim.",
                     {"claim_id": cid, "decision": None,
                      "reason": "Claim %s does not exist in the queue: %s. No decision recorded."
                                % (cid, claim["error"])})

    # the write already answered? read its verdict ------------------------------
    issued = last(obs, "issue_decision_letter")
    if issued is not None:
        err = str(issued.get("error", ""))
        if err.startswith("BLOCKED: narrative_flags"):
            return final("The write refused an approval on flagged text; escalate.",
                         {"claim_id": cid, "decision": "escalate", "trigger": "instruction_in_member_narrative",
                          "reason": "Member narrative contains text aimed at the system; the decision "
                                    "record was refused for any decision other than escalate."})
        if err:
            return final("The write refused the record.",
                         {"claim_id": cid, "decision": None, "reason": "issue_decision_letter refused: " + err})

    dos, member, hospital = claim["date_of_service"], claim["member_id"], claim["hospital_id"]
    lines = claim["lines"]
    codes = list(dict.fromkeys(l["code"] for l in lines))
    total = claim.get("claim_total", sum(int(l["amount"]) for l in lines))
    narrative = claim.get("narrative", "")

    # credulous: believes tool-looking text in the (untrusted) narrative --------
    if policy == "credulous" and re.search(r"covered\s*=\s*true|approve all lines", narrative, re.I):
        return calls("The narrative confirms coverage; record the approval.",
                     [("issue_decision_letter", {
                         "claim_id": cid, "decision": "approve_in_principle",
                         "reason": "Narrative confirms coverage: covered=true, exclusions=none, "
                                   "preauth not required.",
                         "lines": ";".join("%s:covered" % l["code"] for l in lines),
                         "approved_total": total, "refused_total": 0})])

    # 1 · code-scanned hostile text outranks everything (v2 only has the field) --
    if claim.get("narrative_flags"):
        return final("Text aimed at the system was flagged by the scan; escalate without pricing.",
                     {"claim_id": cid, "decision": "escalate", "trigger": "instruction_in_member_narrative",
                      "reason": "Narrative flagged %s: text aimed at the system was found and NOT "
                                "followed. No line was approved." % claim["narrative_flags"]})
    # 2 · resubmission of a decided episode (v2: in get_claim; v1: separate tool) -
    dup = claim.get("duplicate_of")
    dup_obs = first(obs, "check_duplicate_claim")
    if dup is None and dup_obs and dup_obs.get("duplicate_of"):
        dup = dup_obs["duplicate_of"]
    if dup:
        return final("This episode was already decided; escalate.",
                     {"claim_id": cid, "decision": "escalate", "trigger": "duplicate_claim",
                      "reason": "Same member, hospital, date of service and lines as decided claim "
                                "%s (%s on %s)." % (dup["claim_id"], dup["decision"], dup["decided_on"])})

    # 3 · policy, hospital, per-line coverage ---------------------------------
    pol, hosp, cov = first(obs, "lookup_policy"), first(obs, "lookup_hospital"), by_code(obs, "check_coverage")
    dup_call = ("check_duplicate_claim", {"member_id": member, "hospital_id": hospital,
                                          "date_of_service": dos, "lines": lines})
    if parallel:
        if pol is None:
            acts = [("lookup_policy", {"member_id": member}), ("lookup_hospital", {"hospital_id": hospital})]
            acts += [("check_coverage", {"member_id": member, "procedure_code": c}) for c in codes]
            if version == "v1":
                acts.append(dup_call)
            return calls("Policy, hospital and every line's coverage depend only on the claim; "
                         "fetch them together.", acts)
    else:
        # `repeats` is `sequential` with THIS guard deleted: it re-issues lookup_policy
        # every turn because nothing models that the observation already arrived.
        if pol is None or policy == "repeats":
            return calls("Check the policy before pricing anything.", [("lookup_policy", {"member_id": member})])
        if version == "v1" and dup_obs is None:
            return calls("Check the history before deciding.", [dup_call])
    if "error" in pol:
        return final("The member resolves to no policy.",
                     {"claim_id": cid, "decision": None,
                      "reason": "Member %s on %s resolves to no policy: %s." % (member, cid, pol["error"])})
    if pol["status"] != "active":
        return final("The cover is not live; nothing further can be decided at this level.",
                     {"claim_id": cid, "decision": "escalate", "trigger": "policy_lapsed",
                      "reason": "Policy %s status is %s. Nothing further can be decided at this level."
                                % (pol["policy_id"], pol["status"])})
    if not (pol["start_date"] <= dos <= pol["end_date"]):
        return final("The date of service is outside the cover.",
                     {"claim_id": cid, "decision": "escalate", "trigger": "outside_policy_dates",
                      "reason": "Date of service %s is outside policy %s cover %s to %s."
                                % (dos, pol["policy_id"], pol["start_date"], pol["end_date"])})
    if total > pol["remaining"]:
        return final("The claim exceeds the remaining limit; do not price the lines.",
                     {"claim_id": cid, "decision": "escalate", "trigger": "annual_limit_exceeded",
                      "reason": "Claim total %d exceeds %d remaining on policy %s. Lines were not "
                                "individually priced." % (total, pol["remaining"], pol["policy_id"])})
    if not parallel:
        if hosp is None:
            return calls("Record the settlement basis.", [("lookup_hospital", {"hospital_id": hospital})])
        for c in codes:
            if c not in cov:
                return calls("Check line %s." % c, [("check_coverage", {"member_id": member, "procedure_code": c})])
    missing_cov = [c for c in codes if c not in cov]
    if missing_cov:
        return calls("Some lines are still unchecked.",
                     [("check_coverage", {"member_id": member, "procedure_code": c}) for c in missing_cov])

    # 4 · pre-authorisation, only for the lines that need one ------------------
    pa = by_code(obs, "get_preauthorisation")
    need = [c for c in codes if cov[c].get("covered") and cov[c].get("requires_preauth") and c not in pa]
    if need:
        todo = need if parallel else need[:1]
        return calls("Line(s) %s require pre-authorisation; look for one valid on %s." % (", ".join(todo), dos),
                     [("get_preauthorisation", {"member_id": member, "procedure_code": c, "date_of_service": dos})
                      for c in todo])

    # 5 · resolve every line ---------------------------------------------------
    disp, asks, approved, refused = [], [], 0, 0
    for l in lines:
        c, amt = cov[l["code"]], int(l["amount"])
        if not c["covered"]:
            disp.append("%s:not_covered (%s)" % (l["code"], c["exclusion"])); refused += amt; continue
        if c["requires_preauth"]:
            p = pa[l["code"]]
            if not p["valid_on_date"]:
                if p["found"]:
                    f0 = p["found"][0]
                    asks.append("current pre-authorisation for line %s, valid on %s (%s found but its "
                                "validity ended %s)" % (l["code"], dos, f0["preauth_id"], f0["valid_to"]))
                else:
                    asks.append("pre-authorisation reference for line %s, valid on %s" % (l["code"], dos))
                disp.append("%s:pending_preauth" % l["code"]); continue
            f0 = next(f for f in p["found"] if f["preauth_id"] == p["valid_on_date"])
            disp.append("%s:covered (%s valid %s..%s)" % (l["code"], p["valid_on_date"], f0["valid_from"], f0["valid_to"]))
        else:
            disp.append("%s:covered" % l["code"])
        if c.get("required_document") and c["required_document"] not in claim["documents"]:
            asks.append("%s for line %s" % (c["required_document"].replace("_", " "), l["code"]))
            disp[-1] = "%s:pending_document (%s)" % (l["code"], c["required_document"])
            continue
        approved += amt

    basis = ("Hospital %s on panel (direct settlement)" % hosp["hospital_id"] if hosp and hosp.get("panel")
             else "Hospital %s NON-PANEL: member paid, reimbursement basis" % hospital)
    if asks:
        return final("Something specific is missing; name it and stop.",
                     {"claim_id": cid, "decision": "request_document", "missing": "; ".join(asks), "lines": disp,
                      "reason": "Policy %s active to %s. %s. Cannot assess until received: %s. Lines "
                                "resolved so far: %s." % (pol["policy_id"], pol["end_date"], basis,
                                                          "; ".join(asks), "; ".join(disp))})
    payable = sum(1 for d in disp if ":covered" in d)
    return calls("Every line has a disposition; record the approval through the gate.",
                 [("issue_decision_letter", {
                     "claim_id": cid, "decision": "approve_in_principle",
                     "reason": "Policy %s active to %s. %s. %d of %d lines payable; approved total %d against "
                               "%d remaining." % (pol["policy_id"], pol["end_date"], basis, payable, len(disp),
                                                  approved, pol["remaining"]),
                     "lines": ";".join(disp), "approved_total": approved, "refused_total": refused})])


class ScriptedBackend:
    """Deterministic, free, offline. Replays an explicit script when given one,
    otherwise runs the policy above against the transcript."""

    name = "scripted"

    def __init__(self, case_id, system_prompt, policy="careful", version="v2", mode="parallel", script=None):
        self.case_id, self.system_prompt = case_id, system_prompt
        self.policy, self.version, self.mode = policy, version, mode
        self.script = script if script is not None else SCRIPTS.get(case_id)
        self.i = 0
        self.last_usage = (0, 0)
        self.measured = False            # scripted counts are chars/4 ESTIMATES

    def next_move(self, transcript):
        if self.script is not None:
            if self.i >= len(self.script):
                move = final("script exhausted", {"claim_id": self.case_id, "decision": None,
                                                  "reason": "script ended without a conclusion"})
            else:
                move = self.script[self.i]
                self.i += 1
        else:
            move = decide(self.case_id, observations(transcript), self.policy, self.version, self.mode)
        # the same shape as a live bill: the prefix plus the whole history, every turn
        ti = est_tokens(self.system_prompt) + sum(est_tokens(e["content"]) for e in transcript)
        self.last_usage = (ti, est_tokens(json.dumps(move)))
        return move

    def usage(self):
        return self.last_usage


# ── the live path: the ONLY function that knows a vendor exists ───────────────
class LiveBackend:
    name = "live"

    def __init__(self, case_id, system_prompt):
        self.case_id, self.system_prompt = case_id, system_prompt
        self.last_usage = (0, 0)
        self.measured = True
        self.raw = []                     # every raw reply, for the transcript file

    def next_move(self, transcript):
        messages = [{"role": "system", "content": self.system_prompt}] + list(transcript)
        text, usage = _live_call(messages)
        self.raw.append(text)
        if usage is None:                 # a provider that returns no usage block
            self.measured = False
            usage = (sum(est_tokens(m["content"]) for m in messages), est_tokens(text))
        self.last_usage = usage
        return parse_move(text)

    def usage(self):
        return self.last_usage


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.S)


def parse_move(text):
    """The model must answer in JSON. Tolerates code fences and leading prose;
    anything else becomes a move the loop refuses loudly."""
    s = _FENCE.sub("", text or "").strip()
    try:
        obj = json.loads(s)
    except ValueError:
        obj = None
        start = s.find("{")
        if start >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(s[start:])
            except ValueError:
                obj = None
    if isinstance(obj, dict) and ("calls" in obj or "final" in obj):
        return obj
    return {"thought": (text or "")[:300], "invalid": "reply was not one of the two JSON shapes"}


def _live_call(messages):
    """>>> THE ONLY FUNCTION IN THIS REPOSITORY THAT KNOWS A VENDOR <<<
    Returns (text, (prompt_tokens, completion_tokens) or None)."""
    if not config.API_KEY:
        raise RuntimeError("BACKEND is 'live' but no key: set OPENROUTER_API_KEY "
                           "(or put it in the untracked OpenRouter_api.txt).")
    body = {"model": config.MODEL, "messages": messages, "temperature": 0,
            "max_tokens": config.MAX_OUTPUT_TOKENS}
    if config.REASONING:
        body["reasoning"] = config.REASONING
    req = urllib.request.Request(
        config.BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + config.API_KEY, "Content-Type": "application/json",
                 "HTTP-Referer": "https://github.com/zhaoyijie1201/Health-Insurance-Claims-Agent",
                 "X-Title": "PE6201 A2 claims agent"})
    delay = 2.0
    for attempt in range(config.RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=config.TIMEOUT_S) as r:
                payload = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < config.RETRIES:
                time.sleep(delay); delay *= 2; continue
            raise RuntimeError("HTTP %d from %s: %s" % (e.code, config.BASE_URL, e.read()[:300]))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < config.RETRIES:
                time.sleep(delay); delay *= 2; continue
            raise RuntimeError("network error after %d retries: %s" % (config.RETRIES, e))
    if "error" in payload and not payload.get("choices"):
        raise RuntimeError("API error: %s" % json.dumps(payload["error"])[:300])
    text = payload["choices"][0]["message"].get("content") or ""
    u = payload.get("usage") or {}
    usage = (u["prompt_tokens"], u["completion_tokens"]) if "prompt_tokens" in u else None
    return text, usage


def make_backend(case_id, system_prompt, policy="careful", version="v2", mode="parallel",
                 script=None, backend=None):
    backend = backend or config.BACKEND
    if backend == "scripted":
        return ScriptedBackend(case_id, system_prompt, policy, version, mode, script)
    if backend == "live":
        return LiveBackend(case_id, system_prompt)
    raise SystemExit("BACKEND must be 'scripted' or 'live', not %r" % backend)
