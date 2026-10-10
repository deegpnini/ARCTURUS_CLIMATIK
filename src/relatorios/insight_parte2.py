"""
PARTE 2 do insight.py — reconstrucao de features + previsao.
Adiciona as funcoes abaixo ao arquivo existente.
"""
import os
import sys
import json
import hashlib
import math
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import lightgbm as lgb

# ============================================================
# PATHS
# ============================================================
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)

DATA = ROOT / "data"
MODELOS = ROOT / "modelos"
RES = ROOT / "resultados"
INSIGHTS = RES / "insights"
INSIGHTS.mkdir(parents=True, exist_ok=True)

# ============================================================
# UTILS
# ============================================================
def numero(v):
    if v is None: return None
    s = str(v).strip().replace(",", ".")
    if not s: return None
    try: return float(s)
    except: return None

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

# ============================================================
# CARREGAR TELEMETRIA
# ============================================================
def carregar_dados_telemetria():
    """Carrega 2026 (cache local), indexa por timestamp."""
    path = DATA / "telemetria_84580000_2026.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    dados = {}
    for it in d.get("items", []):
        ts_str = (it.get("Data_Hora_Medicao") or "")[:19]
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except:
            continue
        if dt in dados:
            continue
        dados[dt] = {
            "cota": numero(it.get("Cota_Adotada")),
            "chuva": numero(it.get("Chuva_Adotada")),
        }
    return dados

# ============================================================
# FEATURES (mesma logica do build_dataset.py)
# ============================================================
def chuva_acumulada(dados, dt, janela_min):
    n_pontos = janela_min // 15 + 1
    total = 0.0
    validos = 0
    for i in range(n_pontos):
        t = dt - timedelta(minutes=15 * i)
        d = dados.get(t)
        if d and d["chuva"] is not None:
            total += d["chuva"]
            validos += 1
    if validos / n_pontos < 0.9:
        return None
    return total

def cota_stats(dados, dt, janela_min):
    n_pontos = janela_min // 15 + 1
    valores = []
    for i in range(n_pontos):
        t = dt - timedelta(minutes=15 * i)
        d = dados.get(t)
        if d and d["cota"] is not None:
            valores.append(d["cota"])
    if len(valores) / n_pontos < 0.9:
        return None, None, None
    if not valores:
        return None, None, None
    n = len(valores)
    media = sum(valores) / n
    var = sum((v - media) ** 2 for v in valores) / n
    return math.sqrt(var), max(valores), min(valores)

def reconstruir_features(dados, dt):
    """Constroi as 27 features do instante dt."""
    cota_t = dados.get(dt, {}).get("cota")
    if cota_t is None:
        return None

    f = {"timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"), "cota": cota_t}

    # Lags de cota
    for lag in [15, 30, 60, 180, 360, 720, 1440]:
        d_lag = dados.get(dt - timedelta(minutes=lag))
        f[f"cota_lag_{lag}m"] = d_lag["cota"] if d_lag else None

    # Deltas
    for lag in [15, 60, 180]:
        v = f.get(f"cota_lag_{lag}m")
        f[f"delta_{lag}m"] = (cota_t - v) if v is not None else None

    # Aceleracao
    d1 = f.get("delta_60m")
    dt_ant = dt - timedelta(minutes=60)
    d_ant = dados.get(dt_ant, {}).get("cota")
    if d_ant is not None and d1 is not None:
        v_ant = dados.get(dt_ant - timedelta(minutes=60), {}).get("cota")
        delta_ant = (d_ant - v_ant) if v_ant is not None else None
        f["aceleracao_1h"] = (d1 - delta_ant) if delta_ant is not None else None
    else:
        f["aceleracao_1h"] = None

    # Stats 12h
    std, mx, mn = cota_stats(dados, dt, 720)
    f["cota_std_12h"] = std
    f["cota_max_12h"] = mx
    f["cota_min_12h"] = mn

    # Vazao removida (redundante com cota)

    # Chuva acumulada
    for janela in [15, 60, 180, 360, 720, 1440, 2880]:
        f[f"chuva_{janela}m"] = chuva_acumulada(dados, dt, janela)

    # Cíclicos
    hora = dt.hour + dt.minute / 60
    dia_ano = dt.timetuple().tm_yday
    f["sin_hora"] = math.sin(2 * math.pi * hora / 24)
    f["cos_hora"] = math.cos(2 * math.pi * hora / 24)
    f["sin_dia_ano"] = math.sin(2 * math.pi * dia_ano / 365)
    f["cos_dia_ano"] = math.cos(2 * math.pi * dia_ano / 365)

    return f

# ============================================================
# PREVER
# ============================================================
def prever(dados, dt, manifesto):
    """Reconstroi features + prever com os 3 modelos."""
    feats_dict = reconstruir_features(dados, dt)
    if feats_dict is None:
        return None, "cota indisponivel em t"

    cota_atual = feats_dict["cota"]
    previsoes = {}

    for h in ["1h", "3h", "6h"]:
        info = manifesto["horizontes"][h]
        feats_h = info["features"]

        # Monta X na ordem das features
        X = np.array([[feats_dict.get(f) for f in feats_h]], dtype=object)

        # Carrega modelo (LGBM aceita object array, converte internamente)
        model = lgb.Booster(model_file=str(MODELOS / info["arquivo"]))

        delta_pred = float(model.predict(X)[0])
        cota_pred = cota_atual + delta_pred

        previsoes[h] = {
            "delta_previsto": delta_pred,
            "cota_prevista": cota_pred,
        }

    return {
        "cota_atual": cota_atual,
        "features_usadas": sum(1 for k, v in feats_dict.items() if k != "timestamp" and v is not None),
        "features_total": len(feats_dict) - 1,  # -1 para excluir timestamp
        "previsoes": previsoes,
    }, None

# ============================================================
# TESTE — roda com 22/09/2026 00:00 (evento 446)
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("  TESTE — Parte 2: reconstrucao + previsao")
    print("=" * 70)

    print("\n[1] Carregando telemetria...")
    dados = carregar_dados_telemetria()
    print(f"    {len(dados)} timestamps")

    print("\n[2] Carregando manifesto...")
    with open(MODELOS / "manifesto_producao.json", encoding="utf-8") as f:
        manifesto = json.load(f)

    print("\n[3] Testando 3 datas:")
    for dt_str in ["2026-09-21 20:00:00", "2026-09-22 00:00:00", "2026-09-22 06:00:00"]:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        print(f"\n  --- {dt_str} ---")
        res, erro = prever(dados, dt, manifesto)
        if erro:
            print(f"    ERRO: {erro}")
            continue
        print(f"    Cota atual: {res['cota_atual']:.2f} cm")
        print(f"    Features disponiveis: {res['features_usadas']}/{res['features_total']}")
        for h, p in res["previsoes"].items():
            print(f"    {h}: delta={p['delta_previsto']:+.2f} | cota={p['cota_prevista']:.2f}")
