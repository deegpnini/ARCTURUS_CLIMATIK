# Validação e Congelamento de Datasets — ARCTURUS CLIMATIK

- **Status:** `VALIDADO`
- **Data da Auditoria:** `2026-11-26 20:50:36`
- **Fonte Oficial:** ANA — Estação `84580000` (via `hidroana`)
- **Tabela de Referência no Banco:** `PostgreSQL (arcturus) -> ana_historico`
- **Dataset de Treino Congelado:** `data/dataset_treino_ana_preparado.parquet`

---

## 1. Resumo da Verificação Cruzada (`ana_historico` × `dataset_treino_ana_preparado.parquet`)

| Métrica / Atributo | Valor Auditado |
| :--- | :--- |
| **Período `ana_historico` (PostgreSQL)** | `2024-01-01` a `2026-01-31` (`762` registros diários) |
| **Período `dataset_treino_ana_preparado.parquet`** | `2024-01-02` a `2026-01-31` (`761` registros diários, `55` colunas) |
| **Registros na interseção (`2024-01-02` a `2026-01-31`)** | `761` |
| **Correlação de Pearson ($r$)** | `1.000000` |
| **Erro Absoluto Médio (MAE)** | `0.0000 cm` |
| **Erro Absoluto Máximo** | `0.0000 cm` |
| **Unidade Numérica Confirmada** | Centímetros (`cm`) — escala idêntica entre `ana_historico.cota_cm` e `ana_cota_m` |

---

## 2. Assinaturas Criptográficas (SHA-256)

| Artefato | Caminho | SHA-256 |
| :--- | :--- | :--- |
| **CSV Oficial ANA (`hidroana`)** | `data/ana_historico/84580000.csv` | `cb41ca79252bf961bc77d560a3c7f52e0b435855ce23c2441293e1a16eea7aa9` |
| **Dataset de Treino Preparado** | `data/dataset_treino_ana_preparado.parquet` | `368ee530ad5da080794c2b83b0898f20500532b0482fa8b126c91c4f7f0ef870` |

---

## 3. Regra de Governança Científica

1. **Integridade da base diária:** A série `ana_cota_m` presente em `data/dataset_treino_ana_preparado.parquet` reproduz com **erro zero (`0.0000 cm`)** os registros oficiais da estação ANA `84580000` carregados em `ana_historico`.
2. **Separação de escalas temporais:** Este conjunto possui resolução **diária (`1d`)** e é destinado exclusivamente a análises climatológicas/históricas e ao treinamento experimental do modelo `v11c`. A avaliação prospectiva operacional nos horizontes curtos (**`1h`, `3h` e `6h`**) permanece ancorada na série de **15 minutos da régua ERAB** (`leituras` / `forecast_predictions`).
