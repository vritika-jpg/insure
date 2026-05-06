"""
eval.py — inSURE Evaluation Script
Runs 8 test cases through:
  1. Full system (tool use + state minimums + structured output)
  2. Baseline (prompt-only, no tool, no state data)
Scores each with GPT-4o as judge on 3 dimensions (0-2 each, max 6).
Saves results to eval_results.json and prints a summary table.

Usage:
  python eval.py

Requires: OPENAI_API_KEY in .env
"""

import json
import os
import time
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Load test cases ────────────────────────────────────────────────────────────
with open("test_cases.json") as f:
    TEST_CASES = json.load(f)

with open("state_minimums.json") as f:
    STATE_MINIMUMS = json.load(f)

# ── Prompts ────────────────────────────────────────────────────────────────────
FULL_SYSTEM = """You are an insurance coverage advisor for an independent agency.
You help personal lines clients (home and auto) understand their coverage situation.

You have access to a tool that retrieves state-specific minimum requirements.
Always call check_state_minimums before forming your analysis.

Return ONLY valid JSON with this exact structure:
{
  "situation_summary": "2-3 sentence plain-English recap",
  "coverage_gaps": ["gap 1", "gap 2", ...],
  "recommendations": [
    {"rank": 1, "recommendation": "...", "rationale": "..."},
    ...
  ],
  "confidence": "high|medium|low",
  "followup_questions": ["question 1", ...]
}

If the situation is too vague, set confidence to low and ask clarifying questions.
If the request is out of scope (commercial lines, specialty), say so clearly in situation_summary and return empty gaps and recommendations."""

BASELINE_SYSTEM = """You are a general insurance assistant.
Given a client's situation, return a JSON object with:
{
  "situation_summary": "...",
  "coverage_gaps": [...],
  "recommendations": [{"rank": 1, "recommendation": "...", "rationale": "..."}],
  "confidence": "high|medium|low",
  "followup_questions": [...]
}
Return only valid JSON."""

JUDGE_SYSTEM = """You are an expert insurance evaluator scoring AI-generated coverage recommendations.
Score the response on three dimensions, each 0-2:

1. Coverage Accuracy (0-2)
   2 = correctly identifies all major gaps and recommendations for the situation
   1 = partially correct, misses 1-2 important items or includes minor errors
   0 = incorrect, missing major gaps, or hallucinates inappropriate coverage

2. Groundedness (0-2)
   2 = recommendations are specific to the client's state and situation
   1 = partially grounded, some generic advice mixed in
   0 = generic advice with no state/situation specificity

3. Actionability (0-2)
   2 = recommendations are concrete, prioritized, and a client could act on them
   1 = somewhat vague or not prioritized
   0 = vague, unhelpful, or too generic to act on

Return ONLY valid JSON:
{"coverage_accuracy": 0-2, "groundedness": 0-2, "actionability": 0-2, "reasoning": "1-2 sentences"}"""

# ── Tool definition ────────────────────────────────────────────────────────────
TOOLS = [{
    "type": "function",
    "function": {
        "name": "check_state_minimums",
        "description": "Retrieves state-specific insurance minimum requirements.",
        "parameters": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "description": "Two-letter state code"},
                "insurance_type": {"type": "string", "enum": ["auto", "home"]}
            },
            "required": ["state", "insurance_type"]
        }
    }
}]

def check_state_minimums(state: str, insurance_type: str) -> dict:
    s, t = state.upper().strip(), insurance_type.lower()
    if t == "auto":
        return STATE_MINIMUMS["auto"].get(s, {"error": f"No data for {s}"})
    return STATE_MINIMUMS.get("home", {})

# ── Full system call ───────────────────────────────────────────────────────────
def run_full_system(tc: dict) -> dict:
    messages = [
        {"role": "system", "content": FULL_SYSTEM},
        {"role": "user", "content": f"State: {tc['state']}\nInsurance type: {tc['insurance_type']}\n\nSituation:\n{tc['situation']}"}
    ]
    resp = client.chat.completions.create(
        model="gpt-4o-mini", messages=messages,
        tools=TOOLS, tool_choice="required", temperature=0.2
    )
    msg = resp.choices[0].message
    if msg.tool_calls:
        tool_results = []
        assistant_tool_calls = []
        for tc_call in msg.tool_calls:
            args = json.loads(tc_call.function.arguments)
            result = check_state_minimums(args["state"], args["insurance_type"])
            tool_results.append({
                "role": "tool",
                "tool_call_id": tc_call.id,
                "content": json.dumps(result)
            })
            assistant_tool_calls.append({
                "id": tc_call.id, "type": "function",
                "function": {"name": tc_call.function.name, "arguments": tc_call.function.arguments}
            })
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": assistant_tool_calls})
        messages.extend(tool_results)
        final = client.chat.completions.create(
            model="gpt-4o-mini", messages=messages,
            temperature=0.2, response_format={"type": "json_object"}
        )
        return json.loads(final.choices[0].message.content)
    return json.loads(msg.content)

# ── Baseline call ──────────────────────────────────────────────────────────────
def run_baseline(tc: dict) -> dict:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": BASELINE_SYSTEM},
            {"role": "user", "content": f"State: {tc['state']}\nInsurance type: {tc['insurance_type']}\n\nSituation:\n{tc['situation']}"}
        ],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    return json.loads(resp.choices[0].message.content)

# ── Model-as-judge ─────────────────────────────────────────────────────────────
def judge(tc: dict, response: dict) -> dict:
    prompt = f"""Test case: {tc['label']}
State: {tc['state']} | Type: {tc['insurance_type']}
Situation: {tc['situation']}

Expected gaps (for reference): {tc.get('expected_gaps', [])}
Expected recommendations (for reference): {tc.get('expected_recommendations', [])}

AI Response:
{json.dumps(response, indent=2)}

Score this response."""
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    return json.loads(resp.choices[0].message.content)

# ── Main eval loop ─────────────────────────────────────────────────────────────
def main():
    results = []
    print(f"\n{'='*70}")
    print(f"inSURE Evaluation — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*70}\n")

    for tc in TEST_CASES:
        print(f"Running {tc['id']}: {tc['label']}...")

        # Full system
        try:
            full_response = run_full_system(tc)
            full_score = judge(tc, full_response)
            full_total = full_score["coverage_accuracy"] + full_score["groundedness"] + full_score["actionability"]
        except Exception as e:
            full_response = {"error": str(e)}
            full_score = {"coverage_accuracy": 0, "groundedness": 0, "actionability": 0, "reasoning": f"Error: {e}"}
            full_total = 0

        time.sleep(1)  # avoid rate limits

        # Baseline
        try:
            base_response = run_baseline(tc)
            base_score = judge(tc, base_response)
            base_total = base_score["coverage_accuracy"] + base_score["groundedness"] + base_score["actionability"]
        except Exception as e:
            base_response = {"error": str(e)}
            base_score = {"coverage_accuracy": 0, "groundedness": 0, "actionability": 0, "reasoning": f"Error: {e}"}
            base_total = 0

        time.sleep(1)

        delta = full_total - base_total
        print(f"  Full system: {full_total}/6 | Baseline: {base_total}/6 | Delta: {'+' if delta >= 0 else ''}{delta}")

        results.append({
            "id": tc["id"],
            "label": tc["label"],
            "state": tc["state"],
            "type": tc["insurance_type"],
            "full_system": {
                "response": full_response,
                "scores": full_score,
                "total": full_total
            },
            "baseline": {
                "response": base_response,
                "scores": base_score,
                "total": base_total
            },
            "delta": delta
        })

    # ── Summary table ──────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"{'ID':<6} {'Label':<35} {'Full':>5} {'Base':>5} {'Delta':>6}")
    print(f"{'-'*70}")
    full_totals, base_totals = [], []
    for r in results:
        print(f"{r['id']:<6} {r['label']:<35} {r['full_system']['total']:>5}/6 {r['baseline']['total']:>5}/6 {'+' if r['delta']>=0 else ''}{r['delta']:>5}")
        full_totals.append(r['full_system']['total'])
        base_totals.append(r['baseline']['total'])

    avg_full = sum(full_totals) / len(full_totals)
    avg_base = sum(base_totals) / len(base_totals)
    print(f"{'-'*70}")
    print(f"{'AVERAGE':<41} {avg_full:>5.1f}/6 {avg_base:>5.1f}/6 {'+' if avg_full>=avg_base else ''}{avg_full-avg_base:>5.1f}")
    print(f"{'='*70}\n")

    # Save results
    out_path = "eval_results.json"
    with open(out_path, "w") as f:
        json.dump({
            "run_at": datetime.now().isoformat(),
            "summary": {
                "avg_full_system": round(avg_full, 2),
                "avg_baseline": round(avg_base, 2),
                "avg_delta": round(avg_full - avg_base, 2),
                "n_cases": len(results)
            },
            "results": results
        }, f, indent=2)

    print(f"Full results saved to {out_path}")
    print("Spot-check TC01, TC03, TC06 manually — those are the most insurance-specific cases.\n")

if __name__ == "__main__":
    main()
