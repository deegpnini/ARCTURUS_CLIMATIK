# Ensemble de Especialistas — ANA diária

## Fonte e alvo

O treino e a validação deste ensemble usam **exclusivamente**
`data/ana_longa84580000.csv`. A coluna de cota é interpretada em centímetros,
conforme a especificação da série; não há conversão de unidade. Os dados
operacionais da ERAB não são lidos pelo script.

Uma cheia é um episódio de dias consecutivos em que a média diária é
**≥300 cm**. O alvo dos modelos LightGBM é binário: se a cota média do dia
seguinte será ≥300 cm. As features são valores ANA observados até o dia atual
(cota, variações de 1/3/7 dias, aceleração diária, máximas móveis e calendário).
Cada amostra de treino pertence à janela de um evento do especialista: os sete
dias anteriores e os dias do episódio. Cotas ausentes não são interpoladas.

## Tipos e contagens identificados

O período com cota observada vai de **1939-05-26 a 2026-01-31**, com 30.977
leituras válidas e 711 dias sem leitura no intervalo diário completo. Foram
identificados **220 episódios** ≥300 cm.

- **Relâmpago:** Vz no primeiro dia do episódio >50 cm/dia — **210 eventos**.
- **Gradual:** Vz no primeiro dia do episódio entre 12 e 50 cm/dia, inclusive
  — **10 eventos**.
- **Inverno:** pico diário em junho, julho ou agosto — **33 eventos**.
- **Verão:** pico diário entre dezembro e março — **105 eventos**.

As categorias de estação se sobrepõem às categorias por Vz. Episódios sem
medição válida no dia anterior não recebem rótulo relâmpago/gradual, mas ainda
podem receber rótulo sazonal.

## LOEO por evento e comparação com fallback

Cada fold deixa um episódio inteiro de fora. O treino daquele fold contém
somente as janelas ANA dos demais eventos do mesmo especialista. A avaliação é
agregada sobre as predições out-of-fold (OOF), com limiar de classificação 0,5.
O fallback Vz/Az extrapola a cota diária como `cota + Vz + 0,5 × Az` e prevê
cheia quando essa projeção atinge 300 cm.

| Especialista | Eventos / folds | PR-AUC LOEO (modelo / fallback) | F1 OOF (modelo / fallback) | Decisão |
|---|---:|---:|---:|---|
| Relâmpago | 210 / 210 | 0,474 / 0,315 | 0,194 / 0,455 | Fallback Vz/Az |
| Gradual | 10 / 10 | 0,882 / 0,491 | 0,842 / 0,667 | LightGBM |
| Inverno | 33 / 33 | 0,572 / 0,356 | 0,409 / 0,504 | Fallback Vz/Az |
| Verão | 105 / 105 | 0,426 / 0,313 | 0,210 / 0,449 | Fallback Vz/Az |

O modelo só atua quando tem ao menos quatro folds válidos e supera o fallback
em **PR-AUC e F1**. Assim, somente o especialista gradual fica ativo; nos outros
casos o roteador usa o fallback Vz/Az. Os quatro LightGBMs finais foram
treinados apenas nos eventos ANA correspondentes e salvos em
`modelos/especialistas/`. O relatório OOF/fold a fold está em
`resultados/ensemble_especialistas.json`.

## Execução e limitações

Execute da raiz do projeto com `source .venv/bin/activate` e
`python -m src.modelo.ensemble_especialistas`. A função `prever_cheia(features)`
carrega o registro validado e escolhe um especialista ativo ou o fallback.

O modo permanece **experimental/sombra** e não está conectado ao Dash, ao
Telegram nem a alertas públicos. A série diária tem lacunas e não representa
medições horárias. A validação estima desempenho somente nas janelas dos
episódios históricos identificados, não demonstra generalização para novas
cheias nem constitui validação operacional de segurança.
