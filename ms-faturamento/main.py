import os
import httpx
import asyncio
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models, schemas
from database import engine, Base, get_db, SessionLocal

from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MS-Faturamento")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MS_AGENDAMENTOS_URL = os.getenv("MS_AGENDAMENTOS_URL", "http://ms-agendamentos:8000")

@app.post("/faturas", response_model=schemas.Fatura, status_code=201)
def create_fatura(fatura: schemas.FaturaCreate, db: Session = Depends(get_db)):
    # Evitar duplicidade
    existente = db.query(models.Fatura).filter(models.Fatura.consulta_id == fatura.consulta_id).first()
    if existente:
        return existente

    db_fatura = models.Fatura(**fatura.model_dump())
    db.add(db_fatura)
    db.commit()
    db.refresh(db_fatura)
    return db_fatura

@app.get("/faturas", response_model=List[schemas.Fatura])
def list_faturas(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Fatura).offset(skip).limit(limit).all()

@app.post("/faturas/{fatura_id}/pagar")
def pagar_fatura(fatura_id: int, db: Session = Depends(get_db)):
    fatura = db.query(models.Fatura).filter(models.Fatura.id == fatura_id).first()
    if not fatura:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")
    
    fatura.status_pagamento = "PAGO"
    db.commit()
    return {"message": "Fatura paga com sucesso"}

@app.post("/interna/sincronizar")
def sincronizar_pendencias():
    """Endpoint manual para forçar a sincronização de faturamentos pendentes."""
    try:
        resp = httpx.get(f"{MS_AGENDAMENTOS_URL}/interna/pendencias-faturamento", timeout=5.0)
        if resp.status_code != 200:
            return {"status": "Erro ao consultar MS-Agendamentos"}
        
        pendencias = resp.json()
        db = SessionLocal()
        sucessos = 0
        for pendencia in pendencias:
            # Verifica se já existe
            existente = db.query(models.Fatura).filter(models.Fatura.consulta_id == pendencia["consulta_id"]).first()
            if not existente:
                nova_fatura = models.Fatura(consulta_id=pendencia["consulta_id"], valor=pendencia["valor"])
                db.add(nova_fatura)
                db.commit()
            
            # Avisa MS-Agendamentos para dar baixa
            ack_resp = httpx.post(f"{MS_AGENDAMENTOS_URL}/interna/pendencias-faturamento/{pendencia['id']}/confirmar")
            if ack_resp.status_code == 200:
                sucessos += 1
        
        db.close()
        return {"status": f"Sincronização concluída. {sucessos} pendências processadas."}
    except Exception as e:
        return {"status": f"Erro na sincronização: {str(e)}"}

# Para um ambiente de produção real, usaríamos um agendador como APScheduler ou Celery
# Aqui, usamos um loop assíncrono simples na inicialização do FastAPI
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(sync_worker())

async def sync_worker():
    while True:
        await asyncio.to_thread(sincronizar_pendencias)
        await asyncio.sleep(60) # Tenta sincronizar a cada 60 segundos
