# app/services/voice_service.py
# Voice processing — speech-to-text and text-to-speech.
# Owner: Voice teammate
#
# TODO: Voice - implement transcribe(): accept raw audio bytes, return transcript string
# TODO: Voice - implement synthesize(): accept text string, return audio bytes (MP3/WAV)
# TODO: Voice - choose provider (ElevenLabs, Deepgram, Whisper, etc.) and add SDK to requirements.txt


def transcribe(audio_bytes: bytes) -> str:
    """Convert speech audio to a transcript string."""
    # TODO: Voice - implement with chosen STT provider
    raise NotImplementedError


def synthesize(text: str) -> bytes:
    """Convert text to speech audio bytes."""
    # TODO: Voice - implement with chosen TTS provider
    raise NotImplementedError
