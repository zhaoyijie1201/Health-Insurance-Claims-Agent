# D7 · failure 1 · the loop-control failure

Scripted backend, 45 cases, 3 trials per negative case. Tokens are chars/4 estimates with the same shape as a live bill (prefix re-sent every turn).

| configuration | pass | turns median | turns max | halted | tokens in | cost US$ | tokens vs before |
|---|---|---|---|---|---|---|---|
| working agent, sequential (before) | 91/91 | 4 | 10 | 0 | 1,054,824 | 0.1143 | 1.00x |
| minus the memory, de-duplication ON (caught) | 21/91 | 3 | 3 | {'duplicate_action': 70} | 611,816 | 0.0648 | 0.58x |
| minus the memory, de-duplication OFF (runaway) | 21/91 | 12 | 12 | {'step_cap': 70} | 2,835,566 | 0.2947 | 2.69x |
| working agent, parallel (shipped) | 91/91 | 2 | 4 | 0 | 735,942 | 0.0825 | 0.70x |

## 1 · The instrumentation that found it
Turns, model calls, tokens and cost are logged per run (agent.py). With de-duplication deleted, nothing raised an exception: 70 of 91 trials ran to the step cap of 12 turns and the set cost 2.69x the working agent's tokens. The runs that did not loop are the escalations that end before the policy row is needed twice.

## 2 · The turn distribution
Working agent: median 4, worst legitimate run 10 (CLM-9007, four_lines_two_preauth_chases, sequential). Runaway: median 12, max 12, 70 trials at the cap. Caught: median 3, every looping trial stopped at turn 3.

## 3 · The fix, in the code layer, and why the other two guards were the wrong place
Action de-duplication caught it at turn 3, the first repeat, and named the cause (`duplicate_action: lookup_policy called again with identical arguments`). The step cap only fires at turn 12, many turns and several times the tokens later, and says nothing about why. The budget ceiling (60000 tokens) never fired: the runaway peaked below it, so a ceiling set from the legitimate worst case bounds the damage but does not detect the fault. A prompt fix cannot be relied on: the model is the thing that forgot; only the code layer remembers.

## 4 · Before and after
Restoring the guard truncates no legitimate run: the working agent passes 91/91 with the guard on, its worst legitimate run (10 turns) is inside the cap of 12, and no correct run ever repeats an action. The parallel form of the same agent passes 91/91 at 70% of the sequential tokens (D2c).
