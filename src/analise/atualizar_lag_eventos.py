#!/usr/bin/env python3
"""
atualizar_lag_eventos.py — Rastreia o tempo de resposta (lag) entre a chuva
na bacia (evento_atual_bacia.json) e a onda de cheia na ERAB (PostgreSQL).
Calcula cota_inicial (base pre-evento), cota_atual, delta_cota, horas_ate_subida
e horas_ate_pico em data/lag_eventos.jsonl.
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
EVENTO_FILE = BASE_DIR / "data" / "evento_atual_bacia.json"
DCSC_FILE = BASE_DIR / "data" / "chuva_defesacivil_realtime.json"
LAG_FILE = BASE_DIR / "data" / "lag_eventos.jsonl"


def ler_serie_recente_erab():
    """Busca leituras validas das ultimas 6h para identificar base real e subida."""
    sql = """
    SELECT
        to_char(timestamp, 'YYYY-MM-DD"T"HH24:MI:SS'),
        cota_cm,
        COALESCE(vz_cm_h, 0)
    FROM leituras
    WHERE qc = 'VALIDO'
      AND cota_cm IS NOT NULL
      AND timestamp >= NOW() - INTERVAL '6 hours'
    ORDER BY timestamp ASC;
    """
    res = subprocess.run(
        ["psql", "-d", "arcturus", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True,
        text=True,
        check=True,
    )
    serie = []
    for linha in res.stdout.strip().splitlines():
        if not linha.strip():
            continue
        ts_iso, cota_s, vz_s = linha.split("|")
        serie.append({
            "timestamp": ts_iso,
            "cota_cm": float(cota_s),
            "vz_cm_h": float(vz_s),
        })
    return serie


def ler_chuvas_estacoes():
    if not DCSC_FILE.exists():
        return {}
    try:
        dados = json.loads(DCSC_FILE.read_text(encoding="utf-8"))
        out = {}
        for est in dados.get("estacoes", []):
            nome = est.get("nome", "")
            c24 = est.get("chuva_24h_mm")
            if nome and c24 is not None:
                out[nome] = float(c24)
        return out
    except Exception:
        return {}


def main():
    if not EVENTO_FILE.exists():
        print("[LAG] evento_atual_bacia.json ausente; aguardando snapshot.")
        return

    evento = json.loads(EVENTO_FILE.read_text(encoding="utf-8"))
    serie = ler_serie_recente_erab()
    if not serie:
        print("[LAG] Nenhuma leitura VALIDA recente encontrada no PostgreSQL.")
        return

    erab = serie[-1]
    cota_atual = erab["cota_cm"]
    vz_atual = erab["vz_cm_h"]

    # Base pre-evento: menor cota valida nas ultimas 6h antes do repique atual
    min_pt = min(serie, key=lambda x: x["cota_cm"])
    cota_base_6h = min_pt["cota_cm"]

    # Primeiro ponto apos a minima em que a cota subiu >= 3 cm (ex: 97 -> 105)
    ponto_subida = next(
        (p for p in serie if p["timestamp"] >= min_pt["timestamp"] and (p["cota_cm"] - cota_base_6h) >= 3.0),
        None,
    )

    agora = datetime.now()
    evento_id = str(
        evento.get("evento_id")
        or evento.get("id")
        or agora.strftime("%Y%m%d")
    )
    estacao_dom = (
        evento.get("estacao_dominante")
        or evento.get("dominante")
        or "Desconhecida"
    )
    chuva_max = float(
        evento.get("chuva_max_24h")
        or evento.get("chuva_24h_mm")
        or evento.get("max_chuva_24h")
        or 0.0
    )

    registros = []
    if LAG_FILE.exists():
        for linha in LAG_FILE.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha:
                registros.append(json.loads(linha))

    idx_existente = next(
        (i for i, r in enumerate(registros) if str(r.get("evento")) == evento_id),
        None,
    )

    chuvas_est = ler_chuvas_estacoes()

    if idx_existente is None:
        reg = {
            "evento": evento_id,
            "inicio_evento": evento.get("inicio") or min_pt["timestamp"],
            "ultima_atualizacao": erab["timestamp"],
            "estacao_dominante": estacao_dom,
            "chuva_max_24h": round(chuva_max, 2),
            "chuvas_estacoes_24h": chuvas_est,
            "cota_inicial": cota_base_6h,
            "cota_atual": cota_atual,
            "delta_cota": round(cota_atual - cota_base_6h, 2),
            "cota_pico": cota_atual,
            "ts_pico": erab["timestamp"],
            "horas_ate_subida": None,
            "horas_ate_pico": 0.0,
            "status": "MONITORANDO_SUBIDA",
        }
        registros.append(reg)
    else:
        reg = registros[idx_existente]
        # Preserva a menor cota observada como referencia real do inicio da onda
        cota_ini = min(float(reg.get("cota_inicial", cota_base_6h)), cota_base_6h)
        reg["cota_inicial"] = cota_ini

    t0_str = str(reg["inicio_evento"])[:19]
    try:
        t0 = datetime.fromisoformat(t0_str)
    except Exception:
        t0 = datetime.fromisoformat(min_pt["timestamp"][:19])

    if ponto_subida is not None and reg.get("horas_ate_subida") is None:
        t_sub = datetime.fromisoformat(ponto_subida["timestamp"][:19])
        reg["horas_ate_subida"] = round(max((t_sub - t0).total_seconds() / 3600.0, 0.0), 2)
        reg["ts_subida"] = ponto_subida["timestamp"]
        reg["status"] = "EM_SUBIDA"

    if chuva_max >= float(reg.get("chuva_max_24h") or 0.0):
        reg["chuva_max_24h"] = round(chuva_max, 2)
        reg["estacao_dominante"] = estacao_dom

    if chuvas_est:
        reg["chuvas_estacoes_24h"] = chuvas_est

    cota_ini = float(reg["cota_inicial"])
    cota_pico_ant = float(reg.get("cota_pico") or cota_ini)

    if cota_atual >= cota_pico_ant:
        t_pico = datetime.fromisoformat(erab["timestamp"][:19])
        reg["cota_pico"] = cota_atual
        reg["ts_pico"] = erab["timestamp"]
        reg["horas_ate_pico"] = round(max((t_pico - t0).total_seconds() / 3600.0, 0.0), 2)
        if (cota_atual - cota_ini) >= 3.0:
            reg["status"] = "EM_SUBIDA"
    elif (cota_pico_ant - cota_atual) >= 4.0 and vz_atual < 0:
        reg["status"] = "RECESSAO"

    reg["cota_atual"] = cota_atual
    reg["delta_cota"] = round(cota_atual - cota_ini, 2)
    reg["ultima_atualizacao"] = erab["timestamp"]

    LAG_FILE.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in registros) + "\n",
        encoding="utf-8",
    )
    print("\n=== 2. NOVO REGISTRO EM lag_eventos.jsonl ===")
    print(json.dumps(reg, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
