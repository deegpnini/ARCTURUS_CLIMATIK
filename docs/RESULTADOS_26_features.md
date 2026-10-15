# Resultados do modelo de producao (26 features, sem `vazao`)

Backtest leave-one-event-out: 27 eventos da estacao 84580000, 4 execucoes (treino padrao e sementes 11, 22, 33). V/E/D = vitorias/empates/derrotas do delta, com margem de empate por horizonte (persistencia 0,10/0,20/0,34 cm; absoluto 0,10/0,14/0,24 cm).

| Horizonte | Delta vs persistencia (vitorias de 27) | Delta vs absoluto (vitorias de 27) | MAE medio delta (cm) | MAE medio persistencia (cm) | MAE medio absoluto (cm) |
|---|---|---|---|---|---|
| 1h | 26-27 | 18-20 | 2.09-2.10 | 3.88 | 2.42-2.47 |
| 3h | 26-26 | 17-22 | 6.15-6.20 | 10.08 | 6.85-7.02 |
| 6h | 23-24 | 16-20 | 10.07-10.35 | 17.11 | 11.63-11.80 |

Execucao padrao (V/E/D):
- 1h: vs persistencia 26/0/1 | vs absoluto 19/4/4
- 3h: vs persistencia 26/0/1 | vs absoluto 22/1/4
- 6h: vs persistencia 23/2/2 | vs absoluto 16/6/5

## Custo de remover `vazao` (4 pares com/sem, mesma semente)

- 1h: -0.001 cm no MAE do delta (sem - com), IC95% [-0.021, +0.016]; positivo = piora sem vazao
- 3h: -0.060 cm no MAE do delta (sem - com), IC95% [-0.131, +0.004]; positivo = piora sem vazao
- 6h: +0.205 cm no MAE do delta (sem - com), IC95% [+0.035, +0.410]; positivo = piora sem vazao

## Limitacoes

- Uma estacao e 27 eventos. Acima do P95 dos picos (297 cm) ha 2 eventos e acima do P99 (310 cm) 1: sem inferencia para eventos severos.
- A contagem de vitorias oscila 3 a 4 eventos so por semente; por isso relatamos faixas.
- O maior pico do treino e 312 cm. O evento de 22/09/2026 (446 cm na primeira leitura apos um intervalo de 4h15 sem dados, ja em recessao) esta fora dessa faixa; o pico real e desconhecido (>= 446 cm).
- O teste do 446 usou poucas features e e um unico caso.
