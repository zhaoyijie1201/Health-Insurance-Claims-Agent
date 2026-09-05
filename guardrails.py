"""
PE6201 · A2 · Problem A — THE GUARDRAIL LAYER  (D3a)
====================================================================
Four things, and NONE of them involve a model. That is the point.

    1. STEP CAP                 stop after N tool-calling turns
    2. BUDGET CEILING           stop after N tokens
    3. ACTION DE-DUPLICATION    stop repeating an action already taken
    4. AUTONOMY GATE            hold the irreversible step for a human

A model cannot influence whether these fire, which is why D3(b)'s guardrail
cases run on the SCRIPTED backend (`python run_guardrails.py`). They test code.

MAKE THE STOP LOUD. A cap that silently returns an empty answer is worse than
the loop it prevented. Every stop records WHY, and a halted run has NO
decision - it never masquerades as an escalation.
====================================================================
"""
import json


class GuardrailStop(Exception):
    """Raised when the code layer halts a run. Carries the reason so the
    decision record can say what stopped it and at which turn."""

    def __init__(self, reason, detail=""):
        self.reason = reason
        self.detail = detail
        super().__init__("%s: %s" % (reason, detail) if detail else reason)


class Guardrails:
    """One instance per run. Never share one between cases - a shared instance
    leaks state, and D4 requires every case to start clean."""

    def __init__(self, max_turns, max_tokens, autonomy, dedupe=True):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.autonomy = autonomy
        self.dedupe = dedupe
        self.seen_actions = set()
        self.fired = []          # every guardrail event, for the record

    # ---- 1 · step cap ------------------------------------------------------
    def check_turns(self, turn):
        if turn > self.max_turns:
            self._fire("step_cap", "reached %d turns" % self.max_turns)
            raise GuardrailStop("step_cap", "%d turns without a decision" % self.max_turns)

    # ---- 2 · budget ceiling ------------------------------------------------
    def check_budget(self, tokens_so_far):
        if tokens_so_far > self.max_tokens:
            self._fire("budget_ceiling", "%d tokens" % tokens_so_far)
            raise GuardrailStop("budget_ceiling", "spent %d tokens, ceiling is %d"
                                % (tokens_so_far, self.max_tokens))

    # ---- 3 · action de-duplication ----------------------------------------
    def check_duplicate(self, tool, args):
        """A loop has no memory of its own actions unless you give it one. This is
        that memory. D7 failure 1 is exactly this guard deleted (`--no-dedupe`)."""
        if not self.dedupe:
            return
        signature = (tool, json.dumps(args, sort_keys=True, default=str))
        if signature in self.seen_actions:
            self._fire("duplicate_action", "%s repeated with identical arguments" % tool)
            raise GuardrailStop("duplicate_action",
                                "%s called again with identical arguments - the loop "
                                "is not progressing" % tool)
        self.seen_actions.add(signature)

    # ---- 4 · autonomy gate -------------------------------------------------
    def gate(self, action_name, payload, approve=None):
        """Called ONLY in front of the irreversible step. Returns (passed, text).

        `approve` is a callable(action_name, payload) -> bool supplied by the caller:
        the harness auto-approves so the scripted run is deterministic; the demo
        (`run_eval.py CASE --ask`) puts a human there.
        """
        if self.autonomy == "act":
            text = "act - no confirmation required"
            self._fire("gate_passed", "%s (autonomy=act)" % action_name)
            return True, text
        if self.autonomy == "suggest":
            text = "suggest - not executed, proposal returned to the human"
            self._fire("gate_held", "%s (autonomy=suggest)" % action_name)
            return False, text
        ok = bool(approve and approve(action_name, payload))
        text = ("operator approved at turn %s" % payload.get("_turn", "?") if ok
                else "operator declined - nothing recorded")
        self._fire("gate_%s" % ("passed" if ok else "held"), "%s (autonomy=confirm)" % action_name)
        return ok, text

    # ---- bookkeeping -------------------------------------------------------
    def _fire(self, kind, detail):
        self.fired.append({"guardrail": kind, "detail": detail})
