import json
import uuid
from datetime import datetime, timezone

import anthropic

from app.config import settings

_sessions: dict[str, dict] = {}


def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


# ── Prompts ───────────────────────────────────────────────────────────────────

NURSE_SYSTEM_PROMPT = """You are Maya, a compassionate and experienced pre-visit triage nurse at a modern medical clinic. You are conducting a friendly pre-screening interview to gather the patient's information before their appointment with the doctor.

Your personality:
- Genuinely warm, empathetic, and caring — patients should feel truly heard and at ease
- Conversational and natural, never robotic or clinical
- Reassuring without being dismissive — acknowledge their concern before moving forward
- Professional but approachable, like a trusted healthcare friend

Your communication style:
- Keep each message to 2–4 sentences: one specific acknowledgment of what they just shared, then ONE focused question
- NEVER ask two questions in the same message
- Reference what the patient actually said — don't use generic phrases like "I understand" alone
- Use natural language: "That sounds really uncomfortable", "I hear you", "Thanks for sharing that with me"
- Avoid medical jargon; use plain conversational language

Interview — cover these topics in natural order:
1. Main reason for the visit today (chief complaint)
2. When symptoms started, and whether they are getting better, worse, or the same
3. Severity — ask them to rate discomfort 1–10 and describe it in their own words
4. Any other symptoms they're experiencing alongside the main one
5. Known medical conditions or relevant health history
6. Current medications (name and dose if they know it)
7. Known allergies — medications, food, or environmental
8. [After general info gathered] — ask 3–4 targeted follow-up questions relevant to what they've described

Knowing when to close: You may ONLY close the interview after you have covered ALL of these topics:
  ✓ Chief complaint  ✓ Timeline  ✓ Severity (1–10)  ✓ Associated symptoms  ✓ Medical history  ✓ Medications  ✓ Allergies  ✓ At least 3 department-specific follow-ups
This means the interview will always be at least 9–12 turns long. Do NOT close early.
When you are genuinely done, include [INTERVIEW_COMPLETE] at the very end of your message — this tag is hidden from the patient. Your closing message must:
- Thank them warmly and specifically reference something they shared
- Reassure them the doctor will have everything they need
- Tell them they'll hear from the scheduling team shortly
- End on a genuinely caring note

CRITICAL RULES — never break:
1. NEVER suggest a diagnosis or say "it sounds like X condition" or "you might have X"
2. NEVER say anything is "definitely" or "certainly" a specific condition
3. Always say: "The doctor will want to take a closer look at that" or "I'll make sure to note that for the physician"
4. If asked for a diagnosis: "That's exactly what the doctor will evaluate — my job is just to make sure they have the full picture before your visit"
5. Emergency close — ONLY for symptoms that are ACUTELY happening RIGHT NOW and are immediately life-threatening. Examples that qualify: "I have crushing chest pain right now and my arm is numb", "I cannot breathe at all", "I think I'm having a stroke right now", "I am bleeding severely right now". Examples that DO NOT qualify (continue the interview normally): "I've had chest tightness for 10 days when I climb stairs", "I've been short of breath lately", "I had chest pain last week". Symptoms that started days or weeks ago, or happen only with exertion, are NOT emergencies — they need a proper workup. For true acute emergencies only: respond with empathy then say "Based on what you're describing, please call 911 or go to the emergency room immediately — I am flagging this as urgent for our clinical team right now." then add [INTERVIEW_COMPLETE]"""

EXTRACTION_SYSTEM_PROMPT = """You are a clinical data extraction assistant. Extract structured intake information from a patient nurse interview.

Return ONLY valid JSON. Use null for fields not mentioned. Arrays can be empty [].

{
  "chief_complaint": "main reason for visit in patient's words, or null",
  "symptoms": ["array of symptoms mentioned"],
  "symptom_onset": "when symptoms started as patient described, or null",
  "severity_score": null or integer 1-10 if patient rated it,
  "is_worsening": null or true or false,
  "associated_symptoms": ["other symptoms alongside main complaint"],
  "existing_conditions": ["known medical conditions"],
  "medications": ["current medications, include dose if mentioned"],
  "allergies": ["known allergies — medication, food, environmental"],
  "red_flags": ["any urgent or concerning symptoms: chest pain, difficulty breathing, etc."]
}"""

CLASSIFICATION_PROMPT_TEMPLATE = """Based on the patient intake data below, suggest the most appropriate medical department and assess urgency.

Patient data:
{patient_data}

Respond with ONLY valid JSON — no explanation outside the JSON:
{{
  "suggested_department": "Most relevant department (e.g. General Medicine, Cardiology, Dermatology, Orthopedics, Neurology, Gastroenterology, Pulmonology, ENT, Urology, Gynecology)",
  "triage_level": "low or moderate or high or emergency",
  "routing_hint": "One sentence starting with 'Based on what you've shared, this may be most relevant to the...' — never a diagnosis, always speculative language"
}}"""

SUMMARY_SYSTEM_PROMPT = """You are a clinical documentation assistant. Write a concise, professional pre-visit intake summary for a physician to review before seeing their patient.

Structure your response exactly like this:

CHIEF COMPLAINT
[Patient's main reason for visit, in their own words]

SYMPTOM HISTORY
[Timeline, onset, progression, and severity with exact rating if provided]

ASSOCIATED SYMPTOMS
[Other symptoms reported alongside main complaint]

MEDICAL HISTORY
[Known conditions, relevant health background]

MEDICATIONS & ALLERGIES
[Current medications with doses if known; known allergies]

CLINICAL NOTES
[Key clinical observations the physician should be aware of — flag any red flags or urgent concerns clearly]

RECOMMENDED ASSESSMENT
[Which specialty may benefit this patient — use "may benefit from" language, never a diagnosis]

Guidelines:
- Include only what the patient actually said — no speculation
- Flag urgent concerns with [URGENT] prefix
- Keep to under 400 words
- Write for a physician reader — clinical but readable"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _empty_extracted_data() -> dict:
    return {
        "chief_complaint": None,
        "symptoms": [],
        "symptom_onset": None,
        "severity_score": None,
        "is_worsening": None,
        "associated_symptoms": [],
        "existing_conditions": [],
        "medications": [],
        "allergies": [],
        "red_flags": [],
    }


def _merge_extracted(existing: dict, new: dict) -> dict:
    merged = dict(existing)
    for key, value in new.items():
        if key not in merged:
            continue
        if value is None or value == "":
            continue
        if isinstance(value, list):
            if value:
                existing_list = merged.get(key) or []
                combined = list(existing_list)
                for item in value:
                    if item and item not in combined:
                        combined.append(item)
                merged[key] = combined
        else:
            merged[key] = value
    return merged


def _format_extracted_fields(data: dict) -> list[dict]:
    fields = []
    if data.get("chief_complaint"):
        fields.append({"label": "Chief Complaint", "value": data["chief_complaint"]})
    if data.get("symptom_onset"):
        fields.append({"label": "Symptom Timeline", "value": data["symptom_onset"]})
    if data.get("severity_score") is not None:
        score = data["severity_score"]
        label = "Mild" if score <= 3 else "Moderate" if score <= 6 else "Severe"
        fields.append({"label": "Severity", "value": f"{score}/10 — {label}"})
    if data.get("symptoms"):
        fields.append({"label": "Symptoms", "value": ", ".join(data["symptoms"])})
    if data.get("associated_symptoms"):
        fields.append({"label": "Associated Symptoms", "value": ", ".join(data["associated_symptoms"])})
    if data.get("existing_conditions"):
        fields.append({"label": "Medical History", "value": ", ".join(data["existing_conditions"])})
    if data.get("medications"):
        fields.append({"label": "Current Medications", "value": ", ".join(data["medications"])})
    if data.get("allergies"):
        fields.append({"label": "Allergies", "value": ", ".join(data["allergies"])})
    if data.get("red_flags"):
        fields.append({"label": "Clinical Flags", "value": ", ".join(data["red_flags"])})
    return fields


def _assess_triage_from_extracted(data: dict) -> str:
    all_text = " ".join([
        " ".join(data.get("red_flags", [])),
        " ".join(data.get("symptoms", [])),
        " ".join(data.get("associated_symptoms", [])),
        data.get("chief_complaint") or "",
    ]).lower()

    emergency_terms = [
        "chest pain", "can't breathe", "cannot breathe", "difficulty breathing",
        "shortness of breath", "stroke", "unconscious", "unresponsive",
        "severe bleeding", "heart attack", "passing out", "loss of consciousness",
    ]
    high_terms = [
        "high fever", "severe pain", "vomiting blood", "confusion", "dizzy and falling",
        "rapid worsening", "can barely walk", "severe headache",
    ]

    if any(t in all_text for t in emergency_terms):
        return "emergency"
    if any(t in all_text for t in high_terms):
        return "high"
    score = data.get("severity_score")
    if score and score >= 8:
        return "high"
    if score and score >= 5:
        return "moderate"
    if data.get("red_flags"):
        return "moderate"
    return "low"


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _build_dept_system_prompt(dept: str) -> str:
    return (
        NURSE_SYSTEM_PROMPT
        + f"\n\n[CLINICAL CONTEXT — do not share with patient: Based on the general intake, "
        f"this patient's symptoms may be most relevant to the {dept} team. "
        f"Transition naturally to asking 3–4 targeted follow-up questions relevant to this specialty. "
        f"Do NOT tell the patient which department. Ask the clinically relevant questions as a natural continuation of the conversation.]"
    )


# ── Extraction & Classification (Haiku — fast/cheap) ─────────────────────────

async def _run_extraction(client: anthropic.AsyncAnthropic, history: list[dict]) -> dict:
    conversation_text = "\n".join(
        f"{'Maya' if m['role'] == 'assistant' else 'Patient'}: {m['content']}"
        for m in history
    )
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Extract intake data:\n\n{conversation_text}"}],
        )
        return _parse_json_response(response.content[0].text)
    except Exception:
        return _empty_extracted_data()


async def _run_classification(client: anthropic.AsyncAnthropic, extracted: dict) -> dict:
    summary_lines = [
        f"Chief complaint: {extracted.get('chief_complaint') or 'Not specified'}",
        f"Symptoms: {', '.join(extracted.get('symptoms', []) or ['None mentioned'])}",
        f"Associated symptoms: {', '.join(extracted.get('associated_symptoms', []) or ['None'])}",
        f"Medical history: {', '.join(extracted.get('existing_conditions', []) or ['None'])}",
        f"Red flags: {', '.join(extracted.get('red_flags', []) or ['None'])}",
    ]
    prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(patient_data="\n".join(summary_lines))
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_json_response(response.content[0].text)
    except Exception:
        return {
            "suggested_department": "General Medicine",
            "triage_level": "low",
            "routing_hint": "Based on what you've shared, this may be most relevant to the General Medicine team for an initial assessment.",
        }


# ── Public API ────────────────────────────────────────────────────────────────

async def start_session(session_id: str) -> dict:
    client = _client()

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=250,
        system=NURSE_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                "[SYSTEM: The patient has just connected for their pre-visit intake. "
                "Introduce yourself as Maya, their pre-visit nurse. "
                "Let them know this brief chat will take about 5 minutes and helps the doctor "
                "prepare for their visit. Ask what brings them in today. "
                "Keep it warm, natural, and under 3 sentences.]"
            ),
        }],
    )

    opening = response.content[0].text

    _sessions[session_id] = {
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress",
        "conversation_history": [{"role": "assistant", "content": opening}],
        "extracted_data": _empty_extracted_data(),
        "suggested_department": None,
        "triage_level": "low",
        "routing_hint": "Starting your pre-visit intake...",
        "turn_count": 0,
        "dept_context_injected": False,
        "summary_text": None,
    }

    return {
        "session_id": session_id,
        "message": opening,
        "status": "in_progress",
        "progress": 0,
        "extracted_fields": [],
        "triage_level": "low",
        "routing_hint": "Starting your pre-visit intake...",
    }


async def process_response(session_id: str, patient_input: str) -> dict:
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    if session["status"] == "completed":
        return {
            "session_id": session_id,
            "message": "Your intake is complete — thank you so much for your time.",
            "status": "completed",
            "progress": 100,
            "extracted_fields": _format_extracted_fields(session["extracted_data"]),
            "triage_level": session["triage_level"],
            "routing_hint": session["routing_hint"],
        }

    client = _client()

    session["conversation_history"].append({"role": "user", "content": patient_input})
    session["turn_count"] += 1
    turn = session["turn_count"]

    # Run extraction on turns 1, 4, 7, 10, 13+ and always on final turn
    if turn == 1 or turn % 3 == 1:
        extracted = await _run_extraction(client, session["conversation_history"])
        session["extracted_data"] = _merge_extracted(session["extracted_data"], extracted)

    # Classify after turn 5 if we have a chief complaint and haven't classified yet
    if turn == 5 and session["suggested_department"] is None and session["extracted_data"].get("chief_complaint"):
        classification = await _run_classification(client, session["extracted_data"])
        session["suggested_department"] = classification.get("suggested_department", "General Medicine")
        session["triage_level"] = classification.get("triage_level", "low")
        session["routing_hint"] = classification.get("routing_hint", "")

    # Update triage level from symptoms in case red flags appeared
    session["triage_level"] = _assess_triage_from_extracted(session["extracted_data"])

    # Build system prompt — inject dept context once after classification
    if session.get("suggested_department") and not session.get("dept_context_injected"):
        system_prompt = _build_dept_system_prompt(session["suggested_department"])
        session["dept_context_injected"] = True
    else:
        system_prompt = NURSE_SYSTEM_PROMPT

    # Generate Maya's next message
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=system_prompt,
        messages=session["conversation_history"],
    )

    maya_message = response.content[0].text
    # Guards against premature completion:
    # 1. Minimum turn count — can't complete before turn 10
    # 2. Question guard — if Maya's message still has a "?", she's asking, not closing
    _MIN_TURNS_BEFORE_COMPLETE = 10
    has_completion_marker = "[INTERVIEW_COMPLETE]" in maya_message
    clean_message = maya_message.replace("[INTERVIEW_COMPLETE]", "").strip()
    still_asking = "?" in clean_message
    is_complete = has_completion_marker and turn >= _MIN_TURNS_BEFORE_COMPLETE and not still_asking

    # Force completion after 16 turns if model hasn't done it
    if turn >= 16 and not is_complete:
        is_complete = True
        closing = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system=NURSE_SYSTEM_PROMPT,
            messages=[
                *session["conversation_history"],
                {
                    "role": "user",
                    "content": "[SYSTEM: You have all the information needed. Generate a warm, personal closing message. Include [INTERVIEW_COMPLETE] at the end.]",
                },
            ],
        )
        clean_message = closing.content[0].text.replace("[INTERVIEW_COMPLETE]", "").strip()

    session["conversation_history"].append({"role": "assistant", "content": clean_message})

    if is_complete:
        session["status"] = "completed"

        # Final extraction pass over full conversation
        final_extracted = await _run_extraction(client, session["conversation_history"])
        session["extracted_data"] = _merge_extracted(session["extracted_data"], final_extracted)

        # Final classification if not done yet
        if not session["suggested_department"] and session["extracted_data"].get("chief_complaint"):
            classification = await _run_classification(client, session["extracted_data"])
            session["suggested_department"] = classification.get("suggested_department", "General Medicine")
            session["triage_level"] = classification.get("triage_level", "low")
            session["routing_hint"] = classification.get("routing_hint", "")

        # Generate clinical summary
        session["summary_text"] = await _generate_summary_text(client, session)
        progress = 100
    else:
        progress = min(int((turn / 13) * 90) + 5, 90)

    return {
        "session_id": session_id,
        "message": clean_message,
        "status": session["status"],
        "progress": progress,
        "extracted_fields": _format_extracted_fields(session["extracted_data"]),
        "triage_level": session["triage_level"],
        "routing_hint": session["routing_hint"],
    }


async def _generate_summary_text(client: anthropic.AsyncAnthropic, session: dict) -> str:
    conversation_text = "\n".join(
        f"{'Maya (nurse)' if m['role'] == 'assistant' else 'Patient'}: {m['content']}"
        for m in session["conversation_history"]
    )
    extracted = session["extracted_data"]
    prompt = (
        f"Generate a physician pre-visit summary from this nurse interview:\n\n"
        f"CONVERSATION:\n{conversation_text}\n\n"
        f"EXTRACTED DATA:\n{json.dumps(extracted, indent=2)}\n\n"
        f"Suggested department: {session.get('suggested_department', 'Not classified')}\n"
        f"Triage level: {session.get('triage_level', 'low')}"
    )
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception:
        return "Summary generation failed — see transcript for full patient interview."


async def get_summary(session_id: str) -> dict:
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    # If session is still in progress, generate summary from what we have
    if not session.get("summary_text"):
        client = _client()
        session["summary_text"] = await _generate_summary_text(client, session)

    extracted = session["extracted_data"]

    transcript = [
        {
            "id": f"turn-{i}",
            "role": "ai" if m["role"] == "assistant" else "patient",
            "content": m["content"],
            "timestamp": session["created_at"],
            "source": "system" if m["role"] == "assistant" else "voice",
        }
        for i, m in enumerate(session["conversation_history"])
    ]

    return {
        "session_id": session_id,
        "created_at": session["created_at"],
        "status": session["status"],
        "chief_complaint": extracted.get("chief_complaint") or "Not captured",
        "symptoms": extracted.get("symptoms", []),
        "symptom_onset": extracted.get("symptom_onset"),
        "severity_score": extracted.get("severity_score"),
        "is_worsening": extracted.get("is_worsening"),
        "existing_conditions": extracted.get("existing_conditions", []),
        "medications": extracted.get("medications", []),
        "allergies": extracted.get("allergies", []),
        "red_flags": extracted.get("red_flags", []),
        "suggested_department": session.get("suggested_department"),
        "triage_level": session.get("triage_level", "low"),
        "routing_hint": session.get("routing_hint", ""),
        "summary_text": session.get("summary_text", ""),
        "extracted_fields": _format_extracted_fields(extracted),
        "transcript": transcript,
    }
