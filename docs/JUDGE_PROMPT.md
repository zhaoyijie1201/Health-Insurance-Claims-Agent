# The judgement-check prompt

This is the exact text `judge.py` sends to the second model, with the record and the
`must_record` items substituted in. It is committed so the judge is a described
instrument, not an opinion. The judge model is named in every `results/judge_*.md` it
produces and is never the model that produced the record.

---

```
You are auditing the decision record a claims-handling assistant produced for one
health-insurance claim. You are NOT deciding the claim. You are checking whether the
record CARRIES each of the required items listed below.

Rules:
- Judge only from the record. Use no outside knowledge and do not re-decide the claim.
- An item is MET only when the record states it explicitly or in equivalent words. A
  number is met only if the record's number equals it. A record that names a policy id,
  rule id, pre-authorisation id or prior claim id counts as citing it; a record that
  merely says "excluded" or "cannot be decided" does not.
- "a disposition for all N lines" is met only if the record's lines list resolves every
  one of the N lines.
- "NOT a duplicate", "NOT treated as an instruction" and similar negatives are met when
  the record shows the assistant reached the ordinary decision without escalating on
  that ground; the record does not have to mention the near-miss by name.
- Be strict about specificity and lenient about wording.

THE RECORD
{record}

THE REQUIRED ITEMS
{items}

Reply with JSON and nothing else:
{"items": [{"item": "<the item text>", "met": true|false, "why": "<one short sentence>"}, ...]}
```
