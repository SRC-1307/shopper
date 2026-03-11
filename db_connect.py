from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

USER = "root"
PASSWORD = "password"
HOST = "127.0.0.1"
PORT = 3306
DB_NAME = "shopper-DB"

DB_URL = f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB_NAME}"

db_engine = create_engine(DB_URL)

db_connection = db_engine.connect()

session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

declarative_base = declarative_base()

# Reference: https://www.youtube.com/watch?v=zzOwU41UjTM
