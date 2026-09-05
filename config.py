"""
PE6201 · A2 · Problem A — CONFIGURATION
====================================================================
THE VENDOR-NEUTRAL BLOCK THE BRIEF ASKS FOR (D5).

    BACKEND = "scripted"   free, deterministic, no key, no network.
                           MUST be the default in what is submitted: a marker
                           clones the repository and runs `python run_eval.py`.
    BACKEND = "live"       a real model through OpenRouter. Costs money.
                           Only D5(b) and the D2(b) v1 pass need it.

Everything can be overridden from the environment so a battery can be driven
from a shell without editing code:  A2_BACKEND, A2_MODEL, A2_BASE_URL,
A2_PRICE_TIER, A2_DATA, OPENROUTER_API_KEY.
====================================================================
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ── the three strings ─────────────────────────────────────────────────────────
BACKEND = os.environ.get("A2_BACKEND", "scripted")       # "scripted" | "live"
MODEL = os.environ.get("A2_MODEL", "openai/gpt-4o-mini")  # any OpenRouter model id
BASE_URL = os.environ.get("A2_BASE_URL", "https://openrouter.ai/api/v1")


def _read_key():
    """Env var first; then the untracked key file in the repo root (gitignored).
    The key is never printed and never committed."""
    k = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if k:
        return k
    f = os.path.join(HERE, "OpenRouter_api.txt")
    if os.path.exists(f):
        with open(f, encoding="utf-8") as fh:
            lines = [l.strip() for l in fh.read().splitlines() if l.strip()]
        return lines[-1] if lines else ""
    return ""


API_KEY = _read_key()
PROBLEM = "A"                     # this repository does Problem A only
MAX_OUTPUT_TOKENS = 700           # per model reply; a step is short by design
TIMEOUT_S = 60
RETRIES = 4                       # live path: retries on 429/5xx/timeouts, with backoff
# Reasoning cap for reasoning models, passed through as OpenRouter's `reasoning` object.
# None = do not send. Examples: {"max_tokens": 1024} · {"effort": "low"} · {"enabled": False}
REASONING = None

# ── guardrail limits (D3a). Set from evidence, revisit after D7. ──────────────
# Measured on the scripted backend, 15 shipped cases: parallel median 3 turns, max 4;
# sequential worst legitimate run 8. A cap of 10 sits above the worst legitimate run.
MAX_TURNS = 10                    # step cap: tool-calling turns per run
MAX_TOKENS_PER_RUN = 40000        # budget ceiling: tokens (in + out) per run;
                                  # the worst legitimate sequential run is ~18k
DEDUPE = True                     # identical action twice in one run is a bug: stop loudly
AUTONOMY = "confirm"              # "suggest" | "confirm" | "act"
#   suggest  the agent proposes; the letter is not issued; a human does it
#   confirm  everything except the irreversible step, which waits for a yes
#   act      the agent issues the letter itself
# THE GATE SITS IN FRONT OF issue_decision_letter, not in front of the agent.

# ── where the data is ─────────────────────────────────────────────────────────
DATA_DIR = os.environ.get("A2_DATA", "") or os.path.join(HERE, "data")
RESULTS_DIR = os.path.join(HERE, "results")
DECISIONS_LOG = os.path.join(RESULTS_DIR, "decisions.jsonl")   # the gated action's log


def data_root():
    """The folder holding data_A/ and expected_outcomes_A.json. Fails LOUDLY.
    A silent wrong path here is the failure the data guide warns about: every tool
    returns nothing and the run still looks fine."""
    ok = (os.path.isdir(os.path.join(DATA_DIR, "data_A"))
          and os.path.isfile(os.path.join(DATA_DIR, "expected_outcomes_A.json")))
    if not ok:
        raise SystemExit(
            "\n  Could not find the reference data.\n"
            "  Expected data_A/ and expected_outcomes_A.json inside:\n"
            "    %s\n"
            "  Fix: put them there, or export A2_DATA=/path/to/folder\n" % DATA_DIR)
    return DATA_DIR


# ── prices, US$ per MILLION tokens ────────────────────────────────────────────
# Section 7 tiers. Per-model list prices go in MODEL_PRICES; re-check them on
# openrouter.ai/models before quoting a number in the report.
PRICES = {"cheap": (0.10, 0.40), "mid": (1.00, 5.00), "frontier": (5.00, 25.00)}
MODEL_PRICES = {
    "openai/gpt-4o-mini": (0.15, 0.60),
    # "google/gemini-2.5-flash": (..., ...),   fill in from the vendor page, with the date
}
PRICE_TIER = os.environ.get("A2_PRICE_TIER", "cheap")


def price_for(model=None):
    """(price_in, price_out) for a model: its list price if known, else the tier."""
    m = model or MODEL
    if BACKEND == "live" and m in MODEL_PRICES:
        return MODEL_PRICES[m]
    return PRICES[PRICE_TIER]


PRICE_IN, PRICE_OUT = price_for()

# ── cost model inputs (Appendix A, Problem A) ─────────────────────────────────
VOLUME_PER_MONTH = 8000
FAILURE_COST_USD = 38 * 12 / 60        # claims assessor, 12 min per escalated claim = 7.60


def summary():
    """One line at the top of every run, so you always know which backend
    produced the numbers you are looking at."""
    where = "FREE, deterministic" if BACKEND == "scripted" else "LIVE - this costs money"
    model = "(no model)" if BACKEND == "scripted" else MODEL
    return ("BACKEND=%s  %s  |  model=%s  |  cap=%d turns / %d tokens  |  dedupe=%s  |  "
            "autonomy=%s  |  prices %.2f/%.2f US$/M"
            % (BACKEND, where, model, MAX_TURNS, MAX_TOKENS_PER_RUN, DEDUPE, AUTONOMY,
               PRICE_IN, PRICE_OUT))
