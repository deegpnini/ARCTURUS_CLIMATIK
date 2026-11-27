# Avaliação Pareada dos Modelos — ARCTURUS CLIMATIK (Etapa 3)

## Veredito Objetivo por Horizonte (Sem Opinião, Apenas Dados Pareados)

- **1h (`n = 282` origens pareadas):** Menor MAE = **`v8_final_bacia`** (`4.616 cm`, viés `-0.825 cm`) | Menor RMSE = **`fisica_3bracos`** (`7.152 cm`).
- **3h (`n = 282` origens pareadas):** Menor MAE = **`v8_final_bacia`** (`12.060 cm`, viés `-3.026 cm`) | Menor RMSE = **`fisica_3bracos`** (`17.679 cm`).
- **6h (`n = 271` origens pareadas):** Menor MAE = **`v8_final_bacia`** (`21.214 cm`, viés `-5.585 cm`) | Menor RMSE = **`fisica_3bracos`** (`28.702 cm`).
- **24h Sombra (`n = 926` origens pareadas):** Menor MAE = **`v11c_shadow_24h`** (`57.055 cm`, RMSE `70.651 cm`, viés `+3.032 cm`).

## Tabela Completa (`data/avaliacao_modelos.csv`)

| grupo_avaliacao | horizonte | modelo | n_pares | mae_cm | rmse_cm | vies_cm | p90_erro_abs_cm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PROSPECTIVO_CURTO_PAREADO | 1h | persistencia | 282 | 5.397 | 8.046 | 0.908 | 10.9 |
| PROSPECTIVO_CURTO_PAREADO | 1h | v8_final_bacia | 282 | 4.616 | 7.167 | -0.825 | 8.78 |
| PROSPECTIVO_CURTO_PAREADO | 1h | fisica_3bracos | 282 | 4.811 | 7.152 | 1.437 | 9.28 |
| PROSPECTIVO_CURTO_PAREADO | 3h | persistencia | 282 | 14.113 | 19.327 | 1.823 | 27.0 |
| PROSPECTIVO_CURTO_PAREADO | 3h | v8_final_bacia | 282 | 12.06 | 17.812 | -3.026 | 25.958 |
| PROSPECTIVO_CURTO_PAREADO | 3h | fisica_3bracos | 282 | 13.176 | 17.679 | 3.843 | 27.525 |
| PROSPECTIVO_CURTO_PAREADO | 6h | persistencia | 271 | 24.362 | 31.399 | 3.476 | 47.0 |
| PROSPECTIVO_CURTO_PAREADO | 6h | v8_final_bacia | 271 | 21.214 | 29.344 | -5.585 | 48.952 |
| PROSPECTIVO_CURTO_PAREADO | 6h | fisica_3bracos | 271 | 22.677 | 28.702 | 9.502 | 44.53 |
| SOMBRA_24H_PAREADO | 24h | persistencia_24h | 926 | 58.288 | 71.229 | 6.001 | 114.0 |
| SOMBRA_24H_PAREADO | 24h | v11c_shadow_24h | 926 | 57.055 | 70.651 | 3.032 | 119.26 |
| SOMBRA_6H_PAREADO_V8 | 6h | persistencia (subamostra v11c) | 271 | 24.362 | 31.399 | 3.476 | 47.0 |
| SOMBRA_6H_PAREADO_V8 | 6h | v8_final_bacia (subamostra v11c) | 271 | 21.214 | 29.344 | -5.585 | 48.952 |
| SOMBRA_6H_PAREADO_V8 | 6h | fisica_3bracos (subamostra v11c) | 271 | 22.677 | 28.702 | 9.502 | 44.53 |
| SOMBRA_6H_PAREADO_V8 | 6h | v11c_fisica_shadow_6h | 271 | 16.091 | 21.009 | 0.637 | 33.67 |

## Antecipação de Cruzamento de Limiares por Episódio (`data/avaliacao_alertas_episodios.csv`)

| serie | horizonte | modelo | limiar_cm | episodios_reais | detectados | pod_pct | falsos_alarmes | far_pct | antecedencia_media_h |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SERIE_LONGA_V8_02NOV_26NOV | 1h | v8_final_bacia | 150 | 9 | 3 | 33.3 | 2 | 40.0 | 0.67 |
| SERIE_LONGA_V8_02NOV_26NOV | 1h | v8_final_bacia | 200 | 4 | 0 | 0.0 | 1 | 100.0 | nan |
| SERIE_LONGA_V8_02NOV_26NOV | 1h | v8_final_bacia | 250 | 3 | 1 | 33.3 | 0 | 0.0 | 1.0 |
| SERIE_LONGA_V8_02NOV_26NOV | 3h | v8_final_bacia | 150 | 7 | 5 | 71.4 | 1 | 16.7 | 2.45 |
| SERIE_LONGA_V8_02NOV_26NOV | 3h | v8_final_bacia | 200 | 4 | 0 | 0.0 | 1 | 100.0 | nan |
| SERIE_LONGA_V8_02NOV_26NOV | 3h | v8_final_bacia | 250 | 4 | 1 | 25.0 | 0 | 0.0 | 0.25 |
| SERIE_LONGA_V8_02NOV_26NOV | 6h | v8_final_bacia | 150 | 8 | 2 | 25.0 | 0 | 0.0 | 1.62 |
| SERIE_LONGA_V8_02NOV_26NOV | 6h | v8_final_bacia | 200 | 4 | 1 | 25.0 | 1 | 50.0 | 1.0 |
| SERIE_LONGA_V8_02NOV_26NOV | 6h | v8_final_bacia | 250 | 3 | 0 | 0.0 | 1 | 100.0 | nan |
| BANCADA_PAREADA_23NOV_26NOV | 1h | persistencia | 150 | 2 | 0 | 0.0 | 0 | 0.0 | nan |
| BANCADA_PAREADA_23NOV_26NOV | 1h | persistencia | 200 | 1 | 0 | 0.0 | 0 | 0.0 | nan |
| BANCADA_PAREADA_23NOV_26NOV | 1h | v8_final_bacia | 150 | 2 | 1 | 50.0 | 1 | 50.0 | 0.27 |
| BANCADA_PAREADA_23NOV_26NOV | 1h | v8_final_bacia | 200 | 1 | 0 | 0.0 | 0 | 0.0 | nan |
| BANCADA_PAREADA_23NOV_26NOV | 1h | fisica_3bracos | 150 | 2 | 0 | 0.0 | 0 | 0.0 | nan |
| BANCADA_PAREADA_23NOV_26NOV | 1h | fisica_3bracos | 200 | 1 | 1 | 100.0 | 0 | 0.0 | 0.75 |
| BANCADA_PAREADA_23NOV_26NOV | 3h | persistencia | 150 | 2 | 0 | 0.0 | 0 | 0.0 | nan |
| BANCADA_PAREADA_23NOV_26NOV | 3h | persistencia | 200 | 1 | 0 | 0.0 | 0 | 0.0 | nan |
| BANCADA_PAREADA_23NOV_26NOV | 3h | v8_final_bacia | 150 | 2 | 2 | 100.0 | 1 | 33.3 | 2.62 |
| BANCADA_PAREADA_23NOV_26NOV | 3h | v8_final_bacia | 200 | 1 | 0 | 0.0 | 0 | 0.0 | nan |
| BANCADA_PAREADA_23NOV_26NOV | 3h | fisica_3bracos | 150 | 2 | 2 | 100.0 | 1 | 33.3 | 1.51 |
| BANCADA_PAREADA_23NOV_26NOV | 3h | fisica_3bracos | 200 | 1 | 1 | 100.0 | 0 | 0.0 | 0.75 |
| BANCADA_PAREADA_23NOV_26NOV | 6h | persistencia | 150 | 2 | 0 | 0.0 | 0 | 0.0 | nan |
| BANCADA_PAREADA_23NOV_26NOV | 6h | persistencia | 200 | 1 | 0 | 0.0 | 0 | 0.0 | nan |
| BANCADA_PAREADA_23NOV_26NOV | 6h | v8_final_bacia | 150 | 2 | 1 | 50.0 | 0 | 0.0 | 0.25 |
| BANCADA_PAREADA_23NOV_26NOV | 6h | v8_final_bacia | 200 | 1 | 0 | 0.0 | 0 | 0.0 | nan |
| BANCADA_PAREADA_23NOV_26NOV | 6h | fisica_3bracos | 150 | 2 | 2 | 100.0 | 1 | 33.3 | 4.35 |
| BANCADA_PAREADA_23NOV_26NOV | 6h | fisica_3bracos | 200 | 1 | 1 | 100.0 | 0 | 0.0 | 0.77 |
