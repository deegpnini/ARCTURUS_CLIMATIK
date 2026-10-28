- 2026-10-26: ponto removido de resultados/historico_previsoes.csv: 2026-10-25 21:54, cota 127 cm (antes: 86 cm às 21:46). Motivo: não consta no SQLite (101 cm às 22:00; 85 cm antes) e a chuva nas cabeceiras foi ~0,6 mm. Causa não identificada (erro de leitura, operação de barragem ou pulso real não foram distinguidos).

## Flags de qualidade das leituras

As novas leituras coletadas da Tubarão Saneamento e gravadas no histórico/SQLite
recebem uma flag `qc`. As flags descrevem a qualidade da leitura, não alteram
nem removem o valor original:

- `VALIDO`: valor numérico finito e positivo, sem salto superior ao critério
  automático em relação à leitura anterior disponível.
- `SUSPEITO`: salto absoluto **maior que 30 cm** em relação à leitura anterior.
  É uma heurística operacional, não prova de erro; manter o valor para revisão.
- `CORROMPIDO`: valor extraído que não pode ser interpretado como número finito
  positivo (incluindo texto inesperado, NaN ou valor ausente em uma tentativa de
  leitura).
- `MANUAL`: classificação atribuída por revisão humana; deve ser preservada
  pelo pipeline automático.

O critério de salto é aplicado durante a ingestão em `monitor_continuo.py` e
revalidado na gravação SQLite. `monitor_derivada.py` permanece inalterado:
embora o salto possa ser usado como sinalizador, o requisito de preservá-lo
prevalece nesta alteração. Uma leitura sem elemento de cota no site não cria
uma amostra; um valor presente, mas inválido, é registrado como
`CORROMPIDO`. Registros já existentes não são apagados.
