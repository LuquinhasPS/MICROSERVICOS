import urllib.request
import json
import time
import subprocess
import sys
from datetime import datetime, timedelta

CADASTROS_URL = "http://localhost:8001"
AGENDAMENTOS_URL = "http://localhost:8002"
FATURAMENTO_URL = "http://localhost:8003"

def make_request(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    
    req_data = None
    if data is not None:
        req_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
        
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            resp_body = response.read().decode("utf-8")
            if resp_body:
                return response.status, json.loads(resp_body)
            return response.status, None
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(resp_body)
        except:
            return e.code, resp_body
    except Exception as e:
        return 500, str(e)

def truncate_databases():
    print("[LIMPEZA] [1/3] Limpando todas as tabelas nos bancos de dados PostgreSQL...")
    
    # 1. Truncar db_cadastros
    cmd_cad = [
        "docker", "exec", "-i", "clinica_db", "psql", "-U", "postgres", "-d", "db_cadastros", 
        "-c", "TRUNCATE TABLE medicos, pacientes, especialidades RESTART IDENTITY CASCADE;"
    ]
    res_cad = subprocess.run(cmd_cad, capture_output=True, text=True)
    if res_cad.returncode != 0:
        print(f"[ERRO] Erro ao limpar db_cadastros: {res_cad.stderr}")
        return False
    
    # 2. Truncar db_agendamentos
    cmd_age = [
        "docker", "exec", "-i", "clinica_db", "psql", "-U", "postgres", "-d", "db_agendamentos", 
        "-c", "TRUNCATE TABLE consultas, faturamentos_pendentes RESTART IDENTITY CASCADE;"
    ]
    res_age = subprocess.run(cmd_age, capture_output=True, text=True)
    if res_age.returncode != 0:
        print(f"[ERRO] Erro ao limpar db_agendamentos: {res_age.stderr}")
        return False

    # 3. Truncar db_faturamento
    cmd_fat = [
        "docker", "exec", "-i", "clinica_db", "psql", "-U", "postgres", "-d", "db_faturamento", 
        "-c", "TRUNCATE TABLE faturas RESTART IDENTITY CASCADE;"
    ]
    res_fat = subprocess.run(cmd_fat, capture_output=True, text=True)
    if res_fat.returncode != 0:
        print(f"[ERRO] Erro ao limpar db_faturamento: {res_fat.stderr}")
        return False

    print("[OK] Bancos de dados reiniciados com sucesso!")
    return True

def get_next_weekday(weekday_str):
    """Retorna a data (YYYY-MM-DD) do próximo dia da semana correspondente (ex: 'SEG', 'TER', 'QUI')."""
    days = {"SEG": 0, "TER": 1, "QUA": 2, "QUI": 3, "SEX": 4, "SAB": 5, "DOM": 6}
    target = days.get(weekday_str.upper(), 0)
    now = datetime.now()
    # Calcula os dias de diferença
    diff = (target - now.weekday() + 7) % 7
    # Se for hoje, agenda para a próxima semana para garantir consistência
    if diff == 0:
        diff = 7
    next_date = now + timedelta(days=diff)
    return next_date.strftime("%Y-%m-%d")

def seed_data():
    print("[SEED] [2/3] Populando banco de dados com dados de demonstração...")

    # 1. Especialidades (Cadastradas com x-role: admin)
    print("  -> Cadastrando Especialidades...")
    especialidades = ["Cardiologia", "Ortopedia", "Pediatria", "Clínica Geral"]
    esp_ids = {}
    for esp in especialidades:
        status, res = make_request(f"{CADASTROS_URL}/especialidades", "POST", {"nome": esp}, {"x-role": "admin"})
        if status == 200:
            esp_ids[esp] = res["id"]
        else:
            print(f"  [ERRO] Erro ao criar especialidade {esp}: {res}")
            sys.exit(1)

    # 2. Pacientes
    print("  -> Cadastrando Pacientes...")
    pacientes = [
        {"nome": "Lucas Silveira", "cpf": "123.456.789-00", "email": "lucas@email.com", "telefone": "(21) 99999-9999"},
        {"nome": "Maria Oliveira", "cpf": "987.654.321-11", "email": "maria@email.com", "telefone": "(11) 98888-8888"},
        {"nome": "João Santos", "cpf": "111.222.333-44", "email": "joao@email.com", "telefone": "(31) 97777-7777"}
    ]
    pac_ids = {}
    for pac in pacientes:
        status, res = make_request(f"{CADASTROS_URL}/pacientes", "POST", pac)
        if status == 200:
            pac_ids[pac["nome"]] = res["id"]
        else:
            print(f"  [ERRO] Erro ao criar paciente {pac['nome']}: {res}")
            sys.exit(1)

    # 3. Médicos (Cadastrados com x-role: admin)
    print("  -> Cadastrando Médicos com escalas...")
    medicos = [
        {
            "nome": "Dr. Carlos Eduardo", "crm": "CRM-RJ-001001", "especialidade_id": esp_ids["Cardiologia"],
            "dias_trabalho": "SEG,QUA,SEX", "horario_inicio": "09:00:00", "horario_fim": "17:00:00"
        },
        {
            "nome": "Dra. Mariana Souza", "crm": "CRM-SP-002002", "especialidade_id": esp_ids["Ortopedia"],
            "dias_trabalho": "TER,QUI", "horario_inicio": "08:00:00", "horario_fim": "14:00:00"
        },
        {
            "nome": "Dr. Fernando Silva", "crm": "CRM-MG-003003", "especialidade_id": esp_ids["Pediatria"],
            "dias_trabalho": "SEG,TER,QUI,SEX", "horario_inicio": "13:00:00", "horario_fim": "18:00:00"
        },
        {
            "nome": "Dra. Roberta Costa", "crm": "CRM-RJ-004004", "especialidade_id": esp_ids["Clínica Geral"],
            "dias_trabalho": "SEG,TER,QUA,QUI,SEX,SAB", "horario_inicio": "08:00:00", "horario_fim": "18:00:00"
        }
    ]
    med_ids = {}
    for med in medicos:
        status, res = make_request(f"{CADASTROS_URL}/medicos", "POST", med, {"x-role": "admin"})
        if status == 200:
            med_ids[med["nome"]] = res["id"]
        else:
            print(f"  [ERRO] Erro ao criar médico {med['nome']}: {res}")
            sys.exit(1)

    # 4. Consultas com diferentes estados
    print("  -> Agendando e configurando Consultas de Demonstração...")
    
    # Próximas datas de agendamentos válidas
    segunda = get_next_weekday("SEG")
    terca = get_next_weekday("TER")
    quinta = get_next_weekday("QUI")

    # Consulta 1: Lucas Silveira com Dr. Carlos Eduardo -> PENDENTE
    c1_payload = {
        "paciente_id": pac_ids["Lucas Silveira"],
        "medico_id": med_ids["Dr. Carlos Eduardo"],
        "data_hora": f"{segunda}T10:00:00"
    }
    status, c1 = make_request(f"{AGENDAMENTOS_URL}/consultas", "POST", c1_payload)
    if status == 200:
        print(f"    * Consulta #1 criada (PENDENTE). ID: {c1['id']}")
    
    # Consulta 2: Maria Oliveira com Dra. Roberta Costa -> CONFIRMADA
    c2_payload = {
        "paciente_id": pac_ids["Maria Oliveira"],
        "medico_id": med_ids["Dra. Roberta Costa"],
        "data_hora": f"{segunda}T09:00:00"
    }
    status, c2 = make_request(f"{AGENDAMENTOS_URL}/consultas", "POST", c2_payload)
    if status == 200:
        c2_id = c2["id"]
        # Confirmar como admin
        make_request(f"{AGENDAMENTOS_URL}/consultas/{c2_id}/confirmar", "POST", headers={"x-role": "admin"})
        print(f"    * Consulta #2 criada e confirmada (CONFIRMADA). ID: {c2_id}")

    # Consulta 3: João Santos com Dr. Fernando Silva -> CONCLUIDA e faturada
    c3_payload = {
        "paciente_id": pac_ids["João Santos"],
        "medico_id": med_ids["Dr. Fernando Silva"],
        "data_hora": f"{terca}T14:30:00"
    }
    status, c3 = make_request(f"{AGENDAMENTOS_URL}/consultas", "POST", c3_payload)
    if status == 200:
        c3_id = c3["id"]
        # Confirmar
        make_request(f"{AGENDAMENTOS_URL}/consultas/{c3_id}/confirmar", "POST", headers={"x-role": "admin"})
        # Concluir (Valor R$ 250.00)
        make_request(f"{AGENDAMENTOS_URL}/consultas/{c3_id}/concluir", "POST", {"valor": 250.00})
        print(f"    * Consulta #3 criada, confirmada e concluída (CONCLUIDA). ID: {c3_id}")

    # Consulta 4: Lucas Silveira com Dra. Mariana Souza -> CANCELADA
    c4_payload = {
        "paciente_id": pac_ids["Lucas Silveira"],
        "medico_id": med_ids["Dra. Mariana Souza"],
        "data_hora": f"{quinta}T11:30:00"
    }
    status, c4 = make_request(f"{AGENDAMENTOS_URL}/consultas", "POST", c4_payload)
    if status == 200:
        c4_id = c4["id"]
        # Solicitar cancelamento
        make_request(f"{AGENDAMENTOS_URL}/consultas/{c4_id}/solicitar-cancelamento", "POST")
        # Aprovar cancelamento
        make_request(f"{AGENDAMENTOS_URL}/consultas/{c4_id}/aprovar-cancelamento", "POST", headers={"x-role": "admin"})
        print(f"    * Consulta #4 criada e cancelada (CANCELADA). ID: {c4_id}")

    print("[OK] População de dados concluída com sucesso!")

def run_seeder():
    print("=" * 80)
    print(" REINICIANDO E POPULANDO O BANCO DE DADOS DA CLÍNICA ")
    print("=" * 80)
    if truncate_databases():
        seed_data()
        
        # 3. Forçar sincronização do outbox para garantir que faturas da consulta concluída sejam criadas
        print("\n[SYNC] [3/3] Forçando sincronização de faturas pendentes...")
        status, sync_res = make_request(f"{FATURAMENTO_URL}/interna/sincronizar", "POST")
        if status == 200:
            print("[SYNC] Sincronização concluída com o MS-Faturamento!")
        else:
            print("[INFO] Nota: MS-Faturamento offline ou erro de sincronização (reconciliação pendente no outbox).")
            
        print("\n" + "=" * 80)
        print(" BANCO DE DADOS POPULADO E PRONTO PARA A DEMONSTRAÇÃO! ")
        print("=" * 80)
    else:
        print("[ERRO] Não foi possível redefinir o banco de dados. Verifique se o Docker Compose está ativo.")

if __name__ == "__main__":
    run_seeder()
