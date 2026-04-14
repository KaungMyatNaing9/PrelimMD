# app/routes/voice.py
# HTTP routes for voice input/output processing.
# Owner: Voice teammate
#
# TODO: Voice - POST /transcribe → accept audio blob, return transcript text
# TODO: Voice - POST /synthesize → accept text, return audio stream (TTS)

from fastapi import APIRouter

router = APIRouter()


@router.post("/transcribe")
def transcribe_audio():
    # TODO: Voice - call voice_service.transcribe() with uploaded audio file
    return {"message": "placeholder — transcription not yet implemented"}


@router.post("/synthesize")
def synthesize_speech():
    # TODO: Voice - call voice_service.synthesize() with text payload
    return {"message": "placeholder — speech synthesis not yet implemented"}
