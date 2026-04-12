import os

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

USER     = os.environ.get("DB_USER", "root")
PASSWORD = os.environ.get("DB_PASSWORD", "password")
HOST     = os.environ.get("DB_HOST", "127.0.0.1")
PORT     = os.environ.get("DB_PORT", "3306")
DB_NAME  = os.environ.get("DB_NAME", "shopper-DB")
SOCKET   = os.environ.get("DB_SOCKET", "")

# Use socket if provided (Cloud Run), else TCP (local)
if SOCKET:
    DB_URL = f"mysql+pymysql://{USER}:{PASSWORD}@/{DB_NAME}?unix_socket={SOCKET}"
else:
    DB_URL = f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB_NAME}"

db_engine = create_engine(DB_URL)

session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

declarative_base = declarative_base()

# Reference: https://www.youtube.com/watch?v=zzOwU41UjTM
