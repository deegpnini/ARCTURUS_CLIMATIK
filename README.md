# ARCTURUS CLIMATIK

**Plataforma de observação, alerta e aprendizado contínuo da Bacia do Rio Tubarão (SC).**

O ARCTURUS não é um modelo. É uma plataforma de monitoramento hidrológico que combina:
- **Camada 1 (física):** alerta em tempo real baseado em Vz/Az (regras físicas).
- **Camada 2 (científica):** modelo LightGBM em modo sombra (aprende sem alertar).
- **Camada 3 (territorial):** Atlas de Impacto (edificações, escolas, UBS).

**Princípio:** Evidência Primeiro. Modelos podem falhar. Evidências permanecem.

---

## Arquitetura e Estrutura de Diretórios

### Fluxo da operação

O ciclo operacional coleta telemetria da Defesa Civil SC e dados meteorológicos,
atualiza o banco e executa os componentes hidrológicos e de previsão. O v8 é
executado no fluxo de produção; o v11c roda isolado em modo sombra. O dashboard
e o boletim do Telegram apresentam os dados e resultados disponíveis. A
configuração do ciclo não significa, por si só, que cada serviço esteja saudável
em tempo real.

### Estrutura versionada

```text
.
├── app_dash.py                 # entrada do dashboard
├── dashboard_correcoes.py     # funções de apoio importadas pelo dashboard
├── run_cycle.sh                # orquestrador do ciclo operacional
├── cron_motor.sh               # coleta/classificação usada pelo ciclo
├── boletim_telegram.py         # montagem e envio do boletim
├── boletim_cadencia.sh         # controle de cadência do boletim
├── health_check.sh             # verificação operacional
├── watchdog_arcturus.sh        # watchdog do ciclo
├── backup_diario.sh            # backup agendado
├── src/
│   ├── coleta/                 # coletores e atualização de previsões
│   ├── modelo/                 # modelos, inferência e modo sombra
│   ├── relatorios/             # persistência e relatórios
│   └── analise/                # análises do ciclo hidrológico
├── scripts/
│   ├── auditoria/              # auditorias e diagnósticos
│   ├── coleta_hist/            # utilitários históricos de coleta
│   ├── geo_utils/              # ferramentas geográficas
│   ├── modelo_treino/          # avaliação, experimentos e treinamento
│   ├── analise/                # análises auxiliares existentes
│   └── simulacao/              # simulações
├── tests/                      # testes automatizados
├── docs/                       # documentação e registros técnicos
└── data/                       # dados locais e artefatos operacionais
```

Os principais pontos de entrada e arquivos operacionais permanecem na raiz.
Alguns módulos de apoio, como `dashboard_correcoes.py`, `ana_auth.py`,
`model_runner.py`, `persistir_shadow.py` e `backfill_y_true.py`, também ficam
ali por ainda serem importados ou chamados por esses pontos de entrada. Código
reutilizável e componentes do pipeline ficam em `src/`; ferramentas de análise,
auditoria, treinamento e utilitários ficam em `scripts/`. Conteúdo local
temporário em `scripts/local_tmp/` é ignorado pelo Git e não faz parte da
estrutura publicada.

### Operação contínua configurada

A crontab observada no WSL agenda o ciclo principal a cada 15 minutos. O
`run_cycle.sh` atualiza a previsão quando necessário, coleta dados da Defesa
Civil, executa o fluxo de produção e o modo sombra, e avalia o envio do boletim.
Também estão configurados health check a cada 15 minutos, watchdog nos minutos
7, 22, 37 e 52, coleta complementar de chuva a cada 6 horas e backup diário às
03:00. Esses horários descrevem a configuração do agendador, não substituem a
verificação dos logs nem confirmam que uma execução específica teve sucesso.

Há ainda um pipeline diário de promoção/sombra configurado em outro diretório
(`~/projetos/arcturus_coleta`); ele é externo a este repositório.

### Histórico de eventos auditados

Os resultados de eventos abaixo são análises históricas de um conjunto limitado
de casos. Não descrevem a execução atual do ciclo nem devem ser interpretados
como garantia operacional ou validação definitiva de um modelo.

---
## Histórico: análise do lag chuva-rio na Bacia do Tubarão (08/11/2026)

Medimos o lag (tempo entre o pico da chuva na cabeceira e o pico da cota em Tubarão) para 5 eventos:

| Evento | Pico da Chuva | Lag (h) |
|--------|---------------|---------|
| 27/10 11:30 | 26/10 13:00 | 33.7 |
| 30/10 16:45 | 29/10 21:00 | 31.0 |
| 03/11 17:45 | 03/11 13:00 | 16.0 |
| **04/11 08:30** | **04/11 07:00** | **13.5** |
| 07/11 21:30 | 07/11 12:00 | 16.0 |

**Leitura limitada da amostra:** Os cinco eventos mostram lags entre 13,5 e
33,7 horas. A variação observada requer mais eventos antes de propor um lag
fixo; esta amostra, isoladamente, não comprova que um modelo seja superior ou
fisicamente correto em produção.

**Próximo passo registrado à época:** acumular e analisar novos eventos para
refinar essa hipótese.

---

## Registro histórico de configuração e resultados (14/11/2026)

Esta seção preserva um retrato documentado naquela data. Métricas, previsões e
descrições de interface abaixo não são telemetria ao vivo nem confirmação do
estado operacional atual; consulte a crontab e os logs para verificar a
operação.

### 1. Cadência Adaptativa do Boletim (Telegram)
O boletim agora envia mensagens **conforme o estado do rio**:
- **NORMAL** (cota ≤ 100 cm, chuva ≤ 5 mm, vz ≤ 1 cm/h): **60 min**
- **ATENÇÃO** (cota ≤ 200 cm, chuva ≤ 20 mm, vz ≤ 5 cm/h): **30 min**
- **ALERTA** (cota ≤ 300 cm, chuva ≤ 50 mm, vz ≤ 10 cm/h): **15 min**
- **EXTREMO** (acima disso): **5 min**
- **Piora de estado:** envia **na hora** (não espera a cadência).

### 2. Coleta Tripla de Chuva (ECMWF + GFS + UKMO)
O ARCTURUS coleta a previsão de chuva de **três fontes independentes** via Open-Meteo:
- **ECMWF** (europeu), **GFS** (americano), **UKMO** (britânico).
- Calcula a **divergência** (total e horária máxima) e a **confiança** (ALTA/MÉDIA/BAIXA).
- O pior caso é usado no alerta (conservador).

### 3. Mapa da Bacia (19 cidades)
O dashboard (`app_dash.py`) tem um mapa interativo com as **19 cidades da bacia**:
- **Cores por risco de chuva** (verde, amarelo, laranja, vermelho).
- **Datas explícitas** no popup (hoje, amanhã, depois).
- **Previsão do tempo** para cada cidade.

### 4. Modelo v11c (LightGBM + Chuva Futura) em Modo Sombra
O **v11c** foi treinado com **2 anos de dados da ANA** (2024-2026) + **87 anos de climatologia** (1939-2026) + **chuva futura proxy** (com ruído controlado). Resultados:
- **RMSE: 29.01 cm** (vs 38.16 cm da persistência).
- **Ganho: +23.97%** vs persistência.
- **Estável** em 3 folds temporais (+4.81%, +4.57%, +20.02%).
- **Bom nas cheias** (+27.68% vs persistência).
- **Sem vazamento** (auditado).
- **Em modo sombra** (logando predições, sem alertar).

### 5. Dashboard Interativo
- **Cota do rio** (ERAB/Saneamento) em tempo real.
- **Chuva da bacia** (Open-Meteo) com 3 fontes.
- **Previsão do tempo** para 19 cidades.
- **Mapa interativo** com traçado do rio (em desenvolvimento).

---

## Registro histórico do modelo e do pipeline (14/11/2026)

### 1. v11c em Modo Sombra (LightGBM + Chuva Prevista)
- **Modelo:** LightGBM (alvo = delta de cota D+1).
- **Dataset:** 14.938 registros (1980-2024), chuva observada (Zenodo) + cota (ANA) + ensemble (Open-Meteo).
- **Resultado no teste (2021-2024):**
  - **Regime normal:** RMSE=46,90 cm, MAE=22,27 cm, **Ganho=+4,96%** vs persistência.
  - **Regime de cheia (p90=156 cm):** RMSE=102,77 cm, MAE=62,25 cm, **Ganho=+11,24%** vs persistência.
  - **IC 95% do ganho:** normal [+3,02%, +6,91%], cheia [+6,94%, +19,24%] → **não inclui 0** (significativo).
- **Status:** em **modo sombra** (logando previsões, sem alertar a população).
- **Limitação:** RMSE de 1 m nas cheias (alto para EWS). Precisa de mais eventos de cheia.

### 2. Pipeline Automatizado (cron)
- **Todos os dias às 06:00**, o pipeline roda:
  1. Acumula a previsão na sombra (`log_previsoes_sombra.csv`).
  2. Audita o v8 (baseline).
  3. Revisa as features de chuva (acumulados ponderados).
  4. Re-treina o v11c.
  5. Avalia o gatilho de promoção.
- **Log:** `~/projetos/arcturus_coleta/data/pipeline_log.txt`.

### 3. Coleta Tripla de Chuva (ECMWF + GFS + UKMO)
- **Fontes:** ECMWF (europeu), GFS (americano), UKMO (britânico).
- **Divergência:** total e horária máxima.
- **Confiança:** ALTA/MÉDIA/BAIXA.
- **Ensemble:** 50 membros do ECMWF (incerteza).

### 4. Cadência Adaptativa do Boletim (Telegram)
- **NORMAL** (cota ≤ 100 cm, chuva ≤ 5 mm, vz ≤ 1 cm/h): **60 min**.
- **ATENÇÃO** (cota ≤ 200 cm, chuva ≤ 20 mm, vz ≤ 5 cm/h): **30 min**.
- **ALERTA** (cota ≤ 300 cm, chuva ≤ 50 mm, vz ≤ 10 cm/h): **15 min**.
- **EXTREMO** (acima disso): **5 min**.
- **Piora de estado:** envia **na hora**.

### 5. Dashboard Interativo
- **Cota do rio** (ERAB/Saneamento) em tempo real.
- **Chuva da bacia** (Open-Meteo) com 3 fontes.
- **Previsão do tempo** para 19 cidades.
- **Mapa interativo** com cores por risco de chuva.

### 6. Repositório
Os itens sobre organização do repositório e dependências eram uma anotação
daquele registro, não uma verificação do estado atual. O estado versionado atual
deve ser conferido pelo Git e pelos testes automatizados.

---

## Pendências registradas em 14/11/2026 (histórico)

| Item | Prioridade | Status |
|---|---|---|
| **Acumular eventos de cheia** (El Niño) | 🟢 Alta | Aguardando |
| **Reduzir RMSE de 1 m nas cheias** | 🟢 Alta | Pendente |
| **Auditar o v8** com a mesma régua do v11c | 🟡 Média | Pendente |
| **Buscar reforecast histórico** (ECMWF/GFS) | 🟡 Média | Pendente |
| **Rotacionar credenciais** (ANA_SENHA, TRINITY_TOKEN) | 🟡 Baixa | Pendente |
| **Health check** (verificar se voltou a logar) | 🟡 Baixa | Pendente |

---

O agendamento atual observado e os pontos de entrada da operação estão
descritos em [Operação contínua configurada](#operação-contínua-configurada).
Esta documentação não confirma o sucesso de uma execução em particular; para
isso, consulte os health checks e logs operacionais.
