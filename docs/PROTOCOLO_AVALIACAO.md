# Protocolo de Avaliação Prospectiva — Motor V2 (Modo Sombra)

**Data de pré-registro:** 31/10/2026
**Autores:** Comandante Hebron & Trinity SCTEC 7
**Baseado em:** Auditoria técnica do Claude (Anthropic)

## 1. Objetivo
Avaliar se o Motor V2 (LightGBM regressão, Δcota) agrega valor preditivo sobre o baseline de persistência e sobre a Camada 1 (física).

## 2. Métricas Definitivas
- **Skill Score (SS):** `1 - (MAE_modelo / MAE_persistencia)`. 
- **Estratificação:** O SS deve ser calculado no agregado e no regime de evento (|Δ real| > 10 cm).
- **Lead Time:** Capacidade de antecipar o cruzamento de limiar em relação à Camada 1.

## 3. Critérios de Sucesso (Promover a alertante)
O modelo SÓ será promovido a alertante se, após 60 dias:
1. `Skill Score (regime de evento)` >= 0.3 com intervalo de confiança de 95% (bootstrap em blocos) inferior > 0.
2. `n_eventos independentes` >= 10 (se < 10, o resultado é INCONCLUSIVO).
3. `Lead time médio` > 0 em relação à Camada 1 (POD >= 0.7 e FAR <= 0.5).
4. `Viés em subida` |bias| < 20% da magnitude média do Δ.

## 4. Critérios de Falha (Arquivar ou Reformular)
1. `Skill Score` <= 0 no regime de evento.
2. Sem ganho de lead time sobre a Camada 1.

## 5. Cenário Sem Cheia
Se não houver eventos de cheia em 60 dias, o experimento é INCONCLUSIVO. Nesse caso, faremos um "replay retrospectivo honesto" (point-in-time) como complemento, rotulado claramente como retrospectivo.

## 6. Regra de Ouro
A Camada 1 (alerta físico) permanece como única fonte de alerta durante todo o período de avaliação. O Motor V2 não dispara Telegram.
