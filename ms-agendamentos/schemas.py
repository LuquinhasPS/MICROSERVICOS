from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ConsultaBase(BaseModel):
    paciente_id: int
    medico_id: int
    data_hora: datetime

class ConsultaCreate(ConsultaBase):
    pass

class Consulta(ConsultaBase):
    id: int
    status: str

    class Config:
        from_attributes = True

class FaturamentoPendenteBase(BaseModel):
    consulta_id: int
    valor: float

class FaturamentoPendente(FaturamentoPendenteBase):
    id: int
    status_sincronizacao: str
    data_criacao: datetime

    class Config:
        from_attributes = True

class ConcluirConsulta(BaseModel):
    valor: float

class RemarcarConsulta(BaseModel):
    data_hora: datetime
