# ── Standalone dev tool ───────────────────────────────────────────────────────
# This is a self-contained STT + TTS echo server used during development to
# test the Google Speech-to-Text and Text-to-Speech pipeline in isolation,
# without Dialogflow or the database. It is NOT part of the main application.
# Run independently with: uvicorn voice:app --reload
# ─────────────────────────────────────────────────────────────────────────────

import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from google.cloud import speech, texttospeech
from google.oauth2 import service_account

app = FastAPI(title="STT + TTS Echo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

GOOGLE_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def get_credentials() -> service_account.Credentials:
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        raise RuntimeError(
            "GOOGLE_APPLICATION_CREDENTIALS env var not set. "
            "Export the path to your service account JSON file."
        )
    return service_account.Credentials.from_service_account_file(
        creds_path, scopes=GOOGLE_SCOPES
    )


@app.post("/process-audio")
async def process_audio(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    creds = get_credentials()

    # --- Speech-to-Text ---
    stt_client = speech.SpeechClient(credentials=creds)
    recognition_audio = speech.RecognitionAudio(content=audio_bytes)
    stt_config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        sample_rate_hertz=48000,
        language_code="en-US",
    )
    stt_response = stt_client.recognize(config=stt_config, audio=recognition_audio)

    if not stt_response.results:
        raise HTTPException(status_code=422, detail="No speech detected")

    transcript = stt_response.results[0].alternatives[0].transcript

    # --- Text-to-Speech ---
    tts_client = texttospeech.TextToSpeechClient(credentials=creds)
    synthesis_input = texttospeech.SynthesisInput(text=transcript)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    tts_response = tts_client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    return Response(
        content=tts_response.audio_content,
        media_type="audio/mpeg",
        headers={"X-Transcript": transcript},
    )
