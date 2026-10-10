"""
Cria README.md — parte 1 (identidade + problema + solucao + modelo + validacao)
"""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

readme = """# ARCTURUS CLIMATIK

Sistema de previsao de nivel de rio para Santa Catarina, com foco em alerta antecipado de enchentes.

**Nao substitui a Defesa Civil nem o CEMADEN.** Complementa, gerando previsao local com 1h, 3h e 6h de antecedencia.

---

## O problema

Santa Catarina tem historico severo de enchentes. Em setembro de 2026, o estado entrou em calamidade publica:

- 57 municipios com ocorrencias
- 4 em situacao de emergencia (Timbe do Sul, Turvo, Criciuma, Sao Joaquim)
- 42 desabrigados, 344 desalojados, 403 habitacoes afetadas
- Mais de 200 resgates
- Rio Tubarao atingiu o maior valor da serie disponivel

A lacuna: sistemas existentes operam com dados de chuva e modelos regionais. Nao ha previsao local de nivel de rio com antecedencia curta para bacias menores.

---

## A solucao

Modelo de machine learning que:

1. Coleta telemetria de 15 minutos da API oficial da ANA (HidroWebService)
2. Constroi features hidrologicas (lags, deltas, chuvas acumuladas, sazonalidade)
3. Preve a variacao do nivel do rio (delta), nao o valor absoluto
4. Reconstroi: previsao = cota_atual + delta_previsto
5. Gera alerta com 1h, 3h e 6h de antecedencia

**Diferencial tecnico:** o modelo preve delta (variacao), nao cota absoluta. Isso resolve a limitacao de arvores de decisao travarem na media do treino — o modelo generaliza para eventos fora da faixa conhecida.

---

## O modelo

| Item | Valor |
|---|---|
| Algoritmo | LightGBM |
| Target | Delta (cota futura - cota atual) |
| Horizontes | 1h, 3h, 6h |
| Features | 26 |
| Estacao de treino | 84580000 (Rio do Pouso / Tubarao) |
| Bacia | Rio Tubarao |
| num_boost_round | 156 (1h), 84 (3h), 74 (6h) |

**Features:** cota atual, lags (15min a 24h), deltas (15min, 1h, 3h), aceleracao, estatisticas moveis 12h, chuvas acumuladas (15min a 48h), componentes ciclicos.

---

## Validacao

**Protocolo:** leave-one-event-out em 27 eventos historicos.

**Comparacao vs persistencia (baseline trivial: prever cota atual):**

| Horizonte | Ganho | MAE do modelo |
|---|---|---|
| 1h | 26/27 eventos | 1,63 cm |
| 3h | 26/27 eventos | 4,64 cm |
| 6h | 24/27 eventos | 7,24 cm |

**Teste operacional (evento de 22/09/2026, leitura de 446 cm):**

> **Importante:** o valor de 446 cm e a primeira leitura apos um gap de 4h15min na telemetria. Ele ja esta em recessao (446 -> 442 -> 436 -> 430 cm nas primeiras horas). O pico real ocorreu durante o gap e e desconhecido (>= 446 cm).

| Horizonte | Erro persistencia | Erro delta | Erro absoluto |
|---|---|---|---|
| 1h | 22 cm | 19 cm | 187 cm |
| 3h | 48 cm | 42 cm | 191 cm |
| 6h | 71 cm | 53 cm | 264 cm |

**Resultado:** delta venceu nos 3 horizontes. Acertou a direcao da recessao, capturou 12% a 26% da magnitude.
"""

with open("README.md", "w", encoding="utf-8") as f:
    f.write(readme)

print(f"[OK] README.md parte 1 escrita ({Path('README.md').stat().st_size} bytes)")
