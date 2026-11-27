# Resultados e Rastreabilidade — ARCTURUS CLIMATIK

Atualizado em: `2026-11-27 19:14:04 -0300` | Commit de referência: `a97f950`

> Nota metodológica: `cota_altimetrica_m` e `rio_m` permanecem fora de cálculos hidrológicos e sem equivalência assumida como nível d'água até confirmação oficial da coluna na fonte.

## 1. Hashes SHA-256 dos Dados de Entrada (prefixo 16 hex)

| Arquivo de entrada | SHA-256 (16 hex) |
|---|---|
| `data/historico_defesacivil_bacia.jsonl` | `8494fcdb474d2826` |
| `data/ana_longa84580000.csv` | `4c9b14a42cb42528` |

## 2. Registros de Medição e Validação

| Métrica / Resultado | Valor reportado | Script | Commit | Entrada (hash 16 hex) |
|---|---|---|---|---|
| Suíte de testes automatizados (`pytest`) | `75 passed, 0 failed` | `tests/test_model_runner_freshness.py` (75 testes) | `a97f950` | `n/a (testes unitários/integração)` |
| Lag até o pico — mediana `DCSC-00122` | `15.3 h` | `src/analise/lag_chuva_para_erab.py` | `a97f950` | `8494fcdb474d2826` |
| Lag até o pico — mediana `DCSC-00151` | `18.1 h` | `src/analise/lag_chuva_para_erab.py` | `a97f950` | `8494fcdb474d2826` |
| Lag até o pico — mediana `DCSC-00048` | `22.8 h` | `src/analise/lag_chuva_para_erab.py` | `a97f950` | `8494fcdb474d2826` |
| Lag até o pico — mediana `DCSC-00046` / `00054` / `00075` | `28.7 h` | `src/analise/lag_chuva_para_erab.py` | `a97f950` | `8494fcdb474d2826` |
| Correlação Orleans (`15969` h) vs. `84580000` (`29479` h) | `Sem sobreposicao suficiente` | `src/analise/lag_montante_84580000.py` | `a97f950` | `4c9b14a42cb42528` |
