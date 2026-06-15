from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base
import datetime

class Fatura(Base):
    __tablename__ = "faturas"

    id = Column(Integer, primary_key=True, index=True)
    consulta_id = Column(Integer, unique=True, index=True)
    valor = Column(Float)
    status_pagamento = Column(String, default="ABERTO") # ABERTO, PAGO
    data_emissao = Column(DateTime, default=datetime.datetime.utcnow)
