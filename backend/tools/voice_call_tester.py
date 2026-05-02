from __future__ import annotations

from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import requests
import streamlit as st


DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_CALL_SID = "TEST_CALL_001"
DEFAULT_FROM = "+15550001111"
DEFAULT_TO = "+15550002222"
PRESET_RESPONSES = {
    "No Speech": "",
    "Unclear Answer": "maybe kind of",
    "Refusal": "I do not want to answer",
    "Concerning Symptom": "I have trouble breathing and severe pain",
}


def main() -> None:
    st.set_page_config(page_title="PrelimMD Voice Call Tester", layout="wide")
    _init_state()

    st.title("PrelimMD Voice Call Tester")
    st.caption("Local developer dashboard for simulating Twilio-style voice calls against the FastAPI backend.")

    with st.sidebar:
        st.subheader("Call Setup")
        call_type = st.radio("Call type", ["intake", "followup"], key="call_type")
        backend_base_url = st.text_input("Backend base URL", value=st.session_state.backend_base_url, key="backend_base_url")
        call_sid = st.text_input("Fake Twilio CallSid", value=st.session_state.call_sid, key="call_sid")
        from_phone = st.text_input("From", value=st.session_state.from_phone, key="from_phone")
        to_phone = st.text_input("To", value=st.session_state.to_phone, key="to_phone")

        st.markdown("---")
        if call_type == "intake":
            st.text_input("Visit ID", value=st.session_state.visit_id, key="visit_id")
            st.text_input("Optional session_id", value=st.session_state.session_id, key="session_id")
        else:
            st.text_input("Follow-up ID / task_id", value=st.session_state.followup_id, key="followup_id")
            st.text_input("Optional session_id", value=st.session_state.session_id, key="session_id")

        st.markdown("---")
        st.text_input(
            "Inspect session_id",
            value=st.session_state.inspect_session_id,
            key="inspect_session_id",
            help="Optional. If known, the tester can fetch GET /interview/session/{session_id}.",
        )
        confidence = st.number_input("Confidence", min_value=0.0, max_value=1.0, value=st.session_state.confidence, step=0.05, key="confidence")

        start_col, reset_col = st.columns(2)
        with start_col:
            if st.button("Start Call", use_container_width=True):
                start_call()
        with reset_col:
            if st.button("Reset Session", use_container_width=True):
                reset_session()
                st.rerun()

    top_left, top_right = st.columns([1.2, 1])

    with top_left:
        st.subheader("Conversation")
        for entry in st.session_state.history:
            with st.container(border=True):
                st.markdown(f"**{entry['role']}**")
                if entry.get("message"):
                    st.write(entry["message"])
                if entry.get("audio_url"):
                    st.caption(f"Audio URL: {entry['audio_url']}")
                    st.audio(entry["audio_url"])
                if entry.get("action"):
                    st.caption(f"Next action: `{entry['action']}`")
                if entry.get("redirect"):
                    st.caption(f"Redirect: `{entry['redirect']}`")
                if entry.get("hangup"):
                    st.caption("Hangup detected")
                if entry.get("error"):
                    st.error(entry["error"])
                if entry.get("twiml"):
                    with st.expander("Raw TwiML", expanded=False):
                        st.code(entry["twiml"], language="xml")

        st.text_area(
            "Patient response",
            value=st.session_state.pending_response,
            key="pending_response",
            height=100,
            placeholder="Type the simulated SpeechResult here...",
        )

        send_col, ns_col, unclear_col = st.columns(3)
        with send_col:
            if st.button("Send Response", use_container_width=True):
                send_response(st.session_state.pending_response)
        with ns_col:
            if st.button("Test No Speech", use_container_width=True):
                send_response(PRESET_RESPONSES["No Speech"])
        with unclear_col:
            if st.button("Test Unclear Answer", use_container_width=True):
                send_response(PRESET_RESPONSES["Unclear Answer"])

        refusal_col, concern_col = st.columns(2)
        with refusal_col:
            if st.button("Test Refusal", use_container_width=True):
                send_response(PRESET_RESPONSES["Refusal"])
        with concern_col:
            if st.button("Test Concerning Symptom", use_container_width=True):
                send_response(PRESET_RESPONSES["Concerning Symptom"])

    with top_right:
        st.subheader("Current Request State")
        st.json(
            {
                "backend_base_url": st.session_state.backend_base_url,
                "call_type": st.session_state.call_type,
                "call_sid": st.session_state.call_sid,
                "current_action_url": st.session_state.current_action_url,
                "inspect_session_id": st.session_state.inspect_session_id,
            }
        )

        st.subheader("Latest Parsed TwiML")
        st.json(st.session_state.last_parsed or {})

        st.subheader("Session Inspection")
        inspect_col, clear_col = st.columns(2)
        with inspect_col:
            if st.button("Refresh Session State", use_container_width=True):
                inspect_session()
        with clear_col:
            if st.button("Clear Inspection", use_container_width=True):
                st.session_state.session_snapshot = None

        if st.session_state.session_snapshot is not None:
            st.json(st.session_state.session_snapshot)
        else:
            st.info("Enter a known `session_id` or `inspect_session_id` to fetch `/interview/session/{session_id}`.")


def _init_state() -> None:
    defaults = {
        "backend_base_url": DEFAULT_BACKEND_URL,
        "call_type": "intake",
        "call_sid": DEFAULT_CALL_SID,
        "from_phone": DEFAULT_FROM,
        "to_phone": DEFAULT_TO,
        "visit_id": "visit-001",
        "followup_id": "task-001",
        "session_id": "",
        "inspect_session_id": "",
        "confidence": 0.95,
        "history": [],
        "current_action_url": "",
        "last_parsed": {},
        "pending_response": "",
        "session_snapshot": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def start_call() -> None:
    call_type = st.session_state.call_type
    if call_type == "intake":
        path = "/voice/intake/start"
        params = {}
        if st.session_state.session_id.strip():
            params["session_id"] = st.session_state.session_id.strip()
        elif st.session_state.visit_id.strip():
            params["visit_id"] = st.session_state.visit_id.strip()
        else:
            st.error("Visit ID or session_id is required for intake.")
            return
    else:
        path = "/voice/followup/start"
        params = {}
        if st.session_state.session_id.strip():
            params["session_id"] = st.session_state.session_id.strip()
        elif st.session_state.followup_id.strip():
            params["followup_id"] = st.session_state.followup_id.strip()
        else:
            st.error("Follow-up ID/task_id or session_id is required for follow-up.")
            return

    payload = {
        "CallSid": st.session_state.call_sid.strip() or DEFAULT_CALL_SID,
        "From": st.session_state.from_phone.strip() or DEFAULT_FROM,
        "To": st.session_state.to_phone.strip() or DEFAULT_TO,
    }
    _post_and_record(path=path, params=params, data=payload, response_label="Agent")
    inspect_session()


def send_response(speech_result: str) -> None:
    action_url = st.session_state.current_action_url
    if not action_url:
        st.error("Start a call first so the tester knows which answer endpoint to call.")
        return

    patient_message = speech_result if speech_result else "[no speech]"
    st.session_state.history.append({"role": "Patient", "message": patient_message})

    payload = {
        "CallSid": st.session_state.call_sid.strip() or DEFAULT_CALL_SID,
        "SpeechResult": speech_result,
        "Confidence": str(st.session_state.confidence),
        "From": st.session_state.from_phone.strip() or DEFAULT_FROM,
        "To": st.session_state.to_phone.strip() or DEFAULT_TO,
    }
    _post_to_url_and_record(action_url=action_url, data=payload, response_label="Agent")
    inspect_session()


def inspect_session() -> None:
    session_id = (st.session_state.inspect_session_id or st.session_state.session_id).strip()
    if not session_id:
        return

    url = _normalize_url(f"/interview/session/{session_id}")
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        st.session_state.session_snapshot = response.json()
    except Exception as exc:
        st.session_state.session_snapshot = {"error": str(exc), "session_id": session_id}


def reset_session() -> None:
    st.session_state.history = []
    st.session_state.current_action_url = ""
    st.session_state.last_parsed = {}
    st.session_state.pending_response = ""
    st.session_state.session_snapshot = None


def _post_and_record(path: str, params: dict[str, str], data: dict[str, str], response_label: str) -> None:
    url = _normalize_url(path)
    try:
        response = requests.post(url, params=params, data=data, timeout=30)
        _record_backend_response(response=response, request_url=response.url, response_label=response_label)
    except Exception as exc:
        st.session_state.history.append({"role": response_label, "error": str(exc)})


def _post_to_url_and_record(action_url: str, data: dict[str, str], response_label: str) -> None:
    url = _normalize_action_url(action_url)
    try:
        response = requests.post(url, data=data, timeout=30)
        _record_backend_response(response=response, request_url=response.url, response_label=response_label)
    except Exception as exc:
        st.session_state.history.append({"role": response_label, "error": str(exc)})


def _record_backend_response(response: requests.Response, request_url: str, response_label: str) -> None:
    if response.status_code >= 400:
        entry = {
            "role": response_label,
            "error": f"HTTP {response.status_code}: {response.text}",
            "message": "Backend returned an error.",
        }
        st.session_state.history.append(entry)
        return

    twiml = response.text
    parsed = _parse_twiml(twiml, request_url)
    st.session_state.current_action_url = parsed.get("gather_action") or parsed.get("redirect") or ""
    st.session_state.last_parsed = parsed

    message_parts = []
    if parsed.get("say_text"):
        message_parts.append(parsed["say_text"])
    if parsed.get("play_url"):
        message_parts.append(f"[Play] {parsed['play_url']}")
    if not message_parts:
        message_parts.append("[No playable prompt found in TwiML]")

    entry = {
        "role": response_label,
        "message": " ".join(message_parts),
        "audio_url": parsed.get("play_url"),
        "action": parsed.get("gather_action"),
        "redirect": parsed.get("redirect"),
        "hangup": parsed.get("hangup", False),
        "twiml": twiml,
    }
    st.session_state.history.append(entry)


def _parse_twiml(xml_text: str, request_url: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "say_text": "",
        "play_url": "",
        "gather_action": "",
        "redirect": "",
        "hangup": False,
    }
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        parsed["parse_error"] = str(exc)
        return parsed

    say_texts: list[str] = []
    play_url = ""
    gather_action = ""
    redirect_url = ""
    hangup = False

    for element in root.iter():
        tag = element.tag.split("}", 1)[-1]
        text = (element.text or "").strip()
        if tag == "Say" and text:
            say_texts.append(text)
        elif tag == "Play" and text and not play_url:
            play_url = _normalize_action_url(text)
        elif tag == "Gather" and element.attrib.get("action") and not gather_action:
            gather_action = _normalize_action_url(element.attrib["action"], request_url=request_url)
        elif tag == "Redirect" and text and not redirect_url:
            redirect_url = _normalize_action_url(text, request_url=request_url)
        elif tag == "Hangup":
            hangup = True

    parsed["say_text"] = " ".join(say_texts)
    parsed["play_url"] = play_url
    parsed["gather_action"] = gather_action
    parsed["redirect"] = redirect_url
    parsed["hangup"] = hangup
    return parsed


def _normalize_url(path_or_url: str) -> str:
    base = st.session_state.backend_base_url.rstrip("/") + "/"
    return urljoin(base, path_or_url.lstrip("/"))


def _normalize_action_url(path_or_url: str, request_url: str | None = None) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    if request_url:
        return urljoin(request_url, path_or_url)
    return _normalize_url(path_or_url)


if __name__ == "__main__":
    main()
