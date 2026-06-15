from pydantic import BaseModel
from datetime import datetime

class FaturaBase(BaseModel):
    consulta_id: int
    valor: float

class FaturaCreate(FaturaBase):
    pass

class Fatura(FaturaBase):
    id: int
    status_pagamento: str
    data_emissao: datetime

    class Config:
        from_attributes = True
