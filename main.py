import os
import subprocess
from typing import Annotated

from fastapi import FastAPI, status, Depends, Form, UploadFile, File
from fastapi import Request
from fastapi.responses import JSONResponse, FileResponse
from google.cloud import dialogflow
from google.cloud import speech
from google.cloud import texttospeech
from pydantic import BaseModel
from sqlalchemy.orm import Session

import db_models
# import google_cloud_service
from chatbot import get_session_id_from_context, process_intent
from db_connect import db_engine, session_local

app = FastAPI()
db_models.declarative_base.metadata.create_all(bind=db_engine)


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


# https://youtu.be/zzOwU41UjTM?t=1040

db_dependancy = Annotated[Session, Depends(connect_to_db)]


@app.post("/order/", status_code=status.HTTP_201_CREATED)
async def create_order(order: OrderBaseModel, db: db_dependancy):
    db_user = db_models.Order(**order.model_dump())
    db.add(db_user)
    db.commit()


@app.get("/order/{id}", status_code=status.HTTP_201_CREATED)
async def create_order(order: OrderBaseModel, db: db_dependancy):
    db_user = db_models.Order(**order.model_dump())
    db.add(db_user)
    db.commit()


@app.post("/item/", status_code=status.HTTP_201_CREATED)
async def create_item(item: ItemBaseModel, db: db_dependancy):
    db_user = db_models.Item(**item.model_dump())
    db.add(db_user)
    db.commit()


@app.post("/")
async def df_request_handler(request: Request):
    print("RECEIVED")
    df_response = await request.json()
    response_intents = df_response['queryResult']['intent']['displayName']
    response_parameters = df_response['queryResult']['parameters']
    response_contexts = df_response['queryResult']['outputContexts']
    df_session_id = get_session_id_from_context(response_contexts[0]['name'])

    return JSONResponse(content={"fulfillmentText": process_intent(
        intent=response_intents,
        response_parameters=response_parameters,
        session_id=df_session_id)
    })

