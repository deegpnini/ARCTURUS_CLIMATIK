# ESTADO VERIFICADO (gerado por tools/gerar_estado.sh)
gerado_em: 2026-10-25 10:22:43 -03

## Git
dc551fa feat(dash): sincronizacao de relogio WSL/Windows, grafico tempo real e motor de insights (99% sincronizado)
610a479 chore(git): para de rastrear JSONs de estado (runtime)
0bf585b fix(import): adiciona bootstrap do sys.path no coletor
6b07e93 fix(historico): grava cota no historico dentro do coletor (sem side effect no import) e blinda .gitignore
46c5f87 feat(cron): migra cron_motor.sh de Termux para WSL com pipeline de 4 scripts (coleta, ensemble, classificador, Vz)
f41c107 feat(frontend): painel Dash com ensemble meteorologico (ECMWF vs Open-Meteo) e grafico de cota em tempo real
2c6267a feat(v5): painel completo com faixa de alerta, cards de regime e probabilidade, validacao de dados (cota 26 cm) e documentacao de limitacoes
4b5d233 feat: campeonato, classificador de extremos, serie longa e documentacao de limitacoes
 M puxar_historico_ana.py
M  src/modelo/backtest_multi_evento.py
AM src/modelo/treinar_classificador_extremos_final.py
 M src/relatorios/insight_operacional.py
?? assets/
?? atualizar_readme.py
?? auditoria_claude.txt
?? auditoria_para_claude.sh
?? baixar_5anos.py
?? baixar_chuva_longa.py
?? baixar_montante.py
?? buscar_coordenada.py
?? consolidar_arcturus.py
?? corrigir_baixar_resto.py
?? corrigir_dash.py

## Ambiente
Python 3.12.15
numpy==2.3.5

## Modelos e manifestos
drwxr-xr-x 2 oikos oikos    4096 2026-10-25 10:14 _investigacao
-rw-r--r-- 1 oikos oikos 3515764 2026-10-25 10:11 classificador_extremos_final.txt
-rw-r--r-- 1 oikos oikos 3515739 2026-10-25 10:08 classificador_extremos_final.txt.bak
-rw-r--r-- 1 oikos oikos  170961 2026-10-25 10:20 classificador_v2_seed0.txt
-rw-r--r-- 1 oikos oikos  127590 2026-10-25 10:20 classificador_v2_seed1.txt
-rw-r--r-- 1 oikos oikos   61625 2026-10-25 10:20 classificador_v2_seed2.txt
-rw-r--r-- 1 oikos oikos     709 2026-10-15 19:52 hashes_lf.json
-rw-r--r-- 1 oikos oikos     437 2026-10-25 10:11 manifesto_classificador_extremos.json
-rw-r--r-- 1 oikos oikos     746 2026-10-25 10:20 manifesto_classificador_v2.json
-rw-r--r-- 1 oikos oikos     829 2026-10-23 11:33 manifesto_montante.json
-rw-r--r-- 1 oikos oikos    4643 2026-10-15 19:53 manifesto_producao.json
-rw-r--r-- 1 oikos oikos     498 2026-10-23 18:45 manifesto_v4.json
-rw-r--r-- 1 oikos oikos    1674 2026-10-23 19:01 manifesto_v5.json
-rw-r--r-- 1 oikos oikos     667 2026-10-23 20:11 manifesto_v6.json
-rw-r--r-- 1 oikos oikos     639 2026-10-24 05:49 manifesto_v8.json
-rw-r--r-- 1 oikos oikos  268230 2026-10-15 19:25 modelo_delta_1h.txt
-rw-r--r-- 1 oikos oikos  446222 2026-10-23 16:04 modelo_delta_1h_com_montante.txt
-rw-r--r-- 1 oikos oikos   54257 2026-10-23 18:38 modelo_delta_1h_final.txt
-rw-r--r-- 1 oikos oikos  288367 2026-10-23 18:45 modelo_delta_1h_v4_com_montante.txt
-rw-r--r-- 1 oikos oikos  224800 2026-10-23 18:45 modelo_delta_1h_v4_sem_montante.txt
-rw-r--r-- 1 oikos oikos  214743 2026-10-23 19:01 modelo_delta_1h_v5_com_montante.txt
-rw-r--r-- 1 oikos oikos  232325 2026-10-23 19:01 modelo_delta_1h_v5_sem_montante.txt
-rw-r--r-- 1 oikos oikos  276167 2026-10-23 20:11 modelo_delta_1h_v6_final.txt
-rw-r--r-- 1 oikos oikos  461591 2026-10-24 05:49 modelo_delta_1h_v8_final.txt
-rw-r--r-- 1 oikos oikos  188105 2026-10-15 19:25 modelo_delta_3h.txt
-rw-r--r-- 1 oikos oikos  441568 2026-10-23 16:04 modelo_delta_3h_com_montante.txt
-rw-r--r-- 1 oikos oikos  123198 2026-10-23 19:01 modelo_delta_3h_v5_com_montante.txt
-rw-r--r-- 1 oikos oikos  123065 2026-10-23 19:01 modelo_delta_3h_v5_sem_montante.txt
-rw-r--r-- 1 oikos oikos  136519 2026-10-23 20:11 modelo_delta_3h_v6_final.txt
-rw-r--r-- 1 oikos oikos  183286 2026-10-24 05:49 modelo_delta_3h_v8_final.txt
-rw-r--r-- 1 oikos oikos  189608 2026-10-15 19:25 modelo_delta_6h.txt
-rw-r--r-- 1 oikos oikos  440974 2026-10-23 16:04 modelo_delta_6h_com_montante.txt
-rw-r--r-- 1 oikos oikos   91339 2026-10-23 19:01 modelo_delta_6h_v5_com_montante.txt
-rw-r--r-- 1 oikos oikos   99987 2026-10-23 19:01 modelo_delta_6h_v5_sem_montante.txt
-rw-r--r-- 1 oikos oikos  129291 2026-10-23 20:11 modelo_delta_6h_v6_final.txt
-rw-r--r-- 1 oikos oikos  115768 2026-10-24 05:49 modelo_delta_6h_v8_final.txt

## Manifesto do classificador v2
{
  "features": [
    "cota",
    "d1",
    "d3",
    "max3",
    "sin",
    "cos",
    "chuva_1d",
    "chuva_2d",
    "chuva_3d",
    "chuva_5d",
    "chuva_10d",
    "chuva_30d",
    "chuva_max_ponto_2d"
  ],
  "limiar_cheia_cm_media_diaria": 300.0,
  "limiares_por_orcamento_ano": {
    "2": 0.1760181418023005,
    "5": 0.09024389868713129,
    "10": 0.056156174148512754,
    "20": 0.03142369017141961
  },
  "iteracoes": [
    97,
    72,
    34
  ],
  "treino": "<2000",
  "validacao": "2000-2009",
  "teste": ">=2010",
  "modelos": [
    "classificador_v2_seed0.txt",
    "classificador_v2_seed1.txt",
    "classificador_v2_seed2.txt"
  ],
  "uso": "média das 3 sementes; limiar vale só para esta média",
  "gerado_em": "2026-10-25"
}
## Dados
dataset 15min: 2023-12-04 10:00:00 -> 2026-09-21 18:45:00 | cota max: 312.0
ERAB: {'fonte': 'Tubarão Saneamento (ERAB)', 'cota_metros': 0.73, 'cota_cm': 73.0, 'data_extracao': '2026-10-25T10:15:11.974714'}
