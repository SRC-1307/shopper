import asyncio
import os
import uuid
from typing import Annotated

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, status, Depends, File, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from google.cloud import dialogflow, speech, texttospeech
from google.oauth2 import service_account
from pydantic import BaseModel
from sqlalchemy.orm import Session

import db_models
from chatbot import get_session_id_from_context, process_intent
from db_connect import db_engine, session_local

app = FastAPI(title="Shopper API")
db_models.declarative_base.metadata.create_all(bind=db_engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Transcript", "X-Bot-Response", "X-Session-Id"],
)

GOOGLE_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
DIALOGFLOW_PROJECT_ID = os.environ.get("DIALOGFLOW_PROJECT_ID")


# ── Google credentials ────────────────────────────────────────────────────────

def get_credentials():
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path:
        # Local development — use JSON key file
        return service_account.Credentials.from_service_account_file(
            creds_path, scopes=GOOGLE_SCOPES
        )
    else:
        # Cloud Run — use attached service account automatically
        import google.auth
        creds, _ = google.auth.default(scopes=GOOGLE_SCOPES)
        return creds


# ── DB dependency ─────────────────────────────────────────────────────────────

class ItemBaseModel(BaseModel):
    name: str
    company: str
    price: float


class OrderBaseModel(BaseModel):
    id: int
    items: str
    total_price: float
    status: str


def connect_to_db():
    db_connection = session_local()
    try:
        yield db_connection
    finally:
        db_connection.close()


db_dependency = Annotated[Session, Depends(connect_to_db)]


# ── CRUD endpoints ────────────────────────────────────────────────────────────

@app.post("/order/", status_code=status.HTTP_201_CREATED)
async def create_order(order: OrderBaseModel, db: db_dependency):
    db_order = db_models.Order(**order.model_dump())
    db.add(db_order)
    db.commit()


@app.get("/order/{id}")
async def get_order(id: int, db: db_dependency):
    order = db.query(db_models.Order).filter(db_models.Order.id == id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/item/", status_code=status.HTTP_201_CREATED)
async def create_item(item: ItemBaseModel, db: db_dependency):
    db_item = db_models.Item(**item.model_dump())
    db.add(db_item)
    db.commit()


# ── Dialogflow fulfillment webhook ────────────────────────────────────────────

@app.post("/")
async def df_webhook_handler(request: Request):
    """Receives fulfillment webhooks sent by Dialogflow."""
    df_response = await request.json()
    response_intents = df_response['queryResult']['intent']['displayName']
    response_parameters = df_response['queryResult']['parameters']
    response_contexts = df_response['queryResult']['outputContexts']
    df_session_id = get_session_id_from_context(response_contexts[0]['name'])

    return JSONResponse(content={"fulfillmentText": process_intent(
        intent=response_intents,
        response_parameters=response_parameters,
        session_id=df_session_id,
    )})


# ── Voice endpoint: STT → Dialogflow → TTS ───────────────────────────────────

def _detect_intent(session_id: str, text: str, creds) -> str:
    """Send transcript to Dialogflow and return the fulfillment response text."""
    if not DIALOGFLOW_PROJECT_ID:
        raise RuntimeError("DIALOGFLOW_PROJECT_ID env var not set.")

    session_client = dialogflow.SessionsClient(credentials=creds)
    session_path = session_client.session_path(DIALOGFLOW_PROJECT_ID, session_id)

    text_input = dialogflow.TextInput(text=text, language_code="en-US")
    query_input = dialogflow.QueryInput(text=text_input)

    response = session_client.detect_intent(
        request={"session": session_path, "query_input": query_input}
    )
    return response.query_result.fulfillment_text


@app.post("/process-audio")
async def process_audio(
    audio: UploadFile = File(...),
    session_id: str = None,
):
    """
    Full voice pipeline:
      1. Speech-to-Text  — transcribe the uploaded audio
      2. Dialogflow      — detect intent and get bot reply
      3. Text-to-Speech  — synthesise bot reply to MP3

    Pass `session_id` as a query param to maintain conversation context across
    turns. A new UUID is generated automatically for the first request and
    returned in the `X-Session-Id` response header.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    if not session_id:
        session_id = str(uuid.uuid4())

    creds = get_credentials()
    loop = asyncio.get_event_loop()

    # 1. Speech-to-Text
    stt_client = speech.SpeechClient(credentials=creds)
    recognition_audio = speech.RecognitionAudio(content=audio_bytes)
    stt_config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        sample_rate_hertz=48000,
        language_code="en-US",
    )
    stt_response = await loop.run_in_executor(
        None, lambda: stt_client.recognize(config=stt_config, audio=recognition_audio)
    )

    if not stt_response.results:
        raise HTTPException(status_code=422, detail="No speech detected")

    transcript = stt_response.results[0].alternatives[0].transcript

    # 2. Dialogflow — detect intent
    bot_reply = await loop.run_in_executor(
        None, lambda: _detect_intent(session_id=session_id, text=transcript, creds=creds)
    )
    if not bot_reply:
        bot_reply = "I'm sorry, I didn't understand that. Please try again."

    # 3. Text-to-Speech
    tts_client = texttospeech.TextToSpeechClient(credentials=creds)
    synthesis_input = texttospeech.SynthesisInput(text=bot_reply)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    tts_response = await loop.run_in_executor(
        None, lambda: tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
    )

    return Response(
        content=tts_response.audio_content,
        media_type="audio/mpeg",
        headers={
            "X-Transcript": transcript.strip().replace("\n", " ").encode("ascii", errors="replace").decode("ascii"),
            "X-Bot-Response": bot_reply.strip().replace("\n", " ").encode("ascii", errors="replace").decode("ascii"),
            "X-Session-Id": session_id,
        },
    )
