#!/usr/bin/env python3
"""
atualizar_lag_eventos.py — Rastreia o tempo de resposta (lag) entre a chuva
na bacia (evento_atual_bacia.json) e a onda de cheia na ERAB (PostgreSQL).
Grava e atualiza o estado em data/lag_eventos.jsonl.
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
EVENTO_FILE = BASE_DIR / "data" / "evento_atual_bacia.json"
DCSC_FILE = BASE_DIR / "data" / "chuva_defesacivil_realtime.json"
LAG_FILE = BASE_DIR / "data" / "lag_eventos.jsonl"


def ler_ultima_leitura_erab():
    sql = """
    SELECT
        extract(epoch from timestamp)::bigint,
        to_char(timestamp, 'YYYY-MM-DD"T"HH24:MI:SS'),
        cota_cm,
        COALESCE(vz_cm_h, 0)
    FROM leituras
    WHERE qc = 'VALIDO' AND cota_cm IS NOT NULL
    ORDER BY timestamp DESC
    LIMIT 1;
    """
    res = subprocess.run(
        ["psql", "-d", "arcturus", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True,
        text=True,
        check=True,
    )
    linha = res.stdout.strip()
    if not linha:
        return None
    epoch_s, ts_iso, cota_s, vz_s = linha.split("|")
    return {
        "epoch": int(epoch_s),
        "timestamp": ts_iso,
        "cota_cm": float(cota_s),
        "vz_cm_h": float(vz_s),
    }


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
    erab = ler_ultima_leitura_erab()
    if not erab:
        print("[LAG] Nenhuma leitura VALIDA encontrada no PostgreSQL.")
        return

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
    cota_atual = erab["cota_cm"]
    vz_atual = erab["vz_cm_h"]

    if idx_existente is None:
        reg = {
            "evento": evento_id,
            "inicio_evento": evento.get("inicio") or erab["timestamp"],
            "ultima_atualizacao": erab["timestamp"],
            "estacao_dominante": estacao_dom,
            "chuva_max_24h": round(chuva_max, 2),
            "chuvas_estacoes_24h": chuvas_est,
            "cota_inicial": cota_atual,
            "cota_atual": cota_atual,
            "cota_pico": cota_atual,
            "ts_pico": erab["timestamp"],
            "horas_ate_subida": None,
            "horas_ate_pico": 0.0,
            "status": "MONITORANDO_SUBIDA",
        }
        registros.append(reg)
    else:
        reg = registros[idx_existente]
        try:
            t0 = datetime.fromisoformat(str(reg["inicio_evento"])[:19])
            t1 = datetime.fromisoformat(erab["timestamp"][:19])
            horas_decorridas = round(max((t1 - t0).total_seconds() / 3600.0, 0.0), 2)
        except Exception:
            horas_decorridas = None

        if chuva_max >= float(reg.get("chuva_max_24h") or 0.0):
            reg["chuva_max_24h"] = round(chuva_max, 2)
            reg["estacao_dominante"] = estacao_dom

        if chuvas_est:
            reg["chuvas_estacoes_24h"] = chuvas_est

        cota_ini = float(reg["cota_inicial"])
        cota_pico_ant = float(reg.get("cota_pico") or cota_ini)

        # Marca inicio efetivo da resposta hidrologica (+3 cm sobre base ou vz > 1 cm/h)
        if reg.get("horas_ate_subida") is None:
            if (cota_atual - cota_ini) >= 3.0 or vz_atual > 1.0:
                reg["horas_ate_subida"] = horas_decorridas
                reg["ts_subida"] = erab["timestamp"]
                reg["status"] = "EM_SUBIDA"

        # Atualiza pico e lag ate o pico
        if cota_atual > cota_pico_ant:
            reg["cota_pico"] = cota_atual
            reg["ts_pico"] = erab["timestamp"]
            reg["horas_ate_pico"] = horas_decorridas
            reg["status"] = "EM_SUBIDA"
        elif (cota_pico_ant - cota_atual) >= 4.0 and vz_atual < 0:
            reg["status"] = "RECESSAO"

        reg["cota_atual"] = cota_atual
        reg["ultima_atualizacao"] = erab["timestamp"]

    LAG_FILE.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in registros) + "\n",
        encoding="utf-8",
    )
    print(f"[OK] lag_eventos.jsonl atualizado: {json.dumps(reg, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
