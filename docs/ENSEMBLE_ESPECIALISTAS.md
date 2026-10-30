# Ensemble de Especialistas — modo experimental

O módulo `src/modelo/ensemble_especialistas.py` treina quatro regressores
LightGBM para prever a cota em 1 hora: cheia relâmpago, cheia gradual, inverno
e verão. Cada fold Leave-One-Event-Out (LOEO) deixa de fora um evento inteiro;
o LightGBM de cada fold é treinado exclusivamente com as janelas dos demais
eventos daquele especialista. O comparador é a extrapolação Vz/Az
(`cota + delta_60m + 0,5 × aceleracao_1h`).

## Eventos e limites dos dados

A série ANA diária cobre **1939-05-26 a 2026-01-31**. Para resumir eventos
históricos, o script agrupa dias com cota ≥200 cm e separa episódios por lacunas
maiores que 3 dias: foram identificados **574 episódios**, dos quais 85 tiveram
pico em junho-agosto, 280 em dezembro-março e 209 nos demais meses.

Como a ANA está em resolução diária, ela não permite calcular Vz em cm/h nem
classificar retrospectivamente cheias relâmpago e graduais. Para isso, foram
usados os 27 eventos com dados de alta resolução disponíveis entre
2024-10-03 e 2026-09-14: 10 relâmpago (pico observado de Vz >50 cm/h), 14
graduais (12–50 cm/h), 9 de inverno e 9 de verão. As categorias sazonais podem
se sobrepor às categorias pela velocidade de subida.

## Validação LOEO observada

| Especialista | Eventos / folds | MAE LightGBM (cm) | MAE Vz/Az (cm) | Seleção |
|---|---:|---:|---:|---|
| Relâmpago | 10 / 10 | 2,52 | 3,80 | LightGBM |
| Gradual | 14 / 14 | 2,07 | 2,60 | LightGBM |
| Inverno | 9 / 9 | 2,64 | 3,04 | LightGBM |
| Verão | 9 / 9 | 2,25 | 3,24 | LightGBM |

O relatório fold a fold, os metadados e o estado de ativação estão em
`resultados/ensemble_especialistas.json`. Os modelos ativados são os arquivos
LightGBM em `modelos/especialistas/`.

Um especialista só é selecionado se tiver pelo menos quatro eventos e quatro
folds LOEO válidos e sua MAE média por evento for inferior à do fallback. A API
`prever_cota_1h(features)` aplica a regra de roteamento e devolve a previsão do
especialista selecionado ou o fallback Vz/Az. Se não existir especialista
adequado para o mês/Vz, usa o fallback.

## Segurança operacional

Este resultado é **experimental e em modo sombra**, não é um sistema de alerta
e não foi conectado à lógica de envio do Telegram. As métricas são regressão
de cota em janelas de eventos recentes, não avaliação de probabilidade,
antecedência ou desempenho para eventos futuros. A ativação por melhora de MAE
em poucos eventos não demonstra, isoladamente, robustez operacional; os
especialistas devem continuar fora de decisões de segurança pública até
validação externa e revisão hidrológica.
