import os
import httpx
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List

import models, schemas
from database import engine, Base, get_db

from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MS-Agendamentos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MS_CADASTROS_URL = os.getenv("MS_CADASTROS_URL", "http://ms-cadastros:8000")
MS_FATURAMENTO_URL = os.getenv("MS_FATURAMENTO_URL", "http://ms-faturamento:8000")

def check_admin(x_role: str = Header(default="paciente")):
    if x_role != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas administradores.")
    return x_role

def verificar_escala_e_conflito(medico_id: int, data_hora: datetime, db: Session, consulta_id_excluir: int = None):
    # 1. Validar Médico e Horário
    try:
        resp_medico = httpx.get(f"{MS_CADASTROS_URL}/interna/validar-medico/{medico_id}", timeout=5.0)
        if resp_medico.status_code != 200:
            raise HTTPException(status_code=400, detail="Médico inválido ou não encontrado.")
        
        medico_data = resp_medico.json()
        
        # Validar dia da semana
        dias_map = {0: "SEG", 1: "TER", 2: "QUA", 3: "QUI", 4: "SEX", 5: "SAB", 6: "DOM"}
        dia_semana_consulta = dias_map[data_hora.weekday()]
        dias_trabalho_medico = [d.strip().upper() for d in medico_data.get("dias_trabalho", "").split(",")]
        
        if dia_semana_consulta not in dias_trabalho_medico:
            raise HTTPException(
                status_code=400, 
                detail=f"O médico não trabalha neste dia da semana ({dia_semana_consulta}). Dias de trabalho: {medico_data.get('dias_trabalho')}"
            )
            
        # Validar horário
        from datetime import time
        
        def parse_time(t_str):
            if not t_str:
                return None
            parts = t_str.split(":")
            return time(int(parts[0]), int(parts[1]))
            
        t_inicio = parse_time(medico_data.get("horario_inicio"))
        t_fim = parse_time(medico_data.get("horario_fim"))
        t_consulta = data_hora.time()
        
        if t_inicio and t_consulta < t_inicio:
            raise HTTPException(status_code=400, detail=f"O horário solicitado ({t_consulta}) é antes do início do expediente do médico ({t_inicio}).")
        if t_fim and t_consulta > t_fim:
            raise HTTPException(status_code=400, detail=f"O horário solicitado ({t_consulta}) é depois do fim do expediente do médico ({t_fim}).")
            
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Serviço de Cadastros indisponível.")

    # Verifica conflito de horário no agendamento
    query = db.query(models.Consulta).filter(
        models.Consulta.medico_id == medico_id,
        models.Consulta.data_hora == data_hora,
        models.Consulta.status.in_(["PENDENTE", "CONFIRMADA", "AGUARDANDO_CANCELAMENTO"])
    )
    if consulta_id_excluir:
        query = query.filter(models.Consulta.id != consulta_id_excluir)
        
    conflito = query.first()
    if conflito:
        raise HTTPException(status_code=400, detail="Médico já possui consulta neste horário.")

@app.post("/consultas", response_model=schemas.Consulta)
def create_consulta(consulta: schemas.ConsultaCreate, db: Session = Depends(get_db)):
    # 1. Validar Paciente
    try:
        resp_paciente = httpx.get(f"{MS_CADASTROS_URL}/interna/validar-paciente/{consulta.paciente_id}", timeout=5.0)
        if resp_paciente.status_code != 200:
            raise HTTPException(status_code=400, detail="Paciente inválido ou não encontrado.")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Serviço de Cadastros indisponível.")

    # 2. Validar escala e conflito
    verificar_escala_e_conflito(consulta.medico_id, consulta.data_hora, db)

    db_consulta = models.Consulta(**consulta.model_dump())
    db.add(db_consulta)
    db.commit()
    db.refresh(db_consulta)
    return db_consulta

@app.get("/consultas", response_model=List[schemas.Consulta])
def list_consultas(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Consulta).offset(skip).limit(limit).all()

@app.post("/consultas/{consulta_id}/solicitar-cancelamento")
def solicitar_cancelamento(consulta_id: int, db: Session = Depends(get_db)):
    consulta = db.query(models.Consulta).filter(models.Consulta.id == consulta_id).first()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    
    consulta.status = "AGUARDANDO_CANCELAMENTO"
    db.commit()
    return {"message": "Solicitação de cancelamento enviada. Aguardando aprovação do administrador."}

@app.post("/consultas/{consulta_id}/aprovar-cancelamento", dependencies=[Depends(check_admin)])
def aprovar_cancelamento(consulta_id: int, db: Session = Depends(get_db)):
    consulta = db.query(models.Consulta).filter(models.Consulta.id == consulta_id).first()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    
    consulta.status = "CANCELADA"
    db.commit()
    return {"message": "Cancelamento aprovado pelo administrador."}

@app.post("/consultas/{consulta_id}/reprovar-cancelamento", dependencies=[Depends(check_admin)])
def reprovar_cancelamento(consulta_id: int, db: Session = Depends(get_db)):
    consulta = db.query(models.Consulta).filter(models.Consulta.id == consulta_id).first()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    
    consulta.status = "CONFIRMADA"
    db.commit()
    return {"message": "Cancelamento rejeitado. Consulta mantida."}

@app.put("/consultas/{consulta_id}/remarcar")
def remarcar_consulta(consulta_id: int, payload: schemas.RemarcarConsulta, db: Session = Depends(get_db)):
    consulta = db.query(models.Consulta).filter(models.Consulta.id == consulta_id).first()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
    if consulta.status in ["CONCLUIDA", "CANCELADA"]:
        raise HTTPException(status_code=400, detail="Não é possível remarcar uma consulta concluída ou cancelada.")

    # Validar nova escala e conflito (excluindo a própria consulta do conflito de horário)
    verificar_escala_e_conflito(consulta.medico_id, payload.data_hora, db, consulta_id_excluir=consulta_id)
    
    consulta.data_hora = payload.data_hora
    consulta.status = "CONFIRMADA"
    db.commit()
    return {"message": "Consulta remarcada com sucesso.", "nova_data": consulta.data_hora}

@app.post("/consultas/{consulta_id}/confirmar", dependencies=[Depends(check_admin)])
def confirmar_consulta(consulta_id: int, db: Session = Depends(get_db)):
    consulta = db.query(models.Consulta).filter(models.Consulta.id == consulta_id).first()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    if consulta.status != "PENDENTE":
        raise HTTPException(status_code=400, detail="Apenas consultas PENDENTES podem ser confirmadas.")
    consulta.status = "CONFIRMADA"
    db.commit()
    return {"message": "Consulta confirmada com sucesso."}

@app.post("/consultas/{consulta_id}/concluir")
def concluir_consulta(consulta_id: int, payload: schemas.ConcluirConsulta, db: Session = Depends(get_db)):
    consulta = db.query(models.Consulta).filter(models.Consulta.id == consulta_id).first()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    
    consulta.status = "CONCLUIDA"
    db.commit()

    # Tenta faturar via MS-Faturamento
    fatura_payload = {
        "consulta_id": consulta.id,
        "valor": payload.valor
    }
    faturamento_online = False
    try:
        resp = httpx.post(f"{MS_FATURAMENTO_URL}/faturas", json=fatura_payload, timeout=3.0)
        if resp.status_code in [200, 201]:
            faturamento_online = True
    except httpx.RequestError:
        pass # Falha na comunicação
    
    # Tolerância a falhas: Outbox Pattern
    if not faturamento_online:
        pendencia = models.FaturamentoPendente(consulta_id=consulta.id, valor=payload.valor)
        db.add(pendencia)
        db.commit()
        return {"message": "Consulta concluída. Faturamento offline, salvo em pendências para sincronização futura."}

    return {"message": "Consulta concluída e faturada com sucesso."}

# --- Rotas Internas para Reconciliação (Consumidas pelo MS-Faturamento) ---
@app.get("/interna/pendencias-faturamento", response_model=List[schemas.FaturamentoPendente])
def get_pendencias(db: Session = Depends(get_db)):
    return db.query(models.FaturamentoPendente).filter(models.FaturamentoPendente.status_sincronizacao == "PENDENTE").all()

@app.post("/interna/pendencias-faturamento/{pendencia_id}/confirmar")
def confirmar_pendencia(pendencia_id: int, db: Session = Depends(get_db)):
    pendencia = db.query(models.FaturamentoPendente).filter(models.FaturamentoPendente.id == pendencia_id).first()
    if not pendencia:
        raise HTTPException(status_code=404, detail="Pendência não encontrada")
    
    pendencia.status_sincronizacao = "PROCESSADO"
    db.commit()
    return {"message": "Pendência confirmada."}
