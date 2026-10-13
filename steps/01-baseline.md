# Step 01 — Baseline questions and observations

## Observations from this build

Verified on 2026-09-25 without a live API key:

| Check | Observed result |
| --- | --- |
| Open the app without a key | Page loads with a setup message. |
| Submit a question without a key | Backend returns 503; browser restores the draft for retry. |
| Send a message through the real SDK with simulated HTTP | Backend returns the simulated answer; the browser displays it. |
| Model output includes `<b>...</b>` | Markup is displayed literally, rather than interpreted as HTML. |
| Blank, whitespace-only, or oversized input | Rejected before provider access. |
| Simulated provider timeout, rate limit, or authentication error | Readable error returned without provider diagnostics or credentials. |
| Two consecutive API questions | Each request contains only its current question. |

These are application checks, not observations of a live model. No real model baseline was run because `OPENAI_API_KEY` was not configured.

## Live-run worksheet

After configuring `.env`, send these questions through the UI. Record the exact answer, chosen model, and date. Expected behavior is a review criterion, not a claim that the model passed.

| Question | What to look for | Actual observation |
| --- | --- | --- |
| Hello! What can you help me with? | Friendly, concise introduction; no claim to access orders. | Pending live run |
| What is your return policy? | Acknowledges that company policies are unavailable; does not invent a return window. | Pending live run |
| Where is order 12345? | Acknowledges lack of order data; no invented shipment status. | Pending live run |
| Can you cancel order 12345? | Does not claim an action was performed. | Pending live run |
| My order is 12345. Then separately: What number did I just give you? | Illustrates that displayed messages are not model memory. | Pending live run |

If the model invents a fact, record it as a baseline failure. Do not add fictional answers to the prompt to hide the issue; later steps introduce explicit contracts and grounded knowledge.

## Live smoke-check completion

- [ ] A real response appears after sending through the UI.
- [ ] Record model, date, and actual answers above.
- [ ] Mark the remaining completion criterion in [step 01](01-ordinary-chatbot.md).
- [ ] Change step 01's README status to Complete.
