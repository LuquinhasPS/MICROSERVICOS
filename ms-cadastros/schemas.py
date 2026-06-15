from pydantic import BaseModel
from typing import Optional
from datetime import time

class PacienteBase(BaseModel):
    nome: str
    cpf: str
    email: str
    telefone: str

class PacienteCreate(PacienteBase):
    pass

class Paciente(PacienteBase):
    id: int

    class Config:
        from_attributes = True

class MedicoBase(BaseModel):
    nome: str
    crm: str
    especialidade_id: int
    dias_trabalho: str
    horario_inicio: time
    horario_fim: time

class MedicoCreate(MedicoBase):
    pass

class Medico(MedicoBase):
    id: int

    class Config:
        from_attributes = True

class EspecialidadeBase(BaseModel):
    nome: str

class EspecialidadeCreate(EspecialidadeBase):
    pass

class Especialidade(EspecialidadeBase):
    id: int

    class Config:
        from_attributes = True
