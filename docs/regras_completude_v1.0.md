# REGRAS DE COMPLETUDE — ARCTURUS HIDRO v1.0
# Dataset Supervisionado 15min
# Data: 21/09/2026

## PRINCÍPIO-MÃE (NEXUS Cético)
Ausência é ausência. Não transformamos buraco em dado.

## REGRA 1 — Unidade do Exemplo
- 1 linha = estado do sistema em 1 instante t
- Alinhado em grade de 15 min (00:00, 00:15, 00:30, ...)
- Desalinhamento > 7min: descartar

## REGRA 2 — Componentes Obrigatórios (target)
- dataset_1h: cota(t+1h) = cota em +4 registros
- dataset_3h: cota(t+3h) = cota em +12 registros
- dataset_6h: cota(t+6h) = cota em +24 registros
- Target ausente: linha excluída DAQUELE modelo
- NUNCA imputar target

## REGRA 3 — Componentes Críticos (features)
- cota_em_t: obrigatória
- cota_t-1h: obrigatória se delta_1h for usado
- cota_t-3h: obrigatória se delta_3h for usado
- cota_t-24h: obrigatória pra média móvel 24h

## REGRA 4 — Componentes Flexíveis (podem ser NaN)
- chuva_*: se <90% dos pontos na janela, NaN
- LightGBM trata NaN nativamente
- Melhor NaN que dado inventado

## REGRA 5 — Critério de Janelas de Tempo
- 15min: 1/1 pontos (100%)
- 1h: 4/4 pontos (100%)
- 3h: 11/12 pontos (90%)
- 6h: 22/24 pontos (90%)
- 12h: 44/48 pontos (90%)
- 24h: 87/96 pontos (90%)
- 48h: 173/192 pontos (90%)

## REGRA 6 — Controle de Gaps (corrigida)
- ≤ 15min: normal (esperado)
- > 15min e ≤ 30min: 1 leitura faltando — tolerável, marcar flag
- > 30min: quebra de continuidade (features dependentes ficam NaN)
- NUNCA interpolar gap > 30min

Operacionalização precisa:
  "se 2 leituras estão a 30min, isso são 2 intervalos com 1 leitura faltando"
  "não é 1 gap de 30min"
  "contar: gap_intervalos = (delta_minutos / 15) - 1"
  "ex: delta=30min -> 1 intervalo faltando"
  "ex: delta=45min -> 2 intervalos faltando"

## REGRA 7 — Features a Construir
NÍVEL:
- cota_t (obrigatória)
- lags: 15m, 30m, 1h, 3h, 6h, 12h, 24h
- deltas: 15m, 1h, 3h
- aceleracao_1h
- std_12h, max_24h, min_24h

CHUVA:
- acumulados: 15m, 1h, 3h, 6h, 12h, 24h, 48h
- upstream com shift hidrológico
- chuva_orleans_t-4h (tempo de trânsito)

TEMPORAL:
- hora_sin, hora_cos
- dia_ano_sin, dia_ano_cos

QUALIDADE:
- gap_anterior_minutos
- cobertura_chuva_24h_pct

## REGRA 8 — Targets
- target_cota_1h: cota em t+4 registros
- target_cota_3h: cota em t+12 registros
- target_cota_6h: cota em t+24 registros

## REGRA 9 — Divisão Temporal
- treino: período inicial
- validação: período médio
- teste: período mais recente
- NUNCA train_test_split aleatório
- Eventos: treino e teste não podem compartilhar evento

## REGRA 10 — Auditoria Antes de Treinar
Produzir:
- linhas totais por horizonte
- features NaN por coluna
- período temporal
- número de eventos de cheia
- distribuição de cota (percentis)
- densidade de alvos extremos

## REGRA 11 — Densidade de Eventos
- verificar % targets > P90, P95, P99
- se densidade baixa: sample_weight ou métrica nos extremos

## REGRAS-MÃE
- ausência é ausência
- target ausente: linha excluída
- feature ausente: NaN (LightGBM lida)
- gap > 30min: quebra de continuidade
- split temporal: sempre cronológico
- auditoria antes do treino: obrigatória
