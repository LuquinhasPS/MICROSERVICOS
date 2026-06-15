from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List

import models, schemas
from database import engine, Base, get_db

from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MS-Cadastros")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def check_admin(x_role: str = Header(default="paciente")):
    if x_role != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas administradores.")
    return x_role

# --- Pacientes ---
@app.post("/pacientes", response_model=schemas.Paciente)
def create_paciente(paciente: schemas.PacienteCreate, db: Session = Depends(get_db)):
    db_paciente = models.Paciente(**paciente.model_dump())
    db.add(db_paciente)
    db.commit()
    db.refresh(db_paciente)
    return db_paciente

@app.get("/pacientes", response_model=List[schemas.Paciente])
def read_pacientes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Paciente).offset(skip).limit(limit).all()

@app.get("/pacientes/{paciente_id}", response_model=schemas.Paciente)
def read_paciente(paciente_id: int, db: Session = Depends(get_db)):
    paciente = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    if paciente is None:
        raise HTTPException(status_code=404, detail="Paciente não encontrado")
    return paciente

@app.put("/pacientes/{paciente_id}", response_model=schemas.Paciente)
def update_paciente(paciente_id: int, paciente: schemas.PacienteCreate, db: Session = Depends(get_db)):
    db_paciente = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    if db_paciente is None:
        raise HTTPException(status_code=404, detail="Paciente não encontrado")
    for key, value in paciente.model_dump().items():
        setattr(db_paciente, key, value)
    db.commit()
    db.refresh(db_paciente)
    return db_paciente

# --- Especialidades ---
@app.post("/especialidades", response_model=schemas.Especialidade, dependencies=[Depends(check_admin)])
def create_especialidade(especialidade: schemas.EspecialidadeCreate, db: Session = Depends(get_db)):
    db_esp = models.Especialidade(**especialidade.model_dump())
    db.add(db_esp)
    db.commit()
    db.refresh(db_esp)
    return db_esp

# --- Médicos ---
@app.post("/medicos", response_model=schemas.Medico, dependencies=[Depends(check_admin)])
def create_medico(medico: schemas.MedicoCreate, db: Session = Depends(get_db)):
    db_medico = models.Medico(**medico.model_dump())
    db.add(db_medico)
    db.commit()
    db.refresh(db_medico)
    return db_medico

@app.get("/medicos", response_model=List[schemas.Medico])
def read_medicos(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Medico).offset(skip).limit(limit).all()

@app.get("/medicos/{medico_id}", response_model=schemas.Medico)
def read_medico(medico_id: int, db: Session = Depends(get_db)):
    medico = db.query(models.Medico).filter(models.Medico.id == medico_id).first()
    if medico is None:
        raise HTTPException(status_code=404, detail="Médico não encontrado")
    return medico

# --- Rotas Internas para Validação ---
@app.get("/interna/validar-paciente/{paciente_id}")
def validar_paciente(paciente_id: int, db: Session = Depends(get_db)):
    paciente = db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente não encontrado")
    return {"valido": True}

@app.get("/interna/validar-medico/{medico_id}", response_model=schemas.Medico)
def validar_medico(medico_id: int, db: Session = Depends(get_db)):
    medico = db.query(models.Medico).filter(models.Medico.id == medico_id).first()
    if not medico:
        raise HTTPException(status_code=404, detail="Médico não encontrado")
    return medico
