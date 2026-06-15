from sqlalchemy import Column, Integer, String, Time
from database import Base

class Paciente(Base):
    __tablename__ = "pacientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    cpf = Column(String, unique=True, index=True)
    email = Column(String)
    telefone = Column(String)

class Medico(Base):
    __tablename__ = "medicos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    crm = Column(String, unique=True, index=True)
    especialidade_id = Column(Integer)
    dias_trabalho = Column(String) # ex: "SEG,QUA,SEX"
    horario_inicio = Column(Time)
    horario_fim = Column(Time)

class Especialidade(Base):
    __tablename__ = "especialidades"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
