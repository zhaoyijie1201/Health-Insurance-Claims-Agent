# D7 · failure 1 · the loop-control failure

Scripted backend, 15 cases, 3 trials per negative case. Tokens are chars/4 estimates with the same shape as a live bill (prefix re-sent every turn).

| configuration | pass | turns median | turns max | halted | tokens in | cost US$ | tokens vs before |
|---|---|---|---|---|---|---|---|
| working agent, sequential (before) | 33/33 | 2 | 8 | 0 | 335,837 | 0.0362 | 1.00x |
| minus the memory, de-duplication ON (caught) | 9/33 | 3 | 3 | {'duplicate_action': 24} | 204,542 | 0.0217 | 0.61x |
| minus the memory, de-duplication OFF (runaway) | 9/33 | 10 | 10 | {'step_cap': 24} | 764,534 | 0.0798 | 2.28x |
| working agent, parallel (shipped) | 33/33 | 2 | 4 | 0 | 244,174 | 0.0271 | 0.73x |

## 1 · The instrumentation that found it
Turns, model calls, tokens and cost are logged per run (agent.py). With de-duplication deleted, nothing raised an exception: 24 of 33 trials ran to the step cap of 10 turns and the set cost 2.28x the working agent's tokens. The runs that did not loop are the escalations that end before the policy row is needed twice.

## 2 · The turn distribution
Working agent: median 2, worst legitimate run 8 (CLM-8960, four lines, sequential). Runaway: median 10, max 10, 24 trials at the cap. Caught: median 3, every looping trial stopped at turn 3.

## 3 · The fix, in the code layer, and why the other two guards were the wrong place
Action de-duplication caught it at turn 3, the first repeat, and named the cause (`duplicate_action: lookup_policy called again with identical arguments`). The step cap only fires at turn 10, seven turns and roughly three times the tokens later, and says nothing about why. The budget ceiling (40000 tokens) never fired: the runaway peaked below it, so a ceiling set from the legitimate worst case bounds the damage but does not detect the fault. A prompt fix cannot be relied on: the model is the thing that forgot; only the code layer remembers.

## 4 · Before and after
Restoring the guard truncates no legitimate run: the working agent passes 33/33 with the guard on, its worst legitimate run (8 turns) is inside the cap of 10, and no correct run ever repeats an action. The parallel form of the same agent passes 33/33 at 73% of the sequential tokens (D2c).
