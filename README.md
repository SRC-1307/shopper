# Shopper Voice Chatbot

A voice-enabled grocery shopping chatbot powered by Google Cloud. Users can speak naturally to add items to their cart, choose brands, place orders, and track deliveries — all through a browser-based voice interface.

---

## Live Demo

**Frontend:** _(deploy your own — see GCP Deployment below)_
**Backend API Docs:** `https://YOUR_CLOUD_RUN_URL/docs`

---

## Architecture

```
User (Browser)
     │
     │ Voice (WebM audio)
     ▼
index.html (Cloud Storage)
     │
     │ POST /process-audio
     ▼
FastAPI Backend (Cloud Run)
     │
     ├── Google Speech-to-Text  →  transcript
     ├── Google Dialogflow      →  intent detection
     │        │
     │        └── POST / (fulfillment webhook)
     │                │
     │                └── chatbot.py (business logic)
     │                         │
     │                         └── Cloud SQL MySQL
     │                              ├── item  (products & prices)
     │                              └── order (placed orders)
     │
     └── Google Text-to-Speech  →  MP3 audio response
```

---

## Features

- Voice input via browser microphone
- Natural language understanding via Dialogflow
- Add grocery items to cart by speaking
- Choose brands for each item
- View cart contents and total price
- Place orders and get an order ID
- Track existing orders by order ID
- Remove items from cart

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript (MediaRecorder API) |
| Backend | FastAPI (Python) |
| NLP | Google Dialogflow |
| Speech to Text | Google Cloud Speech-to-Text |
| Text to Speech | Google Cloud Text-to-Speech |
| Database | MySQL (Cloud SQL on GCP) |
| Containerization | Docker |
| Hosting - Backend | Google Cloud Run |
| Hosting - Frontend | Google Cloud Storage |

---

## Project Structure

```
shopper-voice-chatbot/
│
├── main.py           # FastAPI app — API endpoints & full voice pipeline
├── chatbot.py        # Intent processing & cart business logic
├── db_connect.py     # DB connection (local TCP & Cloud SQL unix socket)
├── db_models.py      # SQLAlchemy ORM models (Item, Order)
├── voice.py          # Standalone STT/TTS prototype (dev only)
├── index.html        # Frontend — browser voice chat widget
│
├── Dockerfile        # Container config for Cloud Run deployment
├── .dockerignore     # Files excluded from Docker build
├── requirements.txt  # Python dependencies
├── .env.example      # Template for environment variables
└── .gitignore
```

---

## Dialogflow Intents

| Intent | What user says | What happens |
|---|---|---|
| `add.items` | "I want 2 milks and 1 bread" | Adds items to session cart |
| `order.brand` | "Kroger milk and great value bread" | Assigns brands & prices |
| `view.cart` | "What's in my cart?" | Returns cart contents & total |
| `place.the.order` | "Place my order" | Saves order to DB, returns order ID |
| `track.order` | "Track order 5" | Returns order status & price |
| `remove.from.cart` | "Remove milk" | Removes item from cart |

---

## Local Setup

### Prerequisites
- Python 3.11
- MySQL running locally
- GCP project with Dialogflow agent set up
- GCP service account JSON key file

### Steps

**1. Clone the repository**
```bash
git clone https://github.com/YOUR_USERNAME/shopper-voice-chatbot.git
cd shopper-voice-chatbot
```

**2. Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Set up environment variables**
```bash
cp .env.example .env
```
Fill in your values in `.env`:
```
GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
DIALOGFLOW_PROJECT_ID="your-gcp-project-id"
DB_USER=root
DB_PASSWORD=your-password
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=shopper-DB
```

**5. Create the database**
```sql
CREATE DATABASE `shopper-DB`;
```

**6. Run the backend**
```bash
uvicorn main:app --reload
```

**7. Set up Dialogflow webhook**
- Use [ngrok](https://ngrok.com/) to expose localhost:
```bash
ngrok http 8000
```
- Set the ngrok URL as your Dialogflow fulfillment webhook

**8. Open the frontend**
- Open `index.html` in your browser
- The frontend defaults to `http://localhost:8080`. To override, set `window.BACKEND_URL` before the script runs (e.g. inject it via a `<script>` tag in your deployment)

---

## GCP Deployment

### GCP Services Used

| Service | Purpose |
|---|---|
| Cloud Run | Hosts the FastAPI backend |
| Cloud SQL | Managed MySQL database |
| Artifact Registry | Stores Docker image |
| Cloud Build | Builds Docker image from source |
| Cloud Storage | Hosts the frontend HTML |
| Dialogflow | NLP and intent detection |
| Speech-to-Text API | Transcribes voice to text |
| Text-to-Speech API | Converts bot reply to audio |

---

### Deployment Steps

**1. Enable required APIs**
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com
```

**2. Create Artifact Registry**
```bash
gcloud artifacts repositories create shopper-repo \
  --repository-format=docker \
  --location=us-central1
```

**3. Create Cloud SQL instance**
```bash
gcloud sql instances create shopper-db \
  --database-version=MYSQL_8_0 \
  --tier=db-f1-micro \
  --region=us-central1

gcloud sql databases create shopper-DB --instance=shopper-db

gcloud sql users set-password root \
  --instance=shopper-db \
  --password=YOUR_PASSWORD
```

**4. Build and push Docker image**
```bash
gcloud builds submit --tag us-central1-docker.pkg.dev/YOUR_PROJECT_ID/shopper-repo/shopper-api
```

**5. Deploy to Cloud Run**
```bash
gcloud run deploy shopper-api \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/shopper-repo/shopper-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances YOUR_PROJECT_ID:us-central1:shopper-db \
  --service-account YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars "DIALOGFLOW_PROJECT_ID=YOUR_PROJECT_ID,DB_USER=root,DB_PASSWORD=YOUR_PASSWORD,DB_NAME=shopper-DB,DB_SOCKET=/cloudsql/YOUR_PROJECT_ID:us-central1:shopper-db"
```

**6. Deploy frontend to Cloud Storage**
```bash
gsutil mb -l us-central1 gs://YOUR_BUCKET_NAME
gsutil cp index.html gs://YOUR_BUCKET_NAME
gsutil iam ch allUsers:objectViewer gs://YOUR_BUCKET_NAME
gsutil web set -m index.html gs://YOUR_BUCKET_NAME
```

**7. Update Dialogflow webhook**
- Go to [Dialogflow Console](https://dialogflow.cloud.google.com)
- Select your agent → Fulfillment
- Set webhook URL to your Cloud Run URL:
```
https://YOUR_CLOUD_RUN_URL/
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/process-audio` | Full voice pipeline (STT → Dialogflow → TTS) |
| `POST` | `/` | Dialogflow fulfillment webhook |
| `POST` | `/item/` | Add a new grocery item |
| `POST` | `/order/` | Create an order |
| `GET` | `/order/{id}` | Get order by ID |

Full interactive API docs available at `/docs` when running locally.

---

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON key | Local only |
| `DIALOGFLOW_PROJECT_ID` | Your GCP project ID | Yes |
| `DB_USER` | Database username | Yes |
| `DB_PASSWORD` | Database password | Yes |
| `DB_HOST` | Database host (local) | Local only |
| `DB_PORT` | Database port (local) | Local only |
| `DB_NAME` | Database name | Yes |
| `DB_SOCKET` | Cloud SQL unix socket path | Cloud Run only |

---

## Database Schema

**item** table
| Column | Type | Description |
|---|---|---|
| id | INT | Auto increment primary key |
| name | VARCHAR(50) | Item name (e.g. Milk) |
| company | VARCHAR(50) | Brand name (e.g. Kroger) |
| price | DOUBLE | Price per unit |

**order** table
| Column | Type | Description |
|---|---|---|
| id | INT | Auto increment primary key |
| items | JSON | List of ordered items with details |
| total_price | DOUBLE | Total order price |
| timestamp | TIMESTAMP | Order creation time |
| status | ENUM | ordered / shipped / delivered / cancelled |
