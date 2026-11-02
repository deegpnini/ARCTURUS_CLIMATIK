#!/usr/bin/env bash
# Gera docs/ESTADO_VERIFICADO.md com fatos lidos da máquina (sem opinião).
cd "$(dirname "$0")/.." || exit 1
OUT=docs/ESTADO_VERIFICADO.md
{
echo "# ESTADO VERIFICADO (gerado por tools/gerar_estado.sh)"
echo "gerado_em: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo; echo "## Git"; git log --oneline -8; git status --short | head -15
echo; echo "## Ambiente"; python --version
pip freeze 2>/dev/null | grep -iE "^(lightgbm|pandas|numpy|scikit-learn|streamlit|dash|plotly|playwright|earthengine-api)=="
echo; echo "## Modelos e manifestos"; ls -l --time-style=long-iso modelos/ | tail -n +2
echo; echo "## Manifesto do classificador v2"; cat modelos/manifesto_classificador_v2.json 2>/dev/null
echo; echo "## Dados"
python - << 'PY'
import json
import pandas as pd
d = pd.read_csv("data/dataset_1h_com_montante.csv", index_col=0, parse_dates=True).sort_index()
print("dataset 15min:", d.index.min(), "->", d.index.max(), "| cota max:", d["cota"].max())
try:
    print("ERAB:", json.load(open("tubarao_saneamento_dados.json")))
except Exception as e:
    print("ERAB: erro:", e)
PY
} > "$OUT" 2>&1
echo "gerado: $OUT"
