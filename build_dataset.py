#!/usr/bin/env python3
"""
Feature engineering — ARCTURUS Hidro.
Gera 3 datasets: 1h, 3h, 6h.
Aplica regras de completude v1.0.
"""
import json, os, sys, math
from datetime import datetime, timedelta
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
CODIGO = "84580000"

def numero(v):
    if v is None: return None
    s = str(v).strip().replace(',', '.')
    if not s: return None
    try: return float(s)
    except: return None

def carregar_telemetria():
    """Carrega 3 anos, deduplica por timestamp."""
    dados = {}
    for ano in [2024, 2025, 2026]:
        path = f"{CACHE}/telemetria_{CODIGO}_{ano}.json"
        if not os.path.exists(path): continue
        d = json.load(open(path))
        for it in d.get("items", []):
            ts_str = it.get('Data_Hora_Medicao', '')[:19]
            try:
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except:
                continue
            if dt in dados: continue
            dados[dt] = {
                'cota': numero(it.get('Cota_Adotada')),
                'vazao': numero(it.get('Vazao_Adotada')),
                'chuva': numero(it.get('Chuva_Adotada')),
            }
    return dados

def lookup(dados, dt, lag_min):
    """Retorna valor em dt - lag_min (se existir exatamente)."""
    t = dt - timedelta(minutes=lag_min)
    return dados.get(t)

def chuva_acumulada(dados, dt, janela_min):
    """Soma chuva na janela. Se cobertura < 90%, retorna None."""
    n_pontos = janela_min // 15 + 1
    n_esperado = n_pontos
    total = 0.0
    validos = 0
    for i in range(n_pontos):
        t = dt - timedelta(minutes=15 * i)
        d = dados.get(t)
        if d and d['chuva'] is not None:
            total += d['chuva']
            validos += 1
    if validos / n_esperado < 0.9:
        return None
    return total

def cota_stats(dados, dt, janela_min):
    """Retorna (std, max, min) na janela. So se cobertura > 90%."""
    n_pontos = janela_min // 15 + 1
    valores = []
    for i in range(n_pontos):
        t = dt - timedelta(minutes=15 * i)
        d = dados.get(t)
        if d and d['cota'] is not None:
            valores.append(d['cota'])
    if len(valores) / n_pontos < 0.9:
        return None, None, None
    if not valores:
        return None, None, None
    n = len(valores)
    media = sum(valores) / n
    var = sum((v - media) ** 2 for v in valores) / n
    return math.sqrt(var), max(valores), min(valores)

def build_features(dados, dt):
    """Constroi todas as features para o instante dt."""
    cota_t = dados.get(dt, {}).get('cota')
    if cota_t is None:
        return None

    f = {'timestamp': dt.strftime("%Y-%m-%d %H:%M:%S"), 'cota': cota_t}

    # Lags de cota
    for lag in [15, 30, 60, 180, 360, 720, 1440]:
        d_lag = dados.get(dt - timedelta(minutes=lag))
        f[f'cota_lag_{lag}m'] = d_lag['cota'] if d_lag else None

    # Deltas
    for lag in [15, 60, 180]:
        v = f.get(f'cota_lag_{lag}m')
        f[f'delta_{lag}m'] = (cota_t - v) if v is not None else None

    # Aceleracao
    d1 = f.get('delta_60m')
    dt_ant = dt - timedelta(minutes=60)
    d_ant = dados.get(dt_ant, {}).get('cota')
    if d_ant is not None and d1 is not None:
        v_ant = dados.get(dt_ant - timedelta(minutes=60), {}).get('cota')
        delta_ant = (d_ant - v_ant) if v_ant is not None else None
        f['aceleracao_1h'] = (d1 - delta_ant) if delta_ant is not None else None
    else:
        f['aceleracao_1h'] = None

    # Stats de cota
    std, mx, mn = cota_stats(dados, dt, 720)
    f['cota_std_12h'] = std
    f['cota_max_12h'] = mx
    f['cota_min_12h'] = mn

    # Vazao
    f['vazao'] = dados.get(dt, {}).get('vazao')

    # Chuva acumulada
    for janela in [15, 60, 180, 360, 720, 1440, 2880]:
        f[f'chuva_{janela}m'] = chuva_acumulada(dados, dt, janela)

    # Temporal ciclico
    hora = dt.hour + dt.minute / 60
    dia_ano = dt.timetuple().tm_yday
    f['sin_hora'] = math.sin(2 * math.pi * hora / 24)
    f['cos_hora'] = math.cos(2 * math.pi * hora / 24)
    f['sin_dia_ano'] = math.sin(2 * math.pi * dia_ano / 365)
    f['cos_dia_ano'] = math.cos(2 * math.pi * dia_ano / 365)

    return f

def build_targets(dados, dt):
    """Retorna os 3 targets."""
    t = {}
    for h, delta in [('1h', 60), ('3h', 180), ('6h', 360)]:
        d_fut = dados.get(dt + timedelta(minutes=delta))
        t[f'target_{h}'] = d_fut['cota'] if d_fut else None
    return t

def main():
    print("Carregando telemetria...")
    dados = carregar_telemetria()
    print(f"  {len(dados)} timestamps unicos")
    print()

    timestamps = sorted(dados.keys())
    print(f"Periodo: {timestamps[0]} a {timestamps[-1]}")

    print()
    print("Construindo features (isso demora ~2-3 min)...")
    linhas = []
    for i, dt in enumerate(timestamps):
        if i % 5000 == 0:
            print(f"  {i}/{len(timestamps)}")
        f = build_features(dados, dt)
        if f is None:
            continue
        t = build_targets(dados, dt)
        linhas.append({**f, **t})

    print(f"  {len(linhas)} linhas com features")

    # Gera 3 CSVs
    for horizonte in ['1h', '3h', '6h']:
        out = f"{CACHE}/dataset_{horizonte}.csv"
        # So linhas com target valido
        filtradas = [l for l in linhas if l.get(f'target_{horizonte}') is not None]
        
        # Cabecalho
        cols = list(linhas[0].keys())
        # Remove targets nao desse horizonte
        cols_use = [c for c in cols if not (c.startswith('target_') and c != f'target_{horizonte}')]

        with open(out, 'w') as fp:
            fp.write(','.join(cols_use) + '\n')
            for l in filtradas:
                vals = []
                for c in cols_use:
                    v = l.get(c)
                    if v is None:
                        vals.append('')
                    else:
                        vals.append(str(v))
                fp.write(','.join(vals) + '\n')

        print(f"  {horizonte}: {len(filtradas)} linhas -> {out}")

if __name__ == "__main__":
    main()
