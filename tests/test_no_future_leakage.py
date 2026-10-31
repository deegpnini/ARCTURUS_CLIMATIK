#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Adiciona o diretório raiz ao PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
import pytest

# Agora importa a função real
from src.modelo.features_bacia import calcular_features_bacia

def criar_csv_sintetico(n_passado=100, n_futuro=24):
    """Cria um CSV com dados passados e futuros (sentinela 999)."""
    idx = pd.date_range("2026-10-01", periods=n_passado + n_futuro, freq="h")
    df = pd.DataFrame({
        "data_hora": idx,
        "chuva_ponto_1": np.random.rand(len(idx)),
        "chuva_ponto_2": np.random.rand(len(idx)),
    })
    # Dados futuros com valor absurdo (sentinela)
    df.loc[n_passado:, "chuva_ponto_1"] = 999.0
    df.loc[n_passado:, "chuva_ponto_2"] = 999.0
    return df, idx[n_passado - 1]  # ts_origem = última linha passada

def test_invariancia_ao_futuro(monkeypatch, tmp_path):
    df, ts_origem = criar_csv_sintetico()
    
    # Cria um CSV temporário
    csv_test = tmp_path / "chuva_bacia_openmeteo_test.csv"
    df.to_csv(csv_test, index=False)
    
    # Monkeypatch do caminho do arquivo
    import src.modelo.features_bacia as fb
    monkeypatch.setattr(fb, "ARQUIVO_BACIA", csv_test)
    
    # Calcula features com o CSV completo (incluindo futuro)
    f_completo = fb.calcular_features_bacia(ts_origem)
    
    # Trunca o CSV (só passado)
    df_truncado = df[df["data_hora"] <= ts_origem]
    df_truncado.to_csv(csv_test, index=False)
    f_truncado = fb.calcular_features_bacia(ts_origem)
    
    # As features devem ser idênticas
    assert f_completo == f_truncado, f"LEAKAGE DETECTADO: {f_completo} != {f_truncado}"
    print("[OK] Features invariantes ao futuro (sem leakage)")

if __name__ == "__main__":
    test_invariancia_ao_futuro()
