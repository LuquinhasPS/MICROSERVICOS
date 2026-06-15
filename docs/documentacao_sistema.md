# Documentação Arquitetural e de Software

**Disciplina:** Arquitetura e Padrões de Software  
**Instituição:** Centro Federal de Educação Tecnológica Celso Suckow da Fonseca (CEFET/RJ)  
**Professor:** Marcelo Arêas  
**Curso:** Engenharia de Computação / Engenharia de Software  

---

## 1. Descrição do Sistema: Problema e Solução

### 1.1. O Problema: Gestão de Clínicas Médicas
Sistemas tradicionais de saúde frequentemente operam em arquiteturas monolíticas altamente acopladas. Na gestão de clínicas médicas, a coesão de operações críticas — como o cadastramento de pacientes, agendamento de consultas com escalas de médicos especialistas e o faturamento financeiro — apresenta desafios significativos de disponibilidade e tolerância a falhas. 

Em uma infraestrutura centralizada e integrada, a queda temporária do módulo de faturamento (comum em integrações com gateways de pagamento ou serviços bancários externos) pode interromper completamente o agendamento de consultas ou o fluxo operacional de recepção do paciente, causando prejuízos financeiros e operacionais graves.

### 1.2. A Solução: Arquitetura de Microsserviços
Para resolver o acoplamento e garantir que falhas locais não paralisem toda a clínica, propõe-se uma arquitetura baseada em **microsserviços independentes e conteinerizados**. O sistema é composto por três microsserviços principais:

1. **MS-Cadastros:** Gerencia as entidades do domínio de pessoas (Pacientes, Médicos especialistas e Especialidades). É o serviço de referência principal.
2. **MS-Agendamentos:** Gerencia o ciclo de vida das consultas médicas. Integra-se ao `MS-Cadastros` para verificar a existência de entidades e validar se o dia e hora solicitados condizem com a escala do médico especialista. Gerencia também as regras de negócio de remarcação e de cancelamento de consultas (solicitação feita pelo paciente e aprovação/rejeição pelo administrador).
3. **MS-Faturamento:** Emite faturas e gerencia cobranças vinculadas às consultas. Opera de forma tolerante a falhas.

Cada serviço é executado em um container independente (através do Docker) e possui seu próprio banco de dados isolado (PostgreSQL), comunicando-se via requisições REST/JSON.

---

## 2. Preocupações Arquiteturais (Concerns) e Perspectivas

Para garantir que a arquitetura resolva o problema de forma robusta, foram mapeadas preocupações de engenharia (preocupações não funcionais) sob diferentes perspectivas arquiteturais:

### 2.1. Isolamento de Dados (Perspectiva de Dados)
* **Preocupação:** Evitar acoplamento de banco de dados (onde um serviço lê ou altera tabelas de outro serviço diretamente), o que impediria a escalabilidade independente.
* **Solução:** Adoção do padrão *Database per Service*. Cada microsserviço interage exclusivamente com seu banco de dados lógico dedicado (`db_cadastros`, `db_agendamentos`, `db_faturamento`). Qualquer compartilhamento de informação ocorre estritamente por contratos de API expostos via HTTP.

### 2.2. Confiabilidade e Tolerância a Falhas (Perspectiva de Resiliência)
* **Preocupação:** Manter o fluxo de atendimento médico ativo mesmo se o microsserviço financeiro (`MS-Faturamento`) estiver indisponível.
* **Solução:** Implementação do *Outbox Pattern Simplificado*. Se o faturamento falhar ao registrar uma consulta concluída, o `MS-Agendamentos` grava a pendência em uma tabela local de outbox. O sistema conclui o atendimento com sucesso para o usuário final, e a sincronização ocorre de forma assíncrona assim que o `MS-Faturamento` retorna ao ar.

### 2.3. Consistência Eventual
* **Preocupação:** Garantir que todos os atendimentos prestados sejam eventualmente faturados, sem perdas de transações.
* **Solução:** O `MS-Faturamento` possui um *worker* assíncrono em segundo plano (executado concorrentemente em sua thread de inicialização) que consulta periodicamente o endpoint de pendências do `MS-Agendamentos`, emitindo as faturas retroativamente e confirmando o recebimento para dar baixa na fila do outbox.

### 2.4. Segurança e Autorização Simplificada
* **Preocupação:** Restringir o acesso a rotas administrativas (como cadastro de médicos e especialidades) de maneira leve para demonstração em sala de aula.
* **Solução:** Uso do padrão de interceptação de cabeçalhos HTTP. A validação das permissões é realizada pela leitura do header `X-Role: admin` ou `X-Role: paciente` injetado na requisição HTTP.

---

## 3. Padrões de Software e Arquiteturais Utilizados

Abaixo detalha-se os padrões de projeto (Design Patterns) e padrões arquiteturais aplicados no código-fonte do sistema:

### 3.1. Padrão "Database per Service" (Arquitetura)
* **O que é:** Cada microsserviço possui e gerencia seu próprio banco de dados. Nenhum microsserviço acessa diretamente o banco de dados de outro.
* **Justificativa:** Garante independência de deploy e autonomia de escala. Se o volume de dados de faturas crescer exponencialmente, apenas o banco do `MS-Faturamento` precisa ser otimizado ou escalado, sem afetar o cadastro de médicos ou pacientes.
* **Implementação:** No Docker Compose, mapeamos um único container PostgreSQL físico para fins didáticos, mas criamos **três bancos de dados lógicos separados** inicializados pelo script `db-init/init.sql`. Cada aplicação FastAPI se conecta via variáveis de ambiente exclusivamente à sua URI:
  * `DATABASE_URL=postgresql://.../db_cadastros`
  * `DATABASE_URL=postgresql://.../db_agendamentos`
  * `DATABASE_URL=postgresql://.../db_faturamento`

### 3.2. Padrão "Outbox Pattern" Simplificado (Resiliência)
* **O que é:** Em vez de tentar uma transação distribuída de duas fases (2PC) complexa para faturar a consulta, o microsserviço de agendamento salva o evento em uma tabela de pendências local (dentro do mesmo escopo de transação que atualiza a consulta) caso a API de faturamento falhe.
* **Justificativa:** Evita falhas em cadeia (indisponibilidade em cascata). O sistema tolera a queda de componentes de terceiros mantendo a integridade operacional da clínica.
* **Implementação:** No endpoint `/consultas/{consulta_id}/concluir` do `MS-Agendamentos`:
  1. O status da consulta é atualizado para `CONCLUIDA`.
  2. Uma chamada HTTP POST para o `MS-Faturamento` é feita.
  3. Se ocorrer um erro de conexão (`httpx.RequestError`), o sistema intercepta a exceção e insere um registro na tabela `faturamentos_pendentes` com o status `PENDENTE`.
  4. O usuário recebe um retorno HTTP 200 OK com uma mensagem alertando que o faturamento será reconciliado.

### 3.3. Padrão "Background Worker / Polling" (Integração)
* **O que é:** Um processo que roda em segundo plano consumindo e reconciliando estados de forma assíncrona.
* **Justificativa:** Resolve o problema da consistência eventual sem necessitar de uma fila de mensageria complexa (como RabbitMQ ou Kafka) para a demonstração do trabalho acadêmico.
* **Implementação:** No `MS-Faturamento` (`ms-faturamento/main.py`), definimos um loop assíncrono que roda a cada 60 segundos (e também no evento `@app.on_event("startup")`):
  1. Ele consulta o endpoint `/interna/pendencias-faturamento` do `MS-Agendamentos`.
  2. Para cada pendência listada, ele insere a fatura no banco `db_faturamento`.
  3. Após salvar a fatura com sucesso, ele faz uma chamada POST para `/interna/pendencias-faturamento/{id}/confirmar` no `MS-Agendamentos`, que altera o status da pendência para `PROCESSADO`, limpando a fila.

### 3.4. Padrão "Data Transfer Object - DTO / Schemas" (Projeto)
* **O que é:** Separação da estrutura física do banco de dados (Modelos de Entidade) da estrutura de dados trafegada na rede (Contratos de Entrada e Saída).
* **Justificativa:** Protege o banco de dados contra injeção de atributos indesejados (Mass Assignment) e padroniza a formatação de payloads nas requisições HTTP REST.
* **Implementação:** Utilização de classes **Pydantic** (`schemas.py` de cada serviço) que mapeiam os payloads de entrada (ex: `PacienteCreate`) e saída (ex: `Paciente`). As validações de formato (tipos, presença de campos obrigatórios) são feitas automaticamente pelo framework em tempo de execução.

### 3.5. Padrão "Containerization & Orchestration" (Infraestrutura)
* **O que é:** Execução de cada módulo e sua dependência de forma isolada dentro de containers Docker, orquestrados por uma declaração descritiva centralizada.
* **Justificativa:** Resolve o problema clássico de dependências locais de ambiente ("funciona na minha máquina"). Garante que o professor ou colegas de equipe subam todo o ecossistema complexo de 3 servidores mais banco de dados com um único comando.
* **Implementação:** Uso do [docker-compose.yml](file:///c:/Users/LUCAS/Meu%20Canto/CEFET/APS2/MICROSERVICOS/docker-compose.yml) configurando os serviços de rede, build dos Dockerfiles individuais de cada microsserviço Python, variáveis de ambiente e o banco de dados com Healthcheck integrado para gerenciar a ordem correta de inicialização.

### 3.6. Interface de Demonstração (Front-end e Integração)
* **O que é:** Uma aplicação cliente leve de página única (Single-Page Application - SPA) desenvolvida com HTML5, JavaScript vanilla e CSS customizado para interagir com as APIs REST de cada microsserviço.
* **Justificativa:** Atende à exigência de validação do projeto acadêmico, fornecendo uma camada visual para que o professor e os alunos executem e demonstrem fluxos de CRUD, validação de escalas de trabalho e, principalmente, simulem cenários de tolerância a falhas derrubando e subindo os containers.
* **Implementação:**
  * **Habilitação de CORS (Cross-Origin Resource Sharing):** Como o front-end roda no navegador (seja via `file://` ou servidor web estático) e os microsserviços rodam em portas diferentes (`localhost:8001`, `:8002` e `:8003`), adicionou-se o middleware `CORSMiddleware` nas instâncias FastAPI para permitir que o navegador execute requisições sem bloqueio de segurança.
  * **Monitoramento Concorrente de Saúde (Health Check):** Para evitar que um microsserviço offline (como o `MS-Agendamentos` pausado) bloqueie a verificação de saúde dos outros serviços, o front-end executa as requisições de teste em paralelo através de chamadas assíncronas assíncronas concorrentes (`fetch` tratado com promessas paralelas), garantindo atualização instantânea do status no painel.

