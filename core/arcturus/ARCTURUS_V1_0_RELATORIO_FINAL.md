
# ARCTURUS V1.0 — RELATÓRIO FINAL CONSOLIDADO

## DATA: 19/07/2026

---

## 1. A CADEIA DE CORREÇÕES

### 1.1 O F1=0.492 (Modelo "Campeão" Original)
- **Contexto:** Resultado inicial reportado com Random Forest + 8 features
- **Status:** ❌ NÃO CONFIRMADO
- **Motivo:** Não reproduzível, dependia de features de cluster calculadas globalmente (vazamento)

### 1.2 O F1=0.36 (Modelo com Clusters Globais)
- **Contexto:** Resultado após remoção de `cluster_severidade`
- **Status:** ❌ INFLADO POR VAZAMENTO (~20%)
- **Motivo:** DBSCAN e features de cluster calculados sobre o dataset completo ANTES do split de CV

### 1.3 O F1=0.30 (Modelo Honesto)
- **Contexto:** Modelo com 4 features geofísicas (sem clusters)
- **Status:** ✅ VALIDADO
- **Validação:** 5-fold CV com clusters recalculados por fold (sem vazamento)
- **Teste pareado:** p=0.1885 (clusters honestos não demonstraram ganho significativo)

---

## 2. MODELO FINAL

### Features (4)
- `profundidade_km` — Profundidade do evento (km)
- `latitude` — Coordenada geográfica
- `longitude` — Coordenada geográfica
- `proximidade_falha` — Distância à falha geológica mais próxima (km)

### Hiperparâmetros
- **Algoritmo:** RandomForestClassifier
- **n_estimators:** 100
- **max_depth:** 8
- **class_weight:** balanced
- **random_state:** 42

---

## 3. DESEMPENHO (5-fold CV)

### Métricas por Classe

| Classe | Precisão | Recall | F1-Score | Suporte |
|--------|----------|--------|----------|---------|
| BAIXO  | 0.67     | 0.57   | 0.62     | 45.657  |
| MÉDIO  | 0.50     | 0.48   | 0.49     | 32.731  |
| ALTO   | 0.20     | 0.54   | 0.29     | 4.856   |

### Matriz de Confusão

| Real \ Pred | BAIXO | MÉDIO | ALTO |
|-------------|-------|-------|------|
| BAIXO       | 26.039| 14.509| 5.109|
| MÉDIO       | 11.856| 15.572| 5.303|
| ALTO        | 1.125 | 1.124 | 2.607|

### Interpretação Operacional

- **Precisão ALTO:** 20% — 1 em cada 5 alertas de "ALTO" é verdadeiro
- **Recall ALTO:** 54% — captura pouco mais da metade dos eventos ALTO reais
- **Falso positivo:** 80% dos alertas de ALTO seriam falsos

---

## 4. LIMITAÇÕES CONHECIDAS

1. **Precisão baixa na classe ALTO (20%)** — 80% dos alertas seriam falsos positivos
2. **Clusters não validados como benefício real** — teste pareado inconclusivo (p=0.1885)
3. **Custo computacional do DBSCAN por fold (~85-105s)** — inviável para revalidação frequente
4. **Dependência de dados USGS** — qualidade e disponibilidade da API afetam o sistema
5. **Resolução geográfica limitada** — `proximidade_falha` é uma simplificação

---

## 5. STATUS

| Item | Status |
|------|--------|
| Modelo validado | ✅ SIM |
| Sem vazamento de dados | ✅ SIM |
| Documentação consolidada | ✅ SIM |
| Integração com API USGS | ❌ PENDENTE |
| Dashboard de validação | ❌ PENDENTE |
| Produção em tempo real | ❌ PENDENTE |

**Status atual:** 🟡 Modelo final validado — candidato para próxima fase (documentação + integração)

---

## 6. PRÓXIMOS PASSOS

1. **Documentação:** Completar relatório para registro (Zenodo)
2. **Integração:** Conectar com API USGS para coleta em tempo real
3. **Dashboard:** Interface para validação humana dos alertas
4. **Monitoramento:** Acompanhar desempenho em produção
5. **Melhorias:** Coletar mais dados de ALTO para melhorar precisão

---

## 7. ARQUIVOS GERADOS

- `arcturus_v1_0_final.pkl` — Modelo treinado
- `arcturus_v1_0_config.json` — Configuração e métricas
- `inferencia_arcturus.py` — Script de inferência

---

**N.E.X.U.S OIKOS — ONDE A DÚVIDA VIRA INVESTIGAÇÃO**

