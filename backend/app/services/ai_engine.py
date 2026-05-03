# app/services/ai_engine.py
# Agent brain — form parser, data retrieval, form filler, orchestrator.
# Owner: AI (Person 2)

import base64
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Dict

from openai import OpenAI

from app.config import settings
from app.models.schemas import (
    CallResponses,
    ClinicalBrief,
    CompletedForm,
    CompletedFormField,
    CompoundQuestion,
    FormField,
    FormSchema,
    MissingField,
    PrefilledField,
    PrefilledForm,
    FormStats,
    CheckInScannedField,
    TranscriptTurn,
)
from app.services import fhir_service

# ── OpenAI client ─────────────────────────────────────────────────────────────

def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def _chat(system: str, user: str, model: str = "gpt-4o") -> str:
    """Single-turn LLM call — returns the assistant message as a string."""
    response = _client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


# ── In-memory store (replace with DB when Person 1 sets up tables) ────────────

_form_schemas: Dict[str, FormSchema] = {}
_prefilled_forms: Dict[str, PrefilledForm] = {}
_completed_forms: Dict[str, CompletedForm] = {}
_clinical_briefs: Dict[str, ClinicalBrief] = {}


# ── Agent 1: Form parser ──────────────────────────────────────────────────────

_PARSE_SYSTEM = """
You are a medical form parser. Given the text of a healthcare intake form,
extract every field the form requires. For each field identify:
- field_id: unique snake_case identifier
- label: human-readable label exactly as it appears on the form
- type: one of string | date | phone | boolean | email | signature | number
- required: true or false — when in doubt, mark as true. Fields like name, DOB,
  address, phone, insurance, emergency contact, and consent are always required.
  Only mark optional if the form clearly indicates it (e.g. "if applicable").
- section: one of demographics | insurance | medical_history | consent | other
- fhir_mapping: the FHIR resource path if applicable — use these exact paths:
    Patient.name, Patient.birthDate, Patient.gender,
    Patient.telecom.phone  (for phone/mobile fields),
    Patient.telecom.email  (for email fields — NOT Patient.telecom),
    Patient.address, Patient.identifier (SSN),
    Patient.contact.name, Patient.contact.telecom, Patient.contact.relationship,
    Coverage.payor (insurance company), Coverage.identifier (policy/member ID),
    Coverage.subscriber (policy holder name),
    AllergyIntolerance, MedicationRequest, Condition
  Omit fhir_mapping entirely if the field has no FHIR equivalent.

Return ONLY valid JSON matching this shape, no markdown, no explanation:
{
  "form_name": "<name>",
  "fields": [ { "field_id": "...", "label": "...", "type": "...",
                "required": true, "section": "...", "fhir_mapping": "..." } ]
}
""".strip()


def parse_form(ocr_text: str) -> FormSchema:
    """
    Agent 1 — parse OCR/PDF text into a structured FormSchema.
    Stores the result internally and returns it with a generated form_id.
    """
    raw = _chat(_PARSE_SYSTEM, ocr_text)

    # Strip markdown code fences if the model adds them anyway
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    parsed = json.loads(raw)
    form_id = str(uuid.uuid4())

    schema = FormSchema(
        form_id=form_id,
        form_name=parsed.get("form_name", "Untitled Form"),
        fields=[FormField(**f) for f in parsed["fields"]],
    )
    _form_schemas[form_id] = schema
    return schema


# ── Agent 2: Data retrieval + diff (tool-calling agent) ───────────────────────

_RETRIEVAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_patient_demographics",
            "description": (
                "Retrieve patient demographics from the EHR: name, date of birth, gender, "
                "phone, email, home address, SSN, emergency contact details, and insurance info."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "The patient identifier"}
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_allergies",
            "description": "Retrieve the patient's known drug and substance allergies from the EHR.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"}
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_medications",
            "description": "Retrieve the patient's current medications and dosages from the EHR.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"}
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_conditions",
            "description": "Retrieve the patient's active medical conditions and diagnoses from the EHR.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"}
                },
                "required": ["patient_id"],
            },
        },
    },
]

_RETRIEVAL_SYSTEM = """
You are a medical data retrieval agent with access to a patient's EHR (electronic health record).

Given a list of intake form fields, your job is to:
1. Call the appropriate EHR tools to retrieve patient data — only call what you need.
2. Match retrieved values to form fields as accurately as possible.
3. Auto-fill the following without calling tools or asking the patient:
   - Fields with type "signature": fill with the patient's full name (from demographics).
   - Fields asking for today's date or a signing date: fill with today's date in YYYY-MM-DD format.
4. For any remaining field you cannot fill from EHR data, write a short, natural question
   a nurse would ask the patient over the phone (one sentence, no jargon).

Return ONLY valid JSON, no markdown fences, in exactly this shape:
{
  "filled": [{"field_id": "...", "value": "..."}],
  "missing": [{"field_id": "...", "label": "...", "question": "..."}]
}
Every field from the input must appear in exactly one of the two lists.
""".strip()


def _run_retrieval_tools(name: str, args: dict) -> str:
    """Dispatch a tool call from the retrieval agent to the FHIR service."""
    pid = args.get("patient_id", "")
    if name == "get_patient_demographics":
        return json.dumps(fhir_service.get_patient(pid) or {})
    if name == "get_allergies":
        return json.dumps(fhir_service.get_allergies(pid))
    if name == "get_medications":
        return json.dumps(fhir_service.get_medications(pid))
    if name == "get_conditions":
        return json.dumps(fhir_service.get_conditions(pid))
    return json.dumps({"error": f"unknown tool: {name}"})


def retrieve_and_diff(form_schema: FormSchema, patient_id: str) -> PrefilledForm:
    """
    Agent 2 — tool-calling agent that queries the EHR and diffs against the form.
    The LLM decides which tools to call; filled fields come from EHR tool results;
    missing fields get a conversational question generated by the agent.
    """
    fields_payload = [
        {
            "field_id": f.field_id,
            "label": f.label,
            "type": f.type,
            "required": f.required,
            "fhir_mapping": f.fhir_mapping,
        }
        for f in form_schema.fields
    ]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    messages: list[dict] = [
        {"role": "system", "content": _RETRIEVAL_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Patient ID: {patient_id}\n"
                f"Today's date: {today}\n\n"
                f"Form fields to fill:\n{json.dumps(fields_payload, indent=2)}"
            ),
        },
    ]

    client = _client()

    # Agentic loop — runs until the model stops calling tools
    while True:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=_RETRIEVAL_TOOLS,
            temperature=0,
        )
        choice = response.choices[0]
        messages.append(choice.message)

        if choice.finish_reason != "tool_calls":
            break

        for tc in choice.message.tool_calls:
            args = json.loads(tc.function.arguments)
            result = _run_retrieval_tools(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    raw = choice.message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    agent_result = json.loads(raw)

    field_lookup = {f.field_id: f for f in form_schema.fields}
    filled = [
        PrefilledField(field_id=f["field_id"], value=f["value"], source="ehr", confidence=0.95)
        for f in agent_result.get("filled", [])
        if f.get("value") is not None
    ]
    missing = [
        MissingField(
            field_id=f["field_id"],
            label=f["label"],
            question=f["question"],
            type=field_lookup[f["field_id"]].type if f["field_id"] in field_lookup else "string",
            required=field_lookup[f["field_id"]].required if f["field_id"] in field_lookup else False,
        )
        for f in agent_result.get("missing", [])
    ]

    questions = _group_into_questions(missing)

    prefilled = PrefilledForm(
        form_id=form_schema.form_id,
        patient_id=patient_id,
        filled_fields=filled,
        missing_fields=missing,
        questions=questions,
        stats=FormStats(
            total=len(form_schema.fields),
            filled=len(filled),
            missing=len(missing),
        ),
    )
    _prefilled_forms[form_schema.form_id] = prefilled
    return prefilled


def local_prefill(form_schema: "FormSchema", patient_id: str) -> "PrefilledForm":
    """
    Fallback prefill that uses patient data directly from the store — no OpenAI needed.
    Called when OPENAI_API_KEY is not set or the LLM call fails.
    """
    from app.services import store as _store
    from datetime import date

    patient = _store.get_patient(patient_id)

    FIELD_MAP: dict = {}
    if patient:
        full_name = f"{patient.first_name} {patient.last_name}"
        FIELD_MAP = {
            "full_name": full_name,
            "date_of_birth": patient.date_of_birth,
            "gender": patient.gender,
            "phone": patient.phone,
            "email": patient.email,
            "address": patient.address,
            "insurance_provider": patient.insurance_provider,
            "insurance_id": patient.insurance_id,
            "emergency_contact_name": patient.emergency_contact_name,
            "emergency_contact_phone": patient.emergency_contact_phone,
            "emergency_contact_relation": patient.emergency_contact_relation,
            "consent_signature": full_name,
            "consent_date": date.today().isoformat(),
        }
        # remove None values
        FIELD_MAP = {k: v for k, v in FIELD_MAP.items() if v is not None}

    field_lookup = {f.field_id: f for f in form_schema.fields}
    filled = []
    missing = []

    for field in form_schema.fields:
        val = FIELD_MAP.get(field.field_id)
        if val is not None:
            filled.append(PrefilledField(field_id=field.field_id, value=val, source="ehr", confidence=0.9))
        else:
            missing.append(MissingField(
                field_id=field.field_id,
                label=field.label,
                question=f"Could you please provide your {field.label.lower()}?",
                type=field.type,
                required=field.required,
            ))

    prefilled = PrefilledForm(
        form_id=form_schema.form_id,
        patient_id=patient_id,
        filled_fields=filled,
        missing_fields=missing,
        questions=[],
        stats=FormStats(
            total=len(form_schema.fields),
            filled=len(filled),
            missing=len(missing),
        ),
    )
    _prefilled_forms[form_schema.form_id] = prefilled
    return prefilled


_GROUP_SYSTEM = """
You are scripting a pre-visit phone call for a medical office assistant.
You have a list of form fields that still need to be collected from the patient,
and optionally a short statement the patient already made (their opening answer).

Your job: write the fewest, most natural questions possible to collect the remaining fields.

Rules:
- If the patient's opening statement already clearly answers a field, OMIT that field
  entirely — do not ask about it again. Only omit if the information is unambiguous.
- Group related fields into one question (1–4 fields per question, never more).
- The question must sound like something a real person says — NOT a list of fields
  read aloud. If grouping fields makes the question feel like a checklist, split them.
- Write short, casual, warm. One sentence. No jargon.
- Think about what the patient's answer will naturally contain:
    "Who's your emergency contact?" → patient will say name, relationship, number
    "What insurance are you on?"    → patient will say provider; follow with member ID
- Cover ALL remaining fields — required and optional. Do not skip any field unless
  it was clearly answered in the opening statement.
- Never enumerate field names in the question text itself.

Bad:  "What is your emergency contact's name, relationship, and phone number?"
Good: "Who should we call if something comes up, and how do we reach them?"

Bad:  "Can you provide your insurance provider, policy ID, and policy holder name?"
Good: "What insurance are you on, and do you have your member ID handy?"

Return ONLY valid JSON, no markdown:
[
  {
    "question_id": "q1",
    "question": "...",
    "field_ids": ["field_a", "field_b"],
    "required": true
  }
]
""".strip()


# Fields that must never be collected over a phone call for security reasons.
_PHONE_BLOCKLIST = {
    "social_security_last_4", "ssn", "social_security", "social_security_number",
    "patient_signature", "signature",
}

def _group_into_questions(
    missing: list[MissingField],
    opening_context: str = "",
) -> list[CompoundQuestion]:
    """Group missing fields into compound conversational questions.
    Fields in _PHONE_BLOCKLIST are silently dropped — never asked over the phone.
    opening_context: patient's answer to the reason-for-visit question; used to
    skip fields whose answers were already volunteered.
    """
    askable = [f for f in missing if f.field_id not in _PHONE_BLOCKLIST]
    if not askable:
        return []

    payload = [
        {"field_id": f.field_id, "label": f.label, "type": f.type, "required": f.required}
        for f in askable
    ]
    user_msg = json.dumps(payload, indent=2)
    if opening_context:
        user_msg = (
            f"Patient's opening statement: \"{opening_context}\"\n\n"
            f"Fields still needed:\n{user_msg}"
        )

    raw = _chat(_GROUP_SYSTEM, user_msg)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return [CompoundQuestion(**q) for q in json.loads(raw)]


# ── Adaptive question agent ───────────────────────────────────────────────────

_NEXT_Q_SYSTEM = """
You are conducting a pre-visit medical intake call on behalf of a clinic.
You are given:
  - A list of form fields that still need to be collected (not in the EHR).
  - The full conversation so far (opening + any questions already asked).

Your job: decide what to ask next, or declare the call done.

Rules:
- Read the conversation carefully. If a field was clearly answered — even
  incidentally — do not ask about it again.
- Ask ONE question at a time. It should sound like natural speech, not a form.
- You may cover 1–3 closely related fields in one question ONLY if a single
  spoken answer naturally contains all of them (e.g. name + relationship of an
  emergency contact). Never force unrelated things into one question.
- If all required fields are covered (answered or clearly not applicable),
  set done=true and leave question null.
- Never ask about SSN, signatures, or any sensitive identifier over the phone.

Return ONLY valid JSON, no markdown:
{
  "question": "<next question to ask, or null if done>",
  "field_ids": ["<field_ids this question targets>"],
  "done": false
}
""".strip()


def get_next_question(form_id: str, conversation: list[dict]) -> dict:
    """
    Adaptive turn-by-turn question agent.
    Given the full conversation so far, returns the single best next question,
    or signals done when all required fields are covered.
    conversation: list of {"role": "ai"|"patient", "content": "..."}
    """
    prefilled = _prefilled_forms.get(form_id)
    schema    = _form_schemas.get(form_id)
    if not prefilled or not schema:
        return {"question": None, "field_ids": [], "done": True}

    ehr_ids = {f.field_id for f in prefilled.filled_fields}
    remaining = [
        {"field_id": f.field_id, "label": f.label, "required": f.required}
        for f in schema.fields
        if f.field_id not in ehr_ids and f.field_id not in _PHONE_BLOCKLIST
    ]
    if not remaining:
        return {"question": None, "field_ids": [], "done": True}

    conv_text = "\n".join(
        f"{'Assistant' if t['role'] == 'ai' else 'Patient'}: {t['content']}"
        for t in conversation
    )

    user_msg = (
        f"Fields still needed:\n{json.dumps(remaining, indent=2)}\n\n"
        f"Conversation so far:\n{conv_text}"
    )

    raw = _chat(_NEXT_Q_SYSTEM, user_msg)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(raw)


# ── Agent 3: Form filler ──────────────────────────────────────────────────────

_FILL_SYSTEM = """
You are a medical data entry assistant. You receive compound call responses — each
response is one spoken answer that may cover multiple form fields.

For each response, extract a value for every field it covers.

Rules:
- date: ISO 8601 (YYYY-MM-DD)
- phone: E.164 (+1XXXXXXXXXX) for US numbers
- boolean: true or false
- string/email/number: clean up, keep value as-is
- If a field's value cannot be extracted from the answer, set "needs_review": true
  and use null as the value.

Return ONLY valid JSON — a flat array covering every field across all responses:
[ { "field_id": "...", "value": <parsed>, "needs_review": false } ]
""".strip()


def fill_form(prefilled: PrefilledForm, responses: CallResponses) -> CompletedForm:
    """
    Agent 3 — unpack compound spoken answers into individual field values.
    Merges EHR-filled fields with patient-provided answers.
    """
    question_map = {q.question_id: q for q in prefilled.questions}
    field_map = {f.field_id: f for f in prefilled.missing_fields}

    # Build prompt: each entry pairs a spoken answer with the fields it should fill
    pairs = []
    for r in responses.responses:
        question = question_map.get(r.question_id)
        if not question:
            continue
        fields_for_q = [
            {"field_id": fid, "label": field_map[fid].label, "type": field_map[fid].type}
            for fid in question.field_ids
            if fid in field_map
        ]
        pairs.append({"question_id": r.question_id, "raw_answer": r.raw_answer, "fields": fields_for_q})

    raw = _chat(_FILL_SYSTEM, json.dumps(pairs, indent=2))
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    parsed_answers = {item["field_id"]: item for item in json.loads(raw)}

    all_fields = []
    for f in prefilled.filled_fields:
        all_fields.append(CompletedFormField(
            field_id=f.field_id,
            value=f.value,
            source="ehr",
            needs_review=f.needs_review,
        ))
    for field_id, answer in parsed_answers.items():
        all_fields.append(CompletedFormField(
            field_id=field_id,
            value=answer.get("value"),
            source="patient_call",
            needs_review=answer.get("needs_review", False),
        ))

    completed = CompletedForm(
        form_id=prefilled.form_id,
        patient_id=prefilled.patient_id,
        fields=all_fields,
    )
    _completed_forms[prefilled.form_id] = completed
    return completed


# ── Clinical brief generator ──────────────────────────────────────────────────

_BRIEF_SYSTEM = """
You are a clinical intake summarizer. Given a completed patient intake form,
EHR background data, and the patient's stated reason for visit, produce a
concise pre-visit clinical brief for the clinician.

Return ONLY valid JSON, no markdown:
{
  "chief_complaint": "<one sentence>",
  "risk_level": "low" | "moderate" | "high" | "emergency",
  "recommended_routing": "<e.g. Cardiology, General Practice, Urgent Care>",
  "summary": "<2-3 sentence clinical narrative>",
  "notes": "<relevant EHR context — conditions, meds, history that relate to the complaint>"
}

Do NOT include diagnoses, treatment plans, or next steps — those are the clinician's job.

Risk level guide:
  emergency — chest pain + cardiac risk, stroke symptoms, respiratory failure
  high      — acute worsening chronic condition, severe pain, urgent workup needed
  moderate  — concerning but stable, follow-up warranted soon
  low       — routine, preventive, or administrative visit
""".strip()


def generate_clinical_brief(
    completed: CompletedForm,
    reason_for_visit: str,
    questions_payload: list[dict],
    answers_payload: list[dict],
) -> ClinicalBrief:
    """Generate a clinical brief from the completed form and call context."""
    ehr = fhir_service.get_all(completed.patient_id)
    field_values = {f.field_id: f.value for f in completed.fields}

    prompt = json.dumps({
        "reason_for_visit": reason_for_visit,
        "ehr_summary": {
            "conditions": [c["condition"] for c in ehr.get("conditions", [])],
            "medications": [f"{m['name']} {m['dosage']}" for m in ehr.get("medications", [])],
            "allergies":   [a["substance"] for a in ehr.get("allergies", [])],
        },
        "completed_form_fields": {
            fid: val for fid, val in field_values.items() if val is not None
        },
    }, indent=2)

    raw = _chat(_BRIEF_SYSTEM, prompt)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    data = json.loads(raw)

    # Use form schema labels for clean display; fall back to formatted field_id
    schema = _form_schemas.get(completed.form_id)
    label_lookup = {f.field_id: f.label for f in schema.fields} if schema else {}

    flagged_labels = [
        label_lookup.get(f.field_id, f.field_id.replace("_", " ").title())
        for f in completed.fields if f.needs_review
    ]
    extracted = [
        {
            "label": label_lookup.get(f.field_id, f.field_id.replace("_", " ").title()),
            "value": str(f.value),
            "source": f.source,
        }
        for f in completed.fields
        if f.value is not None
    ]

    # Build transcript from the call exchange
    transcript: list[TranscriptTurn] = []
    for i, (q, a) in enumerate(zip(questions_payload, answers_payload)):
        transcript.append(TranscriptTurn(
            id=f"ai-{i}",
            role="ai",
            content=q.get("question", ""),
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))
        transcript.append(TranscriptTurn(
            id=f"patient-{i}",
            role="patient",
            content=a.get("raw_answer", ""),
            timestamp=datetime.now(timezone.utc).isoformat(),
            source="voice",
        ))

    brief = ClinicalBrief(
        report_id=str(uuid.uuid4()),
        form_id=completed.form_id,
        patient_id=completed.patient_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        chief_complaint=data["chief_complaint"],
        risk_level=data["risk_level"],
        recommended_routing=data["recommended_routing"],
        summary=data["summary"],
        notes=data["notes"],
        missing_information=[f"Review needed: {lbl}" for lbl in flagged_labels],
        extracted_fields=extracted,
        transcript=transcript,
    )
    _clinical_briefs[completed.form_id] = brief
    return brief


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_intake_pipeline(ocr_text: str, patient_id: str) -> PrefilledForm:
    schema = parse_form(ocr_text)
    return retrieve_and_diff(schema, patient_id)


_SCAN_EXTRACT_SYSTEM = """
You are extracting structured patient intake values from OCR text captured from a paper form,
insurance card, or ID shown to a clinic camera.

You are given:
- OCR text from the camera capture
- the exact intake fields we care about

Rules:
- Only return values that are explicitly present in the OCR text.
- Keep values concise and human-readable.
- Dates must be YYYY-MM-DD when possible.
- If the OCR text suggests a value but you are not fully confident, still return it with a lower confidence.
- Never invent values.
- Do not return empty strings.

Return ONLY valid JSON:
[
  {
    "field_id": "phone",
    "value": "+15551234567",
    "confidence": 0.88
  }
]
""".strip()


def ocr_image_to_text(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """
    OCR an image captured from a camera using GPT-4o vision.
    """
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key is required for camera scanning.")

    image_b64 = base64.b64encode(image_bytes).decode()
    response = _client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "This is a photo of a patient intake form, ID, or insurance document. "
                            "Extract all visible text exactly as it appears. Output plain text only."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}", "detail": "high"},
                    },
                ],
            }
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def _local_scan_extract(form_schema: FormSchema, ocr_text: str) -> list[CheckInScannedField]:
    """
    Lightweight label-based fallback for common intake fields when LLM extraction is unavailable.
    """
    results: list[CheckInScannedField] = []
    lowered = ocr_text.lower()

    def capture_after(label: str) -> str | None:
        pattern = re.compile(rf"{re.escape(label.lower())}\s*[:\-]?\s*(.+)", re.IGNORECASE)
        for line in ocr_text.splitlines():
            match = pattern.search(line)
            if match:
                value = match.group(1).strip()
                if value:
                    return value
        return None

    aliases = {
        "full_name": ["full name", "name"],
        "date_of_birth": ["date of birth", "dob", "birth date"],
        "phone": ["phone", "phone number", "mobile"],
        "email": ["email", "email address"],
        "address": ["address", "home address"],
        "insurance_provider": ["insurance provider", "insurance company", "payor"],
        "insurance_id": ["member id", "policy number", "insurance id", "subscriber id"],
        "emergency_contact_name": ["emergency contact", "emergency contact name"],
        "emergency_contact_phone": ["emergency contact phone", "emergency phone"],
        "emergency_contact_relation": ["relationship", "relation to patient"],
        "reason_for_visit": ["reason for visit", "chief complaint", "visit reason"],
    }

    for field in form_schema.fields:
        for alias in aliases.get(field.field_id, []):
            value = capture_after(alias)
            if value:
                results.append(
                    CheckInScannedField(
                        field_id=field.field_id,
                        label=field.label,
                        value=value,
                        confidence=0.62,
                        field_type=field.type,
                        section=field.section,
                    )
                )
                break

    if not results and "insurance" in lowered:
        insurance_field = next((field for field in form_schema.fields if field.field_id == "insurance_provider"), None)
        if insurance_field:
            results.append(
                CheckInScannedField(
                    field_id=insurance_field.field_id,
                    label=insurance_field.label,
                    value="Insurance text detected - review needed",
                    confidence=0.35,
                    field_type=insurance_field.type,
                    section=insurance_field.section,
                )
            )

    return results


def extract_scanned_fields(form_schema: FormSchema, ocr_text: str) -> list[CheckInScannedField]:
    """
    Map OCR text from a camera capture back onto a known intake form schema.
    """
    if not settings.openai_api_key:
        return _local_scan_extract(form_schema, ocr_text)

    fields_payload = [
        {
            "field_id": field.field_id,
            "label": field.label,
            "type": field.type,
            "section": field.section,
        }
        for field in form_schema.fields
    ]

    prompt = (
        f"Known intake fields:\n{json.dumps(fields_payload, indent=2)}\n\n"
        f"OCR text:\n{ocr_text}"
    )

    raw = _chat(_SCAN_EXTRACT_SYSTEM, prompt)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        parsed = json.loads(raw)
    except Exception:
        return _local_scan_extract(form_schema, ocr_text)

    field_lookup = {field.field_id: field for field in form_schema.fields}
    results: list[CheckInScannedField] = []
    for item in parsed:
        field = field_lookup.get(item.get("field_id"))
        value = item.get("value")
        if not field or value in (None, ""):
            continue
        results.append(
            CheckInScannedField(
                field_id=field.field_id,
                label=field.label,
                value=value,
                confidence=float(item.get("confidence", 0.75)),
                field_type=field.type,
                section=field.section,
            )
        )

    return results or _local_scan_extract(form_schema, ocr_text)


def finalize_form(form_id: str, responses: CallResponses) -> CompletedForm:
    """
    Fill in a pre-diffed form with patient call responses.
    Also generates a clinical brief silently in the background.
    """
    prefilled = _prefilled_forms.get(form_id)
    if not prefilled:
        raise ValueError(f"No prefilled form found for form_id={form_id}")

    completed = fill_form(prefilled, responses)

    reason = responses.reason_for_visit or "Not provided"

    # Prepend the opening exchange so it appears first in the transcript
    opening_q = [
        {"question": "Hi, can I get your full name and date of birth to confirm I have the right person?"},
        {"question": "And what's the reason for your visit today?"},
    ]
    opening_a = [
        {"raw_answer": "Confirmed"},
        {"raw_answer": reason},
    ]
    q_map = {q.question_id: q.question for q in prefilled.questions}
    q_list = opening_q + [{"question": q_map.get(r.question_id, "")} for r in responses.responses]
    a_list = opening_a + [{"raw_answer": r.raw_answer} for r in responses.responses]
    generate_clinical_brief(completed, reason, q_list, a_list)

    return completed


# ── Accessors (for routes) ────────────────────────────────────────────────────

def get_call_questions(form_id: str, reason_for_visit: str = "") -> list[CompoundQuestion]:
    """Return call questions, optionally filtered by what the patient already said."""
    prefilled = _prefilled_forms.get(form_id)
    if not prefilled:
        return []
    if not reason_for_visit:
        return prefilled.questions
    # Re-run grouper with the opening context so redundant fields are dropped
    return _group_into_questions(prefilled.missing_fields, opening_context=reason_for_visit)


def get_form_schema(form_id: str) -> FormSchema | None:
    return _form_schemas.get(form_id)

def get_prefilled_form(form_id: str) -> PrefilledForm | None:
    return _prefilled_forms.get(form_id)

def get_completed_form(form_id: str) -> CompletedForm | None:
    return _completed_forms.get(form_id)

def get_clinical_brief(form_id: str) -> ClinicalBrief | None:
    return _clinical_briefs.get(form_id)
