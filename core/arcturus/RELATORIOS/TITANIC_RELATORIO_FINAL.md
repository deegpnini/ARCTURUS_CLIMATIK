# ARCTURUS TITANIC — RELATÓRIO FINAL

**Data: 2026-07-30 07:22:07**
**Versão:** V3

## METADADOS

- Modelo: RandomForest
- Features: 11
- F1_CV: 0.7784 +/- 0.0297
- Status: PRODUÇÃO

## TESTE DE FEATURES

**Hipóteses testadas:**
- Cabin Deck (Deck_Enc)
- Ticket Group Size (TicketGroupSize)
- Fare per Person (FarePerPerson)
- Age imputation por Title+Pclass (Age_Imp)

**Resultado:** Nenhuma das 4 features trouxe ganho significativo.
- Ganho observado: -0.0041
- p-valor (Nadeau-Bengio): 0.8244

**Decisão:** RF V3 mantido por parcimônia.

## ARTEFATOS

- titanic_rf_v3.pkl
- encoders_v3.pkl
- submission_final_v3.csv

## LIÇÕES

1. O sinal preditivo do Titanic está majoritariamente capturado por Sex e Title.
2. Feature engineering tem limite — testar e descartar é tão importante quanto testar e aprovar.
3. O protocolo NEXUS de raw evidence vale para resultados negativos também.

---
N.E.X.U.S OIKOS — Onde a dúvida vira investigação 🏛️
