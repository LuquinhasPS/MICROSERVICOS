from sqlalchemy import Column, Integer, String, DateTime, Float
from database import Base
import datetime

class Consulta(Base):
    __tablename__ = "consultas"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, index=True)
    medico_id = Column(Integer, index=True)
    data_hora = Column(DateTime)
    status = Column(String, default="PENDENTE") # PENDENTE, CONFIRMADA, CANCELADA, CONCLUIDA

class FaturamentoPendente(Base):
    __tablename__ = "faturamentos_pendentes"

    id = Column(Integer, primary_key=True, index=True)
    consulta_id = Column(Integer, unique=True, index=True)
    valor = Column(Float)
    status_sincronizacao = Column(String, default="PENDENTE") # PENDENTE, PROCESSADO
    data_criacao = Column(DateTime, default=datetime.datetime.utcnow)
