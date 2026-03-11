import argparse
import io
import os
import sys
import uuid
from typing import Iterable, Optional


def _import_dialogflow():
    try:
        from google.cloud import dialogflow_v2 as dialogflow  # type: ignore

        return dialogflow
    except Exception:
        from google.cloud import dialogflow  # type: ignore

        return dialogflow


def _extract_response_text(query_result) -> str:
    fulfillment_text = getattr(query_result, "fulfillment_text", "") or ""
    if fulfillment_text.strip():
        return fulfillment_text.strip()

    messages = getattr(query_result, "fulfillment_messages", None)
    if not messages:
        return ""

    parts: list[str] = []
    for msg in messages:
        text_obj = getattr(msg, "text", None)
        if not text_obj:
            continue
        for t in getattr(text_obj, "text", []) or []:
            if t and str(t).strip():
                parts.append(str(t).strip())
    return "\n".join(parts).strip()


def _load_audio_for_stt(audio_path: str) -> tuple[bytes, str, int]:
    """Load audio bytes and return (content, encoding, sample_rate_hertz).
    Handles WAV, FLAC, and MP3 (converts via pydub to WAV).
    """
    ext = (os.path.splitext(audio_path)[1] or "").lower()
    with open(audio_path, "rb") as f:
        raw = f.read()

    if ext == ".mp3":
        try:
            from pydub import AudioSegment

            seg = AudioSegment.from_mp3(audio_path)
            seg = seg.set_frame_rate(16000).set_channels(1)
            buf = io.BytesIO()
            seg.export(buf, format="wav")
            buf.seek(0)
            content = buf.read()
            return content, "LINEAR16", 16000
        except Exception as ex:
            raise ValueError(f"Cannot convert MP3 to WAV: {ex}") from ex

    if ext == ".flac":
        return raw, "FLAC", 0  # sample_rate optional for FLAC
    if ext in (".wav", ".wave"):
        return raw, "LINEAR16", 16000
    raise ValueError(
        f"Unsupported audio format '{ext}'. Use .wav, .flac, or .mp3"
    )


def speech_to_text(audio_path: str, language_code: str) -> str:
    """Transcribe audio file to text using Google Cloud Speech-to-Text."""
    from google.cloud import speech

    content, encoding_name, sample_rate = _load_audio_for_stt(audio_path)

    client = speech.SpeechClient()
    encoding = getattr(
        speech.RecognitionConfig.AudioEncoding,
        encoding_name,
        speech.RecognitionConfig.AudioEncoding.LINEAR16,
    )
    config_kwargs: dict = {"encoding": encoding, "language_code": language_code}
    if sample_rate > 0:
        config_kwargs["sample_rate_hertz"] = sample_rate
    config = speech.RecognitionConfig(**config_kwargs)
    audio = speech.RecognitionAudio(content=content)

    response = client.recognize(config=config, audio=audio)
    transcript_parts: list[str] = []
    for result in response.results:
        alternative = result.alternatives[0] if result.alternatives else None
        if alternative and alternative.transcript:
            transcript_parts.append(alternative.transcript.strip())
    return " ".join(transcript_parts).strip()


def text_to_speech(text: str, output_path: str, language_code: str) -> None:
    """Synthesize text to audio file using Google Cloud Text-to-Speech."""
    if not text or not text.strip():
        return
    from google.cloud import texttospeech_v1

    client = texttospeech_v1.TextToSpeechClient()
    input_ = texttospeech_v1.SynthesisInput(text=text.strip())
    voice = texttospeech_v1.VoiceSelectionParams(
        language_code=language_code,
        ssml_gender=texttospeech_v1.SsmlVoiceGender.NEUTRAL,
    )
    audio_config = texttospeech_v1.AudioConfig(
        audio_encoding=texttospeech_v1.AudioEncoding.MP3,
    )
    response = client.synthesize_speech(
        request={
            "input": input_,
            "voice": voice,
            "audio_config": audio_config,
        }
    )
    with open(output_path, "wb") as f:
        f.write(response.audio_content)


def detect_intent_text(
    *,
    project_id: str,
    session_id: str,
    text: str,
    language_code: str,
) -> str:
    dialogflow = _import_dialogflow()
    session_client = dialogflow.SessionsClient()
    session = session_client.session_path(project_id, session_id)

    text_input = dialogflow.TextInput(text=text, language_code=language_code)
    query_input = dialogflow.QueryInput(text=text_input)

    response = session_client.detect_intent(
        request={"session": session, "query_input": query_input}
    )
    return _extract_response_text(response.query_result)


def _iter_user_lines() -> Iterable[str]:
    while True:
        try:
            line = input("> ")
        except EOFError:
            return
        except KeyboardInterrupt:
            print()
            return
        yield line


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Terminal chat client for Dialogflow ES (DetectIntent)."
    )
    parser.add_argument(
        "--project-id",
        default=os.environ.get("DIALOGFLOW_PROJECT_ID") or "",
        help="Dialogflow / GCP project id. Env: DIALOGFLOW_PROJECT_ID",
    )
    parser.add_argument(
        "--language-code",
        default=os.environ.get("DIALOGFLOW_LANGUAGE_CODE") or "en-US",
        help='Language code (default: "en-US"). Env: DIALOGFLOW_LANGUAGE_CODE',
    )
    parser.add_argument(
        "--session-id",
        default=os.environ.get("DIALOGFLOW_SESSION_ID") or "",
        help="Optional session id. Env: DIALOGFLOW_SESSION_ID. Default: random UUID per run.",
    )
    parser.add_argument(
        "--credentials-json",
        default="",
        help="Optional path to service account JSON key (sets GOOGLE_APPLICATION_CREDENTIALS).",
    )
    parser.add_argument(
        "--once",
        default="",
        help='Send one message and exit. Example: --once "hi"',
    )
    parser.add_argument(
        "--audio",
        default="",
        help="Path to input audio file (triggers audio mode). Supports .mp3, .wav, .flac (e.g. new_order.mp3)",
    )
    parser.add_argument(
        "--output-audio",
        default="",
        help="Path for response audio file (required when --audio is used). Output format: MP3",
    )

    args = parser.parse_args(argv)

    if args.credentials_json:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = args.credentials_json

    if not args.project_id:
        print(
            "Error: missing project id. Set DIALOGFLOW_PROJECT_ID or pass --project-id.",
            file=sys.stderr,
        )
        return 2

    session_id = args.session_id or str(uuid.uuid4())

    if args.audio:
        if not args.output_audio:
            print(
                "Error: --output-audio is required when using --audio.",
                file=sys.stderr,
            )
            return 2
        if not os.path.isfile(args.audio):
            print(f"Error: audio file not found: {args.audio}", file=sys.stderr)
            return 2
        try:
            user_text = speech_to_text(args.audio, args.language_code)
        except Exception as ex:
            print(f"Speech-to-Text error: {ex}", file=sys.stderr)
            return 1
        if not user_text or not user_text.strip():
            print("No speech detected in audio file.", file=sys.stderr)
            return 1
        try:
            reply = detect_intent_text(
                project_id=args.project_id,
                session_id=session_id,
                text=user_text,
                language_code=args.language_code,
            )
        except Exception as ex:
            print(f"Dialogflow error: {ex}", file=sys.stderr)
            return 1
        if reply and reply.strip():
            try:
                text_to_speech(reply, args.output_audio, args.language_code)
                print(f"You said: {user_text}")
                print(f"Reply: {reply}")
                print(f"Audio saved to: {args.output_audio}")
            except Exception as ex:
                print(f"Text-to-Speech error: {ex}", file=sys.stderr)
                return 1
        else:
            print(f"You said: {user_text}")
            print("Reply: (empty)")
            print("No reply to synthesize; no audio file written.")
        return 0

    if args.once:
        try:
            reply = detect_intent_text(
                project_id=args.project_id,
                session_id=session_id,
                text=args.once,
                language_code=args.language_code,
            )
        except Exception as ex:
            print(f"Dialogflow error: {ex}", file=sys.stderr)
            return 1
        print(reply or "")
        return 0

    print("Dialogflow terminal chat. Type 'exit' or 'quit' to stop.")
    print(f"(project_id={args.project_id}, session_id={session_id}, language={args.language_code})")

    for user_text in _iter_user_lines():
        user_text = (user_text or "").strip()
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            return 0

        try:
            reply = detect_intent_text(
                project_id=args.project_id,
                session_id=session_id,
                text=user_text,
                language_code=args.language_code,
            )
        except Exception as ex:
            print(f"Dialogflow error: {ex}", file=sys.stderr)
            continue

        if reply:
            print(reply)
        else:
            print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

