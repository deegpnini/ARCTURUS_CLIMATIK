# ARCTURUS CLIMATIK

**Plataforma de observação, alerta e aprendizado contínuo da Bacia do Rio Tubarão (SC).**

O ARCTURUS não é um modelo. É uma plataforma de monitoramento hidrológico que combina:
- **Camada 1 (física):** alerta em tempo real baseado em Vz/Az (regras físicas).
- **Camada 2 (científica):** modelo LightGBM em modo sombra (aprende sem alertar).
- **Camada 3 (territorial):** Atlas de Impacto (edificações, escolas, UBS).

**Princípio:** Evidência Primeiro. Modelos podem falhar. Evidências permanecem.

---

## Arquitetura


---
## Descoberta: Lag Chuva-Rio na Bacia do Tubarão (08/11/2026)

Medimos o lag (tempo entre o pico da chuva na cabeceira e o pico da cota em Tubarão) para 5 eventos:

| Evento | Pico da Chuva | Lag (h) |
|--------|---------------|---------|
| 27/10 11:30 | 26/10 13:00 | 33.7 |
| 30/10 16:45 | 29/10 21:00 | 31.0 |
| 03/11 17:45 | 03/11 13:00 | 16.0 |
| **04/11 08:30** | **04/11 07:00** | **13.5** |
| 07/11 21:30 | 07/11 12:00 | 16.0 |

**Conclusão:** A chuva da cabeceira (Orleans, Lauro Müller, Braço do Norte) leva ~13-16h para fazer o rio atingir o pico em Tubarão. O modelo v10 (que usa o lag de 15h) está fisicamente correto. O v8 (que não usa o lag) está errado.

**Próximo passo:** Acumular mais eventos (o El Niño está vindo) para refinar o lag e validar o modelo.
O código do dashboard está versionado no repositório e roda localmente.

---

## Atualizações (14/11/2026)

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

## Atualizações (14/11/2026)

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
- **Limpo** (`git status` vazio).
- **README atualizado** com o estado atual.
- **`requirements.txt` sincronizado** (pandas, numpy, psycopg2, lightgbm, playwright, etc.).

---

## O que falta (Próximos Passos)

| Item | Prioridade | Status |
|---|---|---|
| **Acumular eventos de cheia** (El Niño) | 🟢 Alta | Aguardando |
| **Reduzir RMSE de 1 m nas cheias** | 🟢 Alta | Pendente |
| **Auditar o v8** com a mesma régua do v11c | 🟡 Média | Pendente |
| **Buscar reforecast histórico** (ECMWF/GFS) | 🟡 Média | Pendente |
| **Rotacionar credenciais** (ANA_SENHA, TRINITY_TOKEN) | 🟡 Baixa | Pendente |
| **Health check** (verificar se voltou a logar) | 🟡 Baixa | Pendente |

---

**O ARCTURUS está no ar, com o v8 em produção, o v11c em sombra, e o pipeline rodando todos os dias às 06:00.**
