# inSURE

Insurance coverage analysis and certificate generation, built with Streamlit and GPT-4o-mini.

## Features

### Tab 1 — Coverage Explainer
Describe your home or auto insurance situation in plain English. inSURE checks your state's minimum requirements and returns:
- **Situation summary** — plain-English recap of your coverage
- **Coverage gaps** — specific things you're missing or under-covered on
- **Ranked recommendations** — prioritized actions with rationale
- **Confidence level** — how complete the analysis is based on info provided
- **Follow-up questions** — what to clarify for a better assessment

### Tab 2 — COI Generator
Upload a PDF declaration page. inSURE extracts the key fields and renders a filled **ACORD 25-style Certificate of Liability Insurance**, downloadable as a PDF.

Extracted fields: insured name & address, producer, insurer, policy number, policy period, all coverage types and limits, description of operations, certificate holder.

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

---

## Project Structure

```
insure/
├── app.py                # Main Streamlit app
├── prompts.py            # System prompts for GPT-4o-mini
├── state_minimums.json   # Auto insurance minimums for all 50 states + DC
├── requirements.txt
└── .env                  # Your API key (not committed)
```

## Requirements

- Python 3.9+
- OpenAI API key (GPT-4o-mini)

## Disclaimer

inSURE is for informational and educational purposes only. It does not constitute legal or financial advice. Always consult a licensed insurance professional for coverage decisions.
