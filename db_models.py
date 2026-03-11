from datetime import datetime
from sqlalchemy import Column, Integer, String, Double, JSON, TIMESTAMP, Enum
from db_connect import declarative_base


class Item(declarative_base):
    __tablename__ = 'item'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    company = Column(String(50), nullable=False)
    price = Column(Double, nullable=False)

class Order(declarative_base):
    __tablename__ = 'order'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    items = Column(JSON, nullable=False)
    total_price = Column(Double, nullable=False)
    timestamp = Column('timestamp', TIMESTAMP(timezone=False), nullable=False, default=datetime.now())
    status = Column(Enum("ordered", "shipped", "delivered", "cancelled","On the way", name="status_enum"), default="ordered")

