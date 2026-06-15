import urllib.request
import json
import time
import subprocess
import sys

CADASTROS_URL = "http://localhost:8001"
AGENDAMENTOS_URL = "http://localhost:8002"
FATURAMENTO_URL = "http://localhost:8003"

def print_header(title):
    print("\n" + "=" * 80)
    print(f" {title.upper():^78} ")
    print("=" * 80)

def print_sub_header(title):
    print(f"\n* --- {title} ---")

def print_success(msg):
    print(f"  [OK SUCCESS] {msg}")

def print_fail(msg):
    print(f"  [FAIL] {msg}")

def print_info(msg):
    print(f"  [INFO] {msg}")

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
            err_json = json.loads(resp_body)
            return e.code, err_json
        except:
            return e.code, resp_body
    except Exception as e:
        return 500, str(e)

def manage_container(action, container_name):
    """Executa comando do docker compose para parar ou iniciar um serviço."""
    cmd = ["docker", "compose", action, container_name]
    print_info(f"Orquestrando infraestrutura: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print_success(f"Container '{container_name}' {action}ed com sucesso.")
            return True
        else:
            print_fail(f"Erro ao gerenciar container: {res.stderr}")
            return False
    except Exception as e:
        print_fail(f"Comando docker compose falhou: {str(e)}")
        return False

def run_elaborate_tests():
    print_header("Iniciando Teste de Integração Avançado - Sistema de Clínicas")
    
    # Gerar suffix único para CPFs e CRMs para evitar conflitos no banco
    unique_suffix = str(int(time.time()))[-6:]
    
    # -------------------------------------------------------------
    print_header("Caso 1: Cadastro de Entidades e Escalas")
    # -------------------------------------------------------------
    
    # 1. Cadastrar Paciente
    paciente_payload = {
        "nome": "Lucas Silveira Teste",
        "cpf": f"999.888.{unique_suffix}-11",
        "email": f"lucas_{unique_suffix}@cefet.br",
        "telefone": "(21) 98765-4321"
    }
    status, paciente = make_request(f"{CADASTROS_URL}/pacientes", "POST", paciente_payload)
    if status == 200:
        paciente_id = paciente["id"]
        print_success(f"Paciente cadastrado. ID: {paciente_id}")
    else:
        print_fail(f"Falha ao cadastrar paciente (Status {status}): {paciente}")
        sys.exit(1)
        
    # 2. Cadastrar Especialidade
    esp_payload = {"nome": f"Neurologia {unique_suffix}"}
    status, esp = make_request(f"{CADASTROS_URL}/especialidades", "POST", esp_payload, {"x-role": "admin"})
    if status == 200:
        especialidade_id = esp["id"]
        print_success(f"Especialidade cadastrada. ID: {especialidade_id}")
    else:
        print_fail(f"Falha ao cadastrar especialidade (Status {status}): {esp}")
        sys.exit(1)
        
    # 3. Cadastrar Médico com escala (SEG,QUA,SEX das 09:00 às 17:00)
    medico_payload = {
        "nome": "Dra. Ana Nogueira",
        "crm": f"CRM-RJ-{unique_suffix}",
        "especialidade_id": especialidade_id,
        "dias_trabalho": "SEG,QUA,SEX",
        "horario_inicio": "09:00:00",
        "horario_fim": "17:00:00"
    }
    status, medico = make_request(f"{CADASTROS_URL}/medicos", "POST", medico_payload, {"x-role": "admin"})
    if status == 200:
        medico_id = medico["id"]
        print_success(f"Médico cadastrado com escala definida. ID: {medico_id}")
    else:
        print_fail(f"Falha ao cadastrar médico (Status {status}): {medico}")
        sys.exit(1)

    # -------------------------------------------------------------
    print_header("Caso 2: Testes de Validação de Regras de Escala Médica")
    # -------------------------------------------------------------
    
    # 2.1. Agendar em dia incorreto (Terça-feira - 16/06/2026)
    print_sub_header("Validando agendamento em dia em que o médico não trabalha (Terça-feira)")
    consulta_dia_invalido = {
        "paciente_id": paciente_id,
        "medico_id": medico_id,
        "data_hora": "2026-06-16T10:00:00" # Terça
    }
    status, err = make_request(f"{AGENDAMENTOS_URL}/consultas", "POST", consulta_dia_invalido)
    if status == 400:
        print_success(f"Bloqueado corretamente com erro 400: {err['detail']}")
    else:
        print_fail(f"Esperado erro 400, recebido {status}: {err}")
        sys.exit(1)
        
    # 2.2. Agendar antes do horário de expediente (08:30:00)
    print_sub_header("Validando agendamento antes do horário de início do expediente (08:30)")
    consulta_hora_cedo = {
        "paciente_id": paciente_id,
        "medico_id": medico_id,
        "data_hora": "2026-06-15T08:30:00" # Segunda, 08:30
    }
    status, err = make_request(f"{AGENDAMENTOS_URL}/consultas", "POST", consulta_hora_cedo)
    if status == 400:
        print_success(f"Bloqueado corretamente com erro 400: {err['detail']}")
    else:
        print_fail(f"Esperado erro 400, recebido {status}: {err}")
        sys.exit(1)

    # 2.3. Agendar depois do horário de expediente (17:30:00)
    print_sub_header("Validando agendamento após o horário de término do expediente (17:30)")
    consulta_hora_tarde = {
        "paciente_id": paciente_id,
        "medico_id": medico_id,
        "data_hora": "2026-06-15T17:30:00" # Segunda, 17:30
    }
    status, err = make_request(f"{AGENDAMENTOS_URL}/consultas", "POST", consulta_hora_tarde)
    if status == 400:
        print_success(f"Bloqueado corretamente com erro 400: {err['detail']}")
    else:
        print_fail(f"Esperado erro 400, recebido {status}: {err}")
        sys.exit(1)

    # -------------------------------------------------------------
    print_header("Caso 3: Conflitos de Horários e Entidades Inexistentes")
    # -------------------------------------------------------------
    
    # 3.1. Agendar com Paciente inexistente
    print_sub_header("Agendando consulta com ID de paciente inválido")
    consulta_paciente_invalido = {
        "paciente_id": 999999,
        "medico_id": medico_id,
        "data_hora": "2026-06-15T10:00:00"
    }
    status, err = make_request(f"{AGENDAMENTOS_URL}/consultas", "POST", consulta_paciente_invalido)
    if status == 400:
        print_success(f"Bloqueado corretamente: {err['detail']}")
    else:
        print_fail(f"Esperado erro 400, recebido {status}: {err}")
        sys.exit(1)

    # 3.2. Agendar consulta válida inicial
    print_sub_header("Agendando consulta válida inicial para Segunda-feira às 10:00")
    consulta_valida = {
        "paciente_id": paciente_id,
        "medico_id": medico_id,
        "data_hora": "2026-06-15T10:00:00"
    }
    status, c1 = make_request(f"{AGENDAMENTOS_URL}/consultas", "POST", consulta_valida)
    if status == 200:
        c1_id = c1["id"]
        print_success(f"Consulta agendada! ID: {c1_id}, Status: {c1['status']}")
    else:
        print_fail(f"Erro ao agendar consulta válida (Status {status}): {c1}")
        sys.exit(1)

    # 3.3. Agendar conflito (Mesmo médico, mesmo horário)
    print_sub_header("Agendando segunda consulta no mesmo horário para o mesmo médico (conflito)")
    status, err = make_request(f"{AGENDAMENTOS_URL}/consultas", "POST", consulta_valida)
    if status == 400:
        print_success(f"Conflito de horário bloqueado corretamente: {err['detail']}")
    else:
        print_fail(f"Esperado bloqueio por conflito de horário (400), recebido {status}: {err}")
        sys.exit(1)

    # -------------------------------------------------------------
    print_header("Caso 4: Fluxo de Cancelamento e Confirmação")
    # -------------------------------------------------------------
    
    # 4.0. Confirmar a consulta c1 (Requer admin)
    print_sub_header("Confirmando a consulta c1 (X-Role: admin)")
    status, err = make_request(f"{AGENDAMENTOS_URL}/consultas/{c1_id}/confirmar", "POST")
    assert status == 403
    print_success("Bloqueio de confirmação sem permissão de admin funcionou.")
    
    status, res = make_request(f"{AGENDAMENTOS_URL}/consultas/{c1_id}/confirmar", "POST", headers={"x-role": "admin"})
    assert status == 200
    print_success("Consulta c1 confirmada pelo administrador com sucesso.")

    # 4.1. Solicitar cancelamento (Paciente)
    print_sub_header("Paciente solicita cancelamento da consulta")
    status, res = make_request(f"{AGENDAMENTOS_URL}/consultas/{c1_id}/solicitar-cancelamento", "POST")
    assert status == 200
    print_success(f"Cancelamento solicitado. Resposta: {res['message']}")
    
    # 4.2. Reprovar cancelamento (Admin)
    print_sub_header("Admin rejeita a solicitação de cancelamento da consulta")
    status, res = make_request(f"{AGENDAMENTOS_URL}/consultas/{c1_id}/reprovar-cancelamento", "POST", headers={"x-role": "admin"})
    assert status == 200
    print_success(f"Cancelamento rejeitado pelo admin. Consulta mantida.")
    
    # 4.3. Solicitar cancelamento de novo e aprovar cancelamento (Admin)
    print_sub_header("Paciente solicita cancelamento novamente e admin aprova")
    make_request(f"{AGENDAMENTOS_URL}/consultas/{c1_id}/solicitar-cancelamento", "POST")
    status, res = make_request(f"{AGENDAMENTOS_URL}/consultas/{c1_id}/aprovar-cancelamento", "POST", headers={"x-role": "admin"})
    assert status == 200
    print_success(f"Cancelamento aprovado pelo admin. Status da consulta agora é CANCELADA.")

    # -------------------------------------------------------------
    print_header("Caso 5: Fluxo de Remarcação de Consultas")
    # -------------------------------------------------------------
    
    # 5.1. Agendar nova consulta válida
    print_sub_header("Agendando consulta de teste para remarcação")
    consulta_remarcar_payload = {
        "paciente_id": paciente_id,
        "medico_id": medico_id,
        "data_hora": "2026-06-15T14:00:00"
    }
    status, c2 = make_request(f"{AGENDAMENTOS_URL}/consultas", "POST", consulta_remarcar_payload)
    assert status == 200
    c2_id = c2["id"]
    print_info(f"Consulta criada: ID {c2_id}, Data: {c2['data_hora']}, Status: {c2['status']}")
    
    # 5.2. Remarcar consulta para outro dia válido (Quarta-feira - 17/06/2026 às 15:00)
    print_sub_header("Remarcando consulta para outro horário válido (Quarta-feira)")
    remarcar_payload = {"data_hora": "2026-06-17T15:00:00"}
    status, res = make_request(f"{AGENDAMENTOS_URL}/consultas/{c2_id}/remarcar", "PUT", remarcar_payload)
    if status == 200:
        print_success(f"Consulta remarcada! Mensagem: {res['message']}. Nova Data: {res['nova_data']}")
    else:
        print_fail(f"Erro ao remarcar consulta (Status {status}): {res}")
        sys.exit(1)

    # c2 já se torna CONFIRMADA no fluxo de remarcação

    # -------------------------------------------------------------
    print_header("Caso 6: Teste de Resiliência Automatizado (Outbox Pattern)")
    # -------------------------------------------------------------
    
    # 6.1. Simular queda do MS-Faturamento derrubando o container
    print_sub_header("Parando o container 'ms-faturamento' para simular falha no faturamento...")
    if not manage_container("stop", "ms-faturamento"):
        print_info("Ignorando teste automatizado do docker (pode ser executado no host local sem permissões docker).")
        print_info("Por favor, garanta que o teste do outbox está funcionando de acordo com as instruções manuais.")
        return
        
    # 6.2. Concluir a consulta c2 enquanto o faturamento está offline
    print_sub_header("Concluindo a consulta ID " + str(c2_id) + " (Faturamento Offline)")
    concluir_payload = {"valor": 350.0}
    status, conclusao = make_request(f"{AGENDAMENTOS_URL}/consultas/{c2_id}/concluir", "POST", concluir_payload)
    if status == 200:
        print_success(f"Consulta concluída normalmente! Resposta: {conclusao['message']}")
        # Deve avisar que salvou no outbox pendente
        assert "offline" in conclusao["message"].lower() or "pendente" in conclusao["message"].lower()
    else:
        print_fail(f"Erro ao concluir consulta (Status {status}): {conclusao}")
        sys.exit(1)
        
    # 6.3. Verificar se a pendência está gravada no banco do MS-Agendamentos
    print_sub_header("Verificando se a pendência de faturamento foi gravada no outbox local...")
    status, pendencias = make_request(f"{AGENDAMENTOS_URL}/interna/pendencias-faturamento")
    assert status == 200
    pendencia_encontrada = False
    for p in pendencias:
        if p["consulta_id"] == c2_id and p["valor"] == 350.0:
            print_success(f"Pendência encontrada no Outbox! ID Pendência: {p['id']}, Consulta: {p['consulta_id']}, Status Sinc: {p['status_sincronizacao']}")
            pendencia_encontrada = True
            break
    assert pendencia_encontrada
    
    # 6.4. Subir o container do MS-Faturamento novamente
    print_sub_header("Iniciando o container 'ms-faturamento' novamente...")
    manage_container("start", "ms-faturamento")
    
    # Aguardar alguns segundos para inicialização completa do FastAPI no container
    print_info("Aguardando 5 segundos para o serviço MS-Faturamento reestabelecer...")
    time.sleep(5)
    
    # 6.5. Forçar a sincronização via endpoint do MS-Faturamento
    print_sub_header("Disparando reconciliação manual do Outbox no MS-Faturamento...")
    status, sync_res = make_request(f"{FATURAMENTO_URL}/interna/sincronizar", "POST")
    if status == 200:
        print_success(f"Sincronização concluída! Resposta: {sync_res['status']}")
    else:
        print_fail(f"Erro ao disparar sincronização (Status {status}): {sync_res}")
        sys.exit(1)
        
    # 6.6. Verificar se a fatura foi devidamente criada e a pendência baixada
    print_sub_header("Confirmando se a fatura foi criada no banco de faturamento após retorno...")
    status, faturas = make_request(f"{FATURAMENTO_URL}/faturas")
    assert status == 200
    fatura_criada = False
    for f in faturas:
        if f["consulta_id"] == c2_id:
            print_success(f"Fatura criada retroativamente! ID Fatura: {f['id']}, Consulta: {f['consulta_id']}, Valor: R$ {f['valor']:.2f}, Status: {f['status_pagamento']}")
            fatura_criada = True
            break
    assert fatura_criada
    
    print_header("Todos os Testes de Integração Avançados Passaram com Sucesso!")

if __name__ == "__main__":
    run_elaborate_tests()
