# 🌪️ ARCTURUS CLIMATIK

**Sistema de Monitoramento Climático para Santa Catarina**

---

## 📋 Sobre o Projeto

ARCTURUS CLIMATIK é um sistema de monitoramento climático que integra dados de **45 estações meteorológicas** (21 EPAGRI + 24 INMET) em Santa Catarina, processa **1.052.136 registros** e gera previsões de temperatura, umidade e eventos extremos.

---

## 📊 Dados

| Fonte | Registros | Estações | Período |
|-------|-----------|----------|---------|
| **EPAGRI** | 352.296 | 21 | 2024-2026 |
| **INMET** | 699.840 | 24 | 2024-2026 |
| **Total** | **1.052.136** | **45** | 2024-2026 |

---

## 🧠 Modelos

| Modelo | Métrica | Skill Score |
|--------|---------|-------------|
| **Regressão (Temperatura)** | RMSE 0.844°C | 0.199 |
| **Classificação (Extremos)** | Acurácia 0.95+ | — |
| **Anomalias (Isolation Forest)** | Recall 1.00 | — |

---

## 🏗️ Arquitetura

```
ARCTURUS_CLIMATIK/
├── dados/                 # Datasets processados
├── scripts/               # Scripts ETL e ML
├── modelos/               # Modelos treinados (.pkl)
├── notebooks/             # Análises exploratórias
├── relatorios/            # Relatórios gerados
├── docs/                  # Documentação
└── dashboard/             # Visualizações
```

---

## 🛠️ Tecnologias

- Python 3.12+
- Pandas, NumPy
- Scikit-learn (Random Forest, Isolation Forest)
- Matplotlib, Seaborn
- Google Colab

---

## 📈 Resultados

| Métrica | Valor |
|---------|-------|
| **Skill RMSE** | 0.199 |
| **RMSE Modelo** | 0.844°C |
| **RMSE Persistência** | 1.054°C |
| **Estações** | 45 |
| **Registros** | 1.052.136 |

---

## 🔍 Auditoria

- **Raw Evidence First** — dados validados com evidência bruta
- **Modo Cético 9.9** — questionamento sistemático
- **Anti-Leakage** — split temporal, sem vazamento
- **Correção de vieses** — estações sobrepostas, arquivos fantasmas

---

## 📌 Próximos Passos

- [ ] Adicionar features físicas (pressão, vento, umidade)
- [ ] Testar XGBoost/LightGBM
- [ ] Dashboard interativo (Streamlit)
- [ ] Alertas automáticos (Telegram)

---

## 🏛️ NEXUS OIKOS

**Onde a dúvida vira investigação.**

---

**Última atualização:** 12/08/2026 21:35