# Avaliação Pareada dos Modelos — ARCTURUS CLIMATIK (Etapa 3)

## Veredito Objetivo por Horizonte (Sem Opinião, Apenas Dados Pareados)

- **1h (`n = 282` origens pareadas):** Menor MAE = **`v8_final_bacia`** (`4.616 cm`, viés `-0.825 cm`) | Menor RMSE = **`fisica_3bracos`** (`7.152 cm`).
- **3h (`n = 280` origens pareadas):** Menor MAE = **`v8_final_bacia`** (`12.032 cm`, viés `-2.933 cm`) | Menor RMSE = **`fisica_3bracos`** (`17.708 cm`).
- **6h (`n = 268` origens pareadas):** Menor MAE = **`v8_final_bacia`** (`21.299 cm`, viés `-5.494 cm`) | Menor RMSE = **`fisica_3bracos`** (`28.836 cm`).
- **24h Sombra (`n = 919` origens pareadas):** Menor MAE = **`v11c_shadow_24h`** (`57.188 cm`, RMSE `70.836 cm`, viés `+2.754 cm`).

## Tabela Completa (`data/avaliacao_modelos.csv`)

| grupo_avaliacao | horizonte | modelo | n_pares | mae_cm | rmse_cm | vies_cm | p90_erro_abs_cm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PROSPECTIVO_CURTO_PAREADO | 1h | persistencia | 282 | 5.397 | 8.046 | 0.908 | 10.9 |
| PROSPECTIVO_CURTO_PAREADO | 1h | v8_final_bacia | 282 | 4.616 | 7.167 | -0.825 | 8.78 |
| PROSPECTIVO_CURTO_PAREADO | 1h | fisica_3bracos | 282 | 4.811 | 7.152 | 1.437 | 9.28 |
| PROSPECTIVO_CURTO_PAREADO | 3h | persistencia | 280 | 14.114 | 19.359 | 1.936 | 27.1 |
| PROSPECTIVO_CURTO_PAREADO | 3h | v8_final_bacia | 280 | 12.032 | 17.822 | -2.933 | 26.038 |
| PROSPECTIVO_CURTO_PAREADO | 3h | fisica_3bracos | 280 | 13.18 | 17.708 | 3.961 | 27.535 |
| PROSPECTIVO_CURTO_PAREADO | 6h | persistencia | 268 | 24.496 | 31.543 | 3.653 | 47.0 |
| PROSPECTIVO_CURTO_PAREADO | 6h | v8_final_bacia | 268 | 21.299 | 29.465 | -5.494 | 49.157 |
| PROSPECTIVO_CURTO_PAREADO | 6h | fisica_3bracos | 268 | 22.815 | 28.836 | 9.723 | 44.672 |
| SOMBRA_24H_PAREADO | 24h | persistencia_24h | 919 | 58.55 | 71.469 | 5.864 | 114.0 |
| SOMBRA_24H_PAREADO | 24h | v11c_shadow_24h | 919 | 57.188 | 70.836 | 2.754 | 119.26 |
| SOMBRA_6H_PAREADO_V8 | 6h | persistencia (subamostra v11c) | 268 | 24.496 | 31.543 | 3.653 | 47.0 |
| SOMBRA_6H_PAREADO_V8 | 6h | v8_final_bacia (subamostra v11c) | 268 | 21.299 | 29.465 | -5.494 | 49.157 |
| SOMBRA_6H_PAREADO_V8 | 6h | fisica_3bracos (subamostra v11c) | 268 | 22.815 | 28.836 | 9.723 | 44.672 |
| SOMBRA_6H_PAREADO_V8 | 6h | v11c_fisica_shadow_6h | 268 | 16.062 | 21.028 | 0.852 | 34.003 |
