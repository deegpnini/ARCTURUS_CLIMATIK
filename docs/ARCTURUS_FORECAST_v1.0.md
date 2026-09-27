# ARCTURUS_FORECAST v1.0
# Data: 22/09/2026
# Status: especificacao definida (nao publicado)

## ARQUITETURA

BASE: persistencia (cota(t))
MODELO: LightGBM
TARGET: delta_cota = cota(t+h) - cota(t)
RECONSTRUCAO: previsao = cota(t) + delta_previsto
HORIZONTES: 1h, 3h, 6h

## EVIDENCIA HISTORICA (27 eventos)

DELTA vs PERSIST:
  1h: 26/27 vitorias
  3h: 26/27 vitorias
  6h: 24/27 vitorias

DELTA vs ABS:
  1h: 19/27 vitorias
  3h: 18/27 vitorias
  6h: 20/27 vitorias

BOOTSTRAP: 10.000 por evento
IC95%: acima de zero em todos comparativos

## ROBUSTEZ

LEAVE_P99_OUT: vantagem permanece
SEVERIDADE P95/P99: inconclusiva (amostra insuficiente)

## TESTE OPERACIONAL 446

STATUS: avaliacao externa
RESULTADO: DELTA venceu 1h, 3h, 6h
LIMITACAO: gap 195 min, features indisponiveis

## LIMITACOES

- Um posto (84580000)
- 27 eventos historicos
- Um caso fora da faixa (446)
- Nao demonstrada generalizacao universal
- Mecanismo de extrapolacao ainda e hipotese
- Direcao correta so testada em 446 (nao nos 27)
- Correlacao pico vs MAE e exploratoria (n=27)

## PROXIMO

SHADOW MODE operacional
