# ARCTURUS CLIMATIK

Sistema de monitoramento e previsão de temperatura horária para Santa Catarina, integrando dados de estações meteorológicas da EPAGRI e do INMET.

**Período dos dados:** 2024-01-01 a 2026-07-31
**Volume:** 1.052.136 registros horários
**Estações:** 45 (após fusão de sobreposições)

---

## Objetivo

Desenvolver um pipeline reproduzível de engenharia de dados e um modelo de previsão horária de temperatura que agregue valor além da simples persistência (previsão = valor da hora anterior).

O modelo principal prevê o **residual** (ΔT = Tₜ − Tₜ₋₁), reduzindo a dependência excessiva da autocorrelação temporal.

---

## Resultados principais (modelo residual)

| Métrica              | Valor     |
|----------------------|-----------|
| RMSE do modelo       | 0.844 °C  |
| RMSE da persistência | 1.054 °C  |
| **Skill RMSE**       | **0.199** |
| Skill MAE            | 0.129     |

> Skill = 1 − (erro_modelo / erro_persistência).
> Valores positivos indicam ganho real sobre o baseline de persistência.

**Observação:** Skill de ~0.20 é moderado. O modelo ainda é fortemente influenciado pela persistência. Melhorias dependem da inclusão de variáveis físicas adicionais (pressão, vento, precipitação, etc.).

---

## Estrutura do repositório

```
ARCTURUS_CLIMATIK/
├── pipeline_completo.py      # Integração e limpeza EPAGRI + INMET
├── modelo_residual.py        # Treinamento e avaliação do modelo residual
├── pipeline.py               # Versão simplificada
├── requirements.txt
├── scripts/
│   └── exemplo.py
└── README.md
```

---

## Instalação

### 1. Clonar o repositório

```bash
git clone https://github.com/deegpnini/ARCTURUS_CLIMATIK.git
cd ARCTURUS_CLIMATIK
```

### 2. Criar ambiente virtual (recomendado)

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# ou
.venv\Scripts\activate           # Windows
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

---

## Como executar

### Pipeline de dados

```bash
python pipeline_completo.py
```

### Modelo residual

```bash
python modelo_residual.py
```

---

## Metodologia resumida

1. **Integração de fontes** — EPAGRI (21 estações) + INMET (24 estações).
2. **Limpeza** — Remoção de estações inválidas, fusão de sobreposições, padronização.
3. **Feature engineering** — Lags de temperatura, codificação cíclica, umidade.
4. **Modelagem** — Alvo: residual ΔT, Random Forest, split temporal.

---

## Limitações conhecidas

- Caminhos de dados hardcoded para ambiente Colab.
- Skill Score moderado (~0.20).
- Variáveis físicas (pressão, vento, precipitação) não integradas.
- Análise de erro por regime térmico não implementada.

---

## Próximos passos

- [ ] Tornar o pipeline reproduzível fora do Colab
- [ ] Adicionar variáveis físicas
- [ ] Implementar validação cruzada temporal
- [ ] Análise de erro por regime térmico

---

**Última atualização:** 12/08/2026