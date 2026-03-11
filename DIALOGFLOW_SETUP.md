## Dialogflow terminal chat (DetectIntent)

This backend repo includes a small CLI that lets you chat with **Dialogflow ES** from your terminal:

- Script: `cli_dialogflow_chat.py`
- Uses: Dialogflow **Sessions DetectIntent**

### Prerequisites (GCP)
- **Enable** the Dialogflow API for your GCP project.
- For **audio mode** (`--audio`), also enable: Cloud Speech-to-Text API, Cloud Text-to-Speech API.
- Create (or reuse) a **service account** that has Dialogflow permissions (commonly “Dialogflow API Client”).
- For audio mode, the service account also needs: "Speech-to-Text User", "Cloud Text-to-Speech User".
- Download the service account **JSON key** file.

### Local authentication (recommended)
Set these environment variables:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/Users/ram/Desktop/C/shopper/back-end/API/shopper-chat-test-c2ffcde98b9d.json"
export DIALOGFLOW_PROJECT_ID="shopper-chat-test"
export DIALOGFLOW_LANGUAGE_CODE="en-US"   # optional
```

### Run (interactive)

```bash
python cli_dialogflow_chat.py
```

### Run (single message)

```bash
python cli_dialogflow_chat.py --once "hi"
```

### Run (audio mode: speech-to-text → Dialogflow → text-to-speech)

```bash
python cli_dialogflow_chat.py --audio new_order.mp3 --output-audio response.mp3
```

Requires **Cloud Speech-to-Text API** and **Cloud Text-to-Speech API** to be enabled. The service account must have:
- **Speech-to-Text User** (or Cloud Speech Administrator) for transcription
- **Cloud Text-to-Speech User** for synthesis

Enable the APIs:

```bash
gcloud services enable speech.googleapis.com texttospeech.googleapis.com
```

Input: MP3 (e.g. `new_order.mp3`), `.wav`, or `.flac` (MP3 is converted to WAV before transcription). Output: MP3.

### Optional flags
- `--project-id`: overrides `DIALOGFLOW_PROJECT_ID`
- `--language-code`: overrides `DIALOGFLOW_LANGUAGE_CODE`
- `--session-id`: set a fixed session id (otherwise one UUID is generated per run)
- `--credentials-json`: sets `GOOGLE_APPLICATION_CREDENTIALS` for this run
- `--audio`: path to input audio file (triggers audio mode; see above)
- `--output-audio`: path for response audio (required when using `--audio`)

### Common errors
- **Missing `DIALOGFLOW_PROJECT_ID`**: set the env var or pass `--project-id`.
- **Credentials errors**: confirm `GOOGLE_APPLICATION_CREDENTIALS` points to a valid JSON key file and the service account has Dialogflow access.
- **Audio mode**: for `--audio`, ensure Speech-to-Text and Text-to-Speech APIs are enabled and the service account has the required IAM roles (see above).

