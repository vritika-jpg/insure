import html
import io
import json
import os
from datetime import datetime

import PyPDF2
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from prompts import COVERAGE_EXPLAINER_SYSTEM, COI_EXTRACTOR_SYSTEM

# ── Init ──────────────────────────────────────────────────────────────────────
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(
    page_title="inSURE",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
.main .block-container { max-width: 1080px; padding-top: 1.5rem; }

.app-header { text-align: center; padding: 1rem 0 0.25rem; }
.app-header h1 { font-size: 2.8rem; font-weight: 800; color: #1a3668;
                 letter-spacing: -1px; margin: 0; }
.app-header p  { color: #6b7280; font-size: 1rem; margin-top: 4px; }

/* ── Cards ── */
.summary-card {
    background: linear-gradient(135deg, #1a3668 0%, #2e5fa3 100%);
    color: white; border-radius: 12px; padding: 20px 24px; margin: 12px 0;
}
.summary-card h3 { color: white; margin: 0 0 8px; font-size: .8rem;
                   text-transform: uppercase; letter-spacing: 1px; opacity: .75; }
.summary-card p  { color: white; margin: 0; font-size: .97rem; line-height: 1.65; }

.card {
    background: white; border-radius: 10px; padding: 18px 20px;
    margin: 10px 0; box-shadow: 0 2px 10px rgba(0,0,0,.06);
    border: 1px solid #edf2f7;
}

/* ── Coverage gaps ── */
.gap-item {
    background: #fff5f5; border-left: 4px solid #e53e3e;
    padding: 9px 14px; margin: 5px 0; border-radius: 0 8px 8px 0;
    font-size: .9rem; color: #2d3748; line-height: 1.5;
}

/* ── Recommendations ── */
.rec-card {
    background: white; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 13px 16px; margin: 7px 0;
    display: flex; gap: 12px; align-items: flex-start;
}
.rec-rank {
    background: #1a3668; color: white; border-radius: 50%;
    width: 28px; height: 28px; min-width: 28px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 13px; flex-shrink: 0;
}
.rec-body   { flex: 1; }
.rec-title  { font-weight: 600; color: #1a202c; font-size: .93rem; margin: 0 0 4px; }
.rec-rationale { color: #718096; font-size: .84rem; margin: 0; line-height: 1.5; }

/* ── Badges ── */
.badge { display: inline-block; padding: 3px 13px; border-radius: 20px;
         font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
.badge-high   { background: #c6f6d5; color: #22543d; }
.badge-medium { background: #fefcbf; color: #744210; }
.badge-low    { background: #fed7d7; color: #822727; }

/* ── Follow-ups ── */
.followup-item {
    background: #ebf4ff; border-left: 4px solid #2e5fa3;
    padding: 8px 14px; margin: 5px 0; border-radius: 0 8px 8px 0;
    font-size: .88rem; color: #2d3748;
}

/* ── Section labels ── */
.section-label {
    font-size: .72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.5px; color: #9ca3af; margin: 18px 0 7px;
}

/* ── ACORD 25 ── */
.acord-wrapper {
    font-family: Arial, Helvetica, sans-serif; font-size: 10px;
    border: 1.5px solid #000; max-width: 900px; margin: 0 auto; background: white;
}
.acord-header {
    background: #1a3668; color: white; text-align: center;
    padding: 8px 4px; font-size: 13px; font-weight: bold; letter-spacing: 2px;
}
.acord-section-bg {
    background: #d0dcec; font-size: 7.5px; font-weight: bold;
    text-transform: uppercase; letter-spacing: .8px;
    padding: 3px 7px; border-bottom: 1px solid #bbb; border-top: 1px solid #bbb;
}
table.at { width: 100%; border-collapse: collapse; }
table.at td, table.at th {
    border: .75px solid #999; padding: 4px 6px; vertical-align: top; font-size: 10px;
}
.al  { font-size: 6.5px; color: #555; font-weight: bold; text-transform: uppercase;
        letter-spacing: .4px; display: block; }
.av  { font-size: 10px; font-weight: 600; color: #111; display: block; margin-top: 2px; }
.abp { font-size: 7.5px; color: #333; line-height: 1.4; margin: 0; }
.act { font-weight: 700; font-size: 9px; text-transform: uppercase; }
.all { font-size: 7px; color: #555; text-transform: uppercase; }
.alv { font-size: 9px; font-weight: 700; }
.acord-footer {
    background: #efefef; padding: 4px 8px; font-size: 6.5px;
    color: #666; text-align: center; border-top: 1px solid #bbb;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── OpenAI tool definition ────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_state_minimums",
            "description": (
                "Retrieves state-specific insurance minimum requirements. "
                "Call this before forming any analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "description": "Two-letter US state/territory code (e.g. 'CA', 'TX', 'DC')",
                    },
                    "insurance_type": {
                        "type": "string",
                        "enum": ["auto", "home"],
                        "description": "Type of insurance to check",
                    },
                },
                "required": ["state", "insurance_type"],
            },
        },
    }
]

_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state_minimums.json")


def _check_state_minimums(state: str, insurance_type: str) -> dict:
    try:
        with open(_JSON_PATH, "r") as f:
            data = json.load(f)
        s, t = state.upper().strip(), insurance_type.lower().strip()
        if t == "auto":
            return data["auto"].get(s, {"error": f"No minimum data found for {s}", "state": s})
        if t == "home":
            return data["home"]
        return {"error": "Invalid insurance_type. Use 'auto' or 'home'."}
    except Exception as exc:
        return {"error": str(exc)}


# ── Tab 1 helpers ─────────────────────────────────────────────────────────────
def analyze_coverage(situation: str, state: str, ins_type: str) -> dict:
    messages = [
        {"role": "system", "content": COVERAGE_EXPLAINER_SYSTEM},
        {
            "role": "user",
            "content": f"State: {state}\nInsurance type: {ins_type}\n\nSituation:\n{situation}",
        },
    ]

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        tool_choice="required",
        temperature=0.2,
    )
    msg = resp.choices[0].message

    if msg.tool_calls:
        tool_msgs = []
        for tc in msg.tool_calls:
            if tc.function.name == "check_state_minimums":
                args = json.loads(tc.function.arguments)
                result = _check_state_minimums(args["state"], args["insurance_type"])
                tool_msgs.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)}
                )

        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )
        messages.extend(tool_msgs)

        final = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        msg = final.choices[0].message

    return json.loads(msg.content)


def _confidence_badge(confidence: str) -> str:
    c = confidence.lower()
    cls = {"high": "badge-high", "medium": "badge-medium", "low": "badge-low"}.get(c, "badge-medium")
    desc = {
        "high": "All key details provided.",
        "medium": "Some details are missing.",
        "low": "Critical details are missing.",
    }.get(c, "")
    return (
        f'<div class="card" style="padding:14px 18px">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
        f'<span class="section-label" style="margin:0">Confidence</span>'
        f'<span class="badge {cls}">{c}</span>'
        f'</div>'
        f'<div style="font-size:.82rem;color:#6b7280">{desc}</div>'
        f"</div>"
    )


def render_coverage_result(result: dict) -> None:
    st.markdown(
        f'<div class="summary-card"><h3>Situation Summary</h3>'
        f'<p>{html.escape(result.get("situation_summary",""))}</p></div>',
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1, 1.4], gap="medium")

    with col_left:
        st.markdown(_confidence_badge(result.get("confidence", "medium")), unsafe_allow_html=True)

        followups = result.get("followup_questions", [])
        if followups:
            st.markdown('<div class="section-label">Follow-up Questions</div>', unsafe_allow_html=True)
            for q in followups:
                st.markdown(
                    f'<div class="followup-item">❓ {html.escape(q)}</div>',
                    unsafe_allow_html=True,
                )

    with col_right:
        gaps = result.get("coverage_gaps", [])
        if gaps:
            st.markdown('<div class="section-label">Coverage Gaps</div>', unsafe_allow_html=True)
            for g in gaps:
                st.markdown(
                    f'<div class="gap-item">▲ {html.escape(g)}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div class="card" style="color:#276749;font-weight:600">'
                "✓ No significant gaps identified with the information provided.</div>",
                unsafe_allow_html=True,
            )

    recs = result.get("recommendations", [])
    if recs:
        st.markdown('<div class="section-label">Recommendations</div>', unsafe_allow_html=True)
        for r in recs:
            st.markdown(
                f'<div class="rec-card">'
                f'<div class="rec-rank">{r.get("rank","•")}</div>'
                f'<div class="rec-body">'
                f'<div class="rec-title">{html.escape(r.get("recommendation",""))}</div>'
                f'<div class="rec-rationale">{html.escape(r.get("rationale",""))}</div>'
                f"</div></div>",
                unsafe_allow_html=True,
            )


# ── Tab 2 helpers ─────────────────────────────────────────────────────────────
def extract_pdf_text(uploaded_file) -> str:
    reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def extract_coi_data(pdf_text: str) -> dict:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": COI_EXTRACTOR_SYSTEM},
            {
                "role": "user",
                "content": f"Extract insurance information from this declaration page:\n\n{pdf_text[:10000]}",
            },
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def _f(val, fallback: str = "—") -> str:
    """Format a value for HTML display: escape and return fallback if absent."""
    if val and str(val).strip() not in ("", "null", "None"):
        return html.escape(str(val))
    return fallback


def render_acord25_html(d: dict) -> str:
    date_str = _f(d.get("policy_period_start"), datetime.now().strftime("%m/%d/%Y"))

    # Build coverage rows
    cov_rows = ""
    for cov in d.get("coverages") or []:
        ctype = _f(cov.get("type"), "Other")
        limit_lines = []
        for key, label in [
            ("combined_single_limit", "Combined Single Limit"),
            ("each_occurrence", "Each Occurrence"),
            ("aggregate", "Aggregate"),
            ("bodily_injury_per_person", "Bodily Injury / Person"),
            ("bodily_injury_per_accident", "Bodily Injury / Accident"),
            ("property_damage", "Property Damage"),
            ("deductible", "Deductible"),
        ]:
            if cov.get(key) and str(cov[key]).strip() not in ("", "null", "None"):
                limit_lines.append(
                    f'<span class="all">{html.escape(label)}:</span> '
                    f'<span class="alv">{html.escape(str(cov[key]))}</span>'
                )
        limits_html = "&nbsp; &nbsp;".join(limit_lines) if limit_lines else "—"
        cov_rows += (
            f"<tr><td colspan='6' style='background:#f7f9fc'>"
            f"<span class='act'>{ctype}</span></td></tr>"
            f"<tr><td colspan='6' style='padding:3px 6px;font-size:9px'>{limits_html}</td></tr>"
        )

    if not cov_rows:
        cov_rows = "<tr><td colspan='6' style='color:#9ca3af;font-style:italic;padding:8px'>No coverages extracted</td></tr>"

    boilerplate = (
        "THIS CERTIFICATE IS ISSUED AS A MATTER OF INFORMATION ONLY AND CONFERS NO RIGHTS UPON "
        "THE CERTIFICATE HOLDER. THIS CERTIFICATE DOES NOT AFFIRMATIVELY OR NEGATIVELY AMEND, "
        "EXTEND OR ALTER THE COVERAGE AFFORDED BY THE POLICIES BELOW."
    )

    return f"""
<div class="acord-wrapper">
  <div class="acord-header">CERTIFICATE OF LIABILITY INSURANCE</div>

  <table class="at">
    <tr>
      <td width="70%"><span class="al">This certificate is issued as a matter of information only</span></td>
      <td width="30%">
        <span class="al">Date (MM/DD/YYYY)</span>
        <span class="av">{date_str}</span>
      </td>
    </tr>
  </table>

  <table class="at">
    <tr>
      <td width="38%">
        <span class="al">Producer</span>
        <span class="av">{_f(d.get('producer_name'))}</span>
        <span class="av" style="font-weight:400;font-size:9px">{_f(d.get('producer_address'), '')}</span>
      </td>
      <td width="62%">
        <p class="abp">{boilerplate}</p>
      </td>
    </tr>
  </table>

  <table class="at">
    <tr>
      <td width="12%" style="background:#d0dcec">
        <span class="al" style="font-size:7px;writing-mode:horizontal-tb">Insured</span>
      </td>
      <td width="54%">
        <span class="av" style="font-size:11px">{_f(d.get('insured_name'))}</span>
        <span class="av" style="font-weight:400;font-size:9px">{_f(d.get('insured_address'), '')}</span>
      </td>
      <td width="34%">
        <span class="al">Additional Insured</span>
        <span class="av" style="font-weight:400">{_f(d.get('additional_insured'))}</span>
      </td>
    </tr>
  </table>

  <div class="acord-section-bg">Insurer(s) Affording Coverage</div>
  <table class="at">
    <tr>
      <td width="12%" style="background:#d0dcec"><span class="al">Insurer A</span></td>
      <td width="54%"><span class="av">{_f(d.get('insurer_name'))}</span></td>
      <td width="34%">
        <span class="al">Policy Number</span>
        <span class="av">{_f(d.get('policy_number'))}</span>
      </td>
    </tr>
    <tr>
      <td colspan="2">
        <span class="al">Policy Period</span>
        <span class="av">{_f(d.get('policy_period_start'))} &nbsp;–&nbsp; {_f(d.get('policy_period_end'))}</span>
      </td>
      <td><span class="al">Insurers B – F</span><span class="av" style="color:#9ca3af;font-weight:400">—</span></td>
    </tr>
  </table>

  <div class="acord-section-bg">Coverages — Certificate Number / Revision Number</div>
  <table class="at">
    <thead>
      <tr style="background:#eef2f7">
        <th colspan="4" style="font-size:7.5px;text-align:left;padding:3px 6px">Type of Insurance</th>
        <th colspan="2" style="font-size:7.5px;text-align:left;padding:3px 6px">Limits</th>
      </tr>
    </thead>
    <tbody>{cov_rows}</tbody>
  </table>

  <div class="acord-section-bg">Description of Operations / Locations / Vehicles</div>
  <table class="at">
    <tr><td style="min-height:44px;font-size:9.5px">{_f(d.get('description_of_operations'), 'N/A')}</td></tr>
  </table>

  <div class="acord-section-bg">Certificate Holder</div>
  <table class="at">
    <tr>
      <td width="45%" style="padding:7px 8px">
        <span class="av" style="font-size:11px">{_f(d.get('certificate_holder_name'))}</span>
        <span class="av" style="font-weight:400;font-size:9px">{_f(d.get('certificate_holder_address'), '')}</span>
      </td>
      <td width="55%" style="padding:7px 8px">
        <span class="al">Cancellation</span>
        <p class="abp" style="margin-top:4px">
          SHOULD ANY OF THE ABOVE DESCRIBED POLICIES BE CANCELLED BEFORE THE EXPIRATION DATE THEREOF,
          NOTICE WILL BE DELIVERED IN ACCORDANCE WITH THE POLICY PROVISIONS.
        </p>
        <div style="margin-top:14px;font-size:9px">
          AUTHORIZED REPRESENTATIVE
          <span style="border-bottom:1px solid #000;display:inline-block;width:170px;margin-left:6px">&nbsp;</span>
        </div>
      </td>
    </tr>
  </table>

  <div class="acord-footer">
    ACORD 25 (2016/03) &nbsp;|&nbsp; © 1988–2016 ACORD CORPORATION. All rights reserved.
    &nbsp;|&nbsp; Generated by inSURE — for informational purposes only.
  </div>
</div>
"""


def generate_coi_pdf(d: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.4 * inch,
        bottomMargin=0.4 * inch,
        leftMargin=0.4 * inch,
        rightMargin=0.4 * inch,
    )

    BLUE = colors.HexColor("#1a3668")
    LBLUE = colors.HexColor("#d0dcec")
    LGRAY = colors.HexColor("#efefef")
    BLACK = colors.black
    W = 7.2 * inch

    def ps(name, **kw):
        defaults = dict(fontName="Helvetica", leading=11, fontSize=9)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    def cell_p(label: str, value: str) -> Paragraph:
        esc_val = _f(value)
        return Paragraph(
            f'<font size="6" color="grey"><b>{html.escape(label.upper())}</b></font><br/>'
            f'<font size="9"><b>{esc_val}</b></font>',
            ps("cell"),
        )

    def sh(text: str) -> Table:
        t = Table(
            [[Paragraph(f'<font size="7" color="white"><b>{html.escape(text.upper())}</b></font>', ps("sh"))]],
            colWidths=[W],
        )
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BLUE),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        return t

    base_style = [
        ("BOX", (0, 0), (-1, -1), 0.5, BLACK),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BLACK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]

    story = []

    # Title
    title_t = Table(
        [[Paragraph('<font size="12" color="white"><b>CERTIFICATE OF LIABILITY INSURANCE</b></font>',
                    ps("title", alignment=1))]],
        colWidths=[W],
    )
    title_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(title_t)

    # Date / boilerplate
    bp = (
        "THIS CERTIFICATE IS ISSUED AS A MATTER OF INFORMATION ONLY AND CONFERS NO RIGHTS UPON THE "
        "CERTIFICATE HOLDER. THIS CERTIFICATE DOES NOT AFFIRMATIVELY OR NEGATIVELY AMEND, EXTEND OR "
        "ALTER THE COVERAGE AFFORDED BY THE POLICIES BELOW."
    )
    date_val = _f(d.get("policy_period_start"), datetime.now().strftime("%m/%d/%Y"))
    dt = Table(
        [[cell_p("Date (MM/DD/YYYY)", date_val),
          Paragraph(f'<font size="7">{bp}</font>', ps("bp", leading=9))]],
        colWidths=[1.6 * inch, 5.6 * inch],
    )
    dt.setStyle(TableStyle(base_style))
    story.append(dt)

    # Producer / Insured
    pi = Table(
        [[cell_p("Producer", d.get("producer_name", "")),
          cell_p("Insured", d.get("insured_name", ""))]],
        colWidths=[3.6 * inch, 3.6 * inch],
    )
    pi.setStyle(TableStyle(base_style))
    story.append(pi)

    # Insurer
    story.append(sh("Insurer(s) Affording Coverage"))
    period = f'{_f(d.get("policy_period_start"))} – {_f(d.get("policy_period_end"))}'
    ins_t = Table(
        [[cell_p("Insurer A", d.get("insurer_name")),
          cell_p("Policy Number", d.get("policy_number")),
          cell_p("Policy Period", period)]],
        colWidths=[3.2 * inch, 2.0 * inch, 2.0 * inch],
    )
    ins_t.setStyle(TableStyle(base_style + [("BACKGROUND", (0, 0), (0, 0), LBLUE)]))
    story.append(ins_t)

    # Coverages
    story.append(sh("Coverages"))
    cov_rows = [
        [Paragraph('<font size="7"><b>Type of Insurance</b></font>', ps("ch")),
         Paragraph('<font size="7"><b>Limits</b></font>', ps("cl"))],
    ]
    for cov in d.get("coverages") or []:
        parts = []
        for key, label in [
            ("combined_single_limit", "Combined Single Limit"),
            ("each_occurrence", "Each Occurrence"),
            ("aggregate", "Aggregate"),
            ("bodily_injury_per_person", "BI / Person"),
            ("bodily_injury_per_accident", "BI / Accident"),
            ("property_damage", "Property Damage"),
            ("deductible", "Deductible"),
        ]:
            v = cov.get(key)
            if v and str(v).strip() not in ("", "null", "None"):
                parts.append(
                    f'<font size="6.5" color="grey">{html.escape(label)}: </font>'
                    f'<font size="8.5"><b>{html.escape(str(v))}</b></font>'
                )
        limits_str = "  ".join(parts) if parts else "—"
        cov_rows.append([
            Paragraph(f'<font size="9"><b>{_f(cov.get("type"), "Other")}</b></font>', ps("ct")),
            Paragraph(limits_str, ps("lm", leading=11)),
        ])

    if len(cov_rows) == 1:
        cov_rows.append([Paragraph('<font size="8" color="grey">No coverages extracted</font>', ps("nc")), ""])

    cov_style = list(base_style) + [("BACKGROUND", (0, 0), (-1, 0), LBLUE)]
    for i in range(2, len(cov_rows), 2):
        cov_style.append(("BACKGROUND", (0, i), (-1, i), LGRAY))
    cov_t = Table(cov_rows, colWidths=[3.0 * inch, 4.2 * inch])
    cov_t.setStyle(TableStyle(cov_style))
    story.append(cov_t)

    # Description of Operations
    story.append(sh("Description of Operations / Locations / Vehicles"))
    desc_t = Table(
        [[Paragraph(f'<font size="8">{_f(d.get("description_of_operations"), "N/A")}</font>', ps("desc"))]],
        colWidths=[W],
    )
    desc_t.setStyle(TableStyle(base_style + [("MINROWHEIGHT", (0, 0), (-1, -1), 44)]))
    story.append(desc_t)

    # Certificate holder / Cancellation
    story.append(sh("Certificate Holder"))
    cancel = Paragraph(
        '<font size="7">SHOULD ANY OF THE ABOVE DESCRIBED POLICIES BE CANCELLED BEFORE THE EXPIRATION '
        'DATE THEREOF, NOTICE WILL BE DELIVERED IN ACCORDANCE WITH THE POLICY PROVISIONS.<br/><br/>'
        'AUTHORIZED REPRESENTATIVE: ______________________________</font>',
        ps("ct2", leading=10),
    )
    ch_t = Table(
        [[Paragraph(
            f'<font size="10"><b>{_f(d.get("certificate_holder_name"))}</b></font><br/>'
            f'<font size="8">{_f(d.get("certificate_holder_address"), "")}</font>',
            ps("chd"),
        ), cancel]],
        colWidths=[3.6 * inch, 3.6 * inch],
    )
    ch_t.setStyle(TableStyle(base_style + [("MINROWHEIGHT", (0, 0), (-1, -1), 60)]))
    story.append(ch_t)

    # Footer
    foot_t = Table(
        [[Paragraph(
            '<font size="6" color="grey">ACORD 25 (2016/03) | © 1988-2016 ACORD CORPORATION. '
            'All rights reserved. | Generated by inSURE — for informational purposes only.</font>',
            ps("ft", alignment=1),
        )]],
        colWidths=[W],
    )
    foot_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LGRAY),
        ("BOX", (0, 0), (-1, -1), 0.5, BLACK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(foot_t)

    doc.build(story)
    return buffer.getvalue()


# ── Layout ───────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="app-header"><h1>inSURE</h1>'
    "<p>AI-powered insurance coverage analysis &amp; certificate generation</p></div>",
    unsafe_allow_html=True,
)

tab1, tab2 = st.tabs(["🔍 Coverage Explainer", "📄 COI Generator"])

# ── Tab 1: Coverage Explainer ─────────────────────────────────────────────────
with tab1:
    st.markdown("#### Describe your insurance situation")

    STATE_CODES = [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DC", "DE", "FL",
        "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
        "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
        "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
        "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    ]

    col_form, col_results = st.columns([1, 1.7], gap="large")

    with col_form:
        state = st.selectbox("State", options=STATE_CODES, index=STATE_CODES.index("CA"))
        ins_type = st.radio("Insurance Type", ["auto", "home"], horizontal=True)
        situation = st.text_area(
            "Situation",
            placeholder=(
                "e.g. I just bought a used 2020 Honda Civic in Texas. "
                "I carry state minimum liability only. The car is financed, "
                "I drive ~14,000 miles/year, and I have a teenage driver on the policy."
            ),
            height=185,
            label_visibility="collapsed",
        )
        submitted = st.button("Analyze Coverage →", type="primary", use_container_width=True)

    with col_results:
        if submitted:
            if not situation.strip():
                st.warning("Please describe your situation first.")
            else:
                with st.spinner("Fetching state requirements and analyzing…"):
                    try:
                        result = analyze_coverage(situation, state, ins_type)
                        st.session_state["coverage_result"] = result
                    except Exception as exc:
                        st.error(f"Analysis failed: {exc}")

        if "coverage_result" in st.session_state:
            render_coverage_result(st.session_state["coverage_result"])

# ── Tab 2: COI Generator ──────────────────────────────────────────────────────
with tab2:
    st.markdown("#### Upload a Declaration Page (PDF)")
    uploaded = st.file_uploader(
        "Drag and drop or browse — PDF dec pages, binders, or existing COIs",
        type=["pdf"],
        label_visibility="collapsed",
    )

    if uploaded:
        with st.spinner("Extracting text and parsing fields…"):
            try:
                pdf_text = extract_pdf_text(uploaded)
                if not pdf_text:
                    st.error(
                        "Could not extract text from this PDF. "
                        "It may be a scanned image — try a text-based PDF."
                    )
                    st.stop()
                coi_data = extract_coi_data(pdf_text)
                st.session_state["coi_data"] = coi_data
                st.session_state["coi_pdf"] = generate_coi_pdf(coi_data)
            except Exception as exc:
                st.error(f"Extraction failed: {exc}")

    if "coi_data" in st.session_state:
        d = st.session_state["coi_data"]

        st.markdown("---")
        col_hdr, col_dl = st.columns([3, 1])
        with col_hdr:
            st.markdown("##### Certificate of Liability Insurance — ACORD 25")
        with col_dl:
            fname = (d.get("insured_name") or "certificate").replace(" ", "_")
            st.download_button(
                label="⬇ Download PDF",
                data=st.session_state["coi_pdf"],
                file_name=f"COI_{fname}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )

        st.markdown(render_acord25_html(d), unsafe_allow_html=True)

        with st.expander("Extracted Fields (raw JSON)"):
            st.json(d)
