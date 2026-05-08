# InSure — Insurance Coverage Advisor

Insurance coverage analysis and certificate generation, built with Streamlit and GPT-4o-mini.

---

## Context, User, and Problem

**User:** Clients of independent insurance agencies with limited coverage literacy — renters, homeowners, and auto policyholders who don't know what they have, what they're missing, or what they need.

**Workflow being improved:** Two workflows at an independent agency. First, the client intake and education step — agents spend significant time explaining basic coverage concepts and identifying gaps before any productive quoting can begin. Second, COI generation — agents manually extract fields from declaration pages and fill ACORD 25 forms, a tedious task done dozens of times per week.

**Why it matters:** Independent agencies compete on speed and service quality. Automating coverage education gives clients consistent guidance before their first meeting. Automating COI generation saves agents 10-15 minutes per certificate.

---

## Features

### Tab 1 — Coverage Explainer

Describe your home or auto insurance situation in plain English. InSure checks your state's minimum requirements and returns:

- **Situation summary** — plain-English recap of your coverage
- **Coverage gaps** — specific things you're missing or under-covered on
- **Ranked recommendations** — prioritized actions with rationale
- **Confidence level** — how complete the analysis is based on info provided
- **Follow-up questions** — what to clarify for a better assessment

### Tab 2 — COI Generator

Upload a PDF declaration page. InSure extracts the key fields and fills the official **ACORD 25 (2016/03) Certificate of Liability Insurance** form, downloadable as a PDF.

Extracted fields: insured name & address, producer, insurer, policy number, policy period, all coverage types and limits, description of operations, certificate holder.

---

## Solution and Design

**Key design choices:**

- **No RAG.** The coverage knowledge base is small and stable — it fits directly in the system prompt and a JSON lookup file. RAG would be over-engineering for this corpus size.
- **Tool use for state data.** State minimums are structured data retrieved on demand via a function call (`check_state_minimums`), not pre-loaded into every prompt.
- **Structured outputs.** The system prompt constrains the model to return a defined JSON schema, enabling consistent UI rendering and programmatic evaluation.
- **Scope-limited to personal lines.** The system explicitly refuses commercial lines requests and flags them for a licensed agent.
- **Official ACORD 25 form filling.** The COI generator fills the real ACORD 25 (2016/03) fillable PDF using `pypdf`, mapping extracted JSON fields directly to the form's named fields. No custom PDF layout code — the form structure is already correct by definition.

---

## Evaluation and Results

**Baseline:** A prompt-only version of the coverage explainer — same input, no tool call, no state minimums data. Represents the "just ask ChatGPT" baseline.

**Test set:** 8 synthetic client scenarios across financed auto, first-time renter, home-based business, new homeowner, older paid-off car, new driver, and two edge cases (vague input, out-of-scope commercial).

**Rubric:** Each response scored 0–2 on three dimensions by GPT-4o as model-as-judge: coverage accuracy, groundedness, and actionability. Max 6 per case.

| ID | Scenario | InSure | Baseline | Delta |
|----|----------|--------|----------|-------|
| TC01 | Financed auto, teen driver | 6/6 | 6/6 | 0 |
| TC02 | First apartment renter, MD | 6/6 | 3/6 | +3 |
| TC03 | Home-based photography business | 2/6 | 3/6 | -1 |
| TC04 | New homeowner, VA | 4/6 | 3/6 | +1 |
| TC05 | Old paid-off car, liability only | 3/6 | 3/6 | 0 |
| TC06 | New driver, no prior coverage | 2/6 | 3/6 | -1 |
| TC07 | Edge: minimal input | 6/6 | 6/6 | 0 |
| TC08 | Edge: out-of-scope commercial | 6/6 | 0/6 | +6 |
| | **Average** | **4.4/6** | **3.4/6** | **+1.0** |

**What the results show:** InSure wins on average (4.4 vs 3.4). Biggest gains on TC02 (tool correctly retrieved MD-specific minimums) and TC08 (correctly refused a commercial lines request; baseline hallucinated home coverage advice for a restaurant owner). TC03 and TC06 underperformed — TC06 was overly cautious and asked for clarification instead of advising; TC03 revealed a gap in the system prompt around inland marine and E&O policies. Both are honest failure cases.

**Where a human should stay involved:** Any low-confidence output, commercial lines questions, carrier recommendations, and price quotes are all out of scope and escalated to a licensed agent.

---

## Artifact Snapshot

*(Add screenshots here — one of the Coverage Explainer output card, one of the COI generator)*

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/vritika-jpg/insure.git
cd insure
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Add your OpenAI API key**

Create a `.env` file in the project root:
```
OPENAI_API_KEY=sk-proj-...
```

**4. Run the app**
```bash
streamlit run app.py
```

**5. Run the evaluation**
```bash
python eval.py
```
Results saved to `eval_results.json`.

---

## Project Structure

```
insure/
├── app.py                     # Main Streamlit app
├── prompts.py                 # System prompts for GPT-4o-mini
├── acord25_template.pdf.pdf   # Official fillable ACORD 25 form (2016/03)
├── state_minimums.json        # Auto and home insurance minimums by state
├── eval.py                    # Evaluation script
├── test_cases.json            # 8 synthetic test cases with ground-truth answers
├── eval_results.json          # Evaluation output
├── requirements.txt
└── .env                       # Your API key (not committed)
```

## Requirements

- Python 3.9+
- OpenAI API key (GPT-4o-mini)
- `pypdf>=4.0.0` (for reading uploaded PDFs and filling the ACORD 25 template)

---

## Disclaimer

InSure is for informational and educational purposes only. It does not constitute legal or financial advice. Always consult a licensed insurance professional before making coverage decisions.
