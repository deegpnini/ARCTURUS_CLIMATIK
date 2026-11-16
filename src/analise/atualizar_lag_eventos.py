#!/usr/bin/env python3
"""
atualizar_lag_eventos.py — Rastreia a resposta hidrologica (lag e amplitude)
em duas escalas:
  1) Evento completo: cota_pre_evento -> cota_atual (delta_total)
  2) Pulso/repique local: cota_base_repique -> cota_atual (delta_repique)
Separa tambem dominante_24h (acumulado do evento) e dominante_6h (chuva recente).
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
EVENTO_FILE = BASE_DIR / "data" / "evento_atual_bacia.json"
DCSC_FILE = BASE_DIR / "data" / "chuva_defesacivil_realtime.json"
LAG_FILE = BASE_DIR / "data" / "lag_eventos.jsonl"


def ler_serie_erab(horas=12):
    """Busca leituras validas das ultimas N horas ordenadas cronologicamente."""
    sql = f"""
    SELECT
        to_char(timestamp, 'YYYY-MM-DD"T"HH24:MI:SS'),
        cota_cm,
        COALESCE(vz_cm_h, 0)
    FROM leituras
    WHERE qc = 'VALIDO'
      AND cota_cm IS NOT NULL
      AND timestamp >= NOW() - INTERVAL '{int(horas)} hours'
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


def ler_telemetria_dcsc():
    """Extrai acumulados de 24h e 6h por estacao e identifica ambas as dominantes."""
    if not DCSC_FILE.exists():
        return {}, {}, None, 0.0, None, 0.0

    dados = json.loads(DCSC_FILE.read_text(encoding="utf-8"))
    estacoes = dados.get("estacoes", [])

    chuvas_24h = {}
    chuvas_6h = {}
    dom_24h, max_24h = None, -1.0
    dom_6h, max_6h = None, -1.0

    for est in estacoes:
        nome = (est.get("nome") or "").strip()
        if not nome:
            continue
        c24 = est.get("chuva_24h_mm")
        c6 = est.get("chuva_6h_mm")

        if c24 is not None:
            v24 = float(c24)
            chuvas_24h[nome] = v24
            if v24 > max_24h:
                max_24h = v24
                dom_24h = nome

        if c6 is not None:
            v6 = float(c6)
            chuvas_6h[nome] = v6
            if v6 > max_6h:
                max_6h = v6
                dom_6h = nome

    return (
        chuvas_24h,
        chuvas_6h,
        dom_24h,
        max(max_24h, 0.0),
        dom_6h,
        max(max_6h, 0.0),
    )


def detectar_base_repique(serie):
    """
    Identifica a cota de base local imediatamente antes do repique atual
    (ex: patamar de 97 cm antes do salto para 105 cm) e o momento de inicio da subida.
    """
    if len(serie) < 2:
        pt = serie[-1]
        return pt["cota_cm"], pt["timestamp"], None

    # Percorre de tras para frente para achar o ultimo patamar estavel antes da subida atual
    idx_base = len(serie) - 1
    for i in range(len(serie) - 2, -1, -1):
        if serie[i]["cota_cm"] <= serie[idx_base]["cota_cm"]:
            idx_base = i
        elif (serie[i]["cota_cm"] - serie[idx_base]["cota_cm"]) > 2.0:
            # Encontrou uma onda anterior mais alta; para no vale entre ondas
            break

    base_pt = serie[idx_base]
    cota_base = base_pt["cota_cm"]

    # Primeiro ponto apos a base em que a cota subiu >= 3 cm
    ponto_subida = next(
        (p for p in serie[idx_base + 1:] if (p["cota_cm"] - cota_base) >= 3.0),
        None,
    )
    return cota_base, base_pt["timestamp"], ponto_subida


def main():
    if not EVENTO_FILE.exists():
        print("[LAG] evento_atual_bacia.json ausente; aguardando snapshot.")
        return

    evento = json.loads(EVENTO_FILE.read_text(encoding="utf-8"))
    serie = ler_serie_erab(horas=12)
    if not serie:
        print("[LAG] Nenhuma leitura VALIDA recente encontrada no PostgreSQL.")
        return

    erab = serie[-1]
    cota_atual = erab["cota_cm"]
    vz_atual = erab["vz_cm_h"]

    # Escala 1: Base hidrologica completa (menor cota pre-evento nas ultimas 12h)
    pt_pre = min(serie, key=lambda x: x["cota_cm"])
    cota_pre_evento = pt_pre["cota_cm"]

    # Escala 2: Base local do repique atual (ex: 97 cm)
    cota_base_repique, ts_base_repique, ponto_subida = detectar_base_repique(serie)

    chuvas_24h, chuvas_6h, dom_24h, max_24h, dom_6h, max_6h = ler_telemetria_dcsc()

    agora = datetime.now()
    evento_id = str(
        evento.get("evento_id")
        or evento.get("id")
        or agora.strftime("%Y%m%d")
    )

    if not dom_24h:
        dom_24h = evento.get("estacao_dominante") or "Desconhecida"
        max_24h = float(evento.get("chuva_max_24h") or 0.0)

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

    if idx_existente is None:
        reg = {
            "evento": evento_id,
            "inicio_evento": evento.get("inicio") or pt_pre["timestamp"],
            "cota_pre_evento": cota_pre_evento,
        }
        registros.append(reg)
    else:
        reg = registros[idx_existente]
        # Preserva a menor cota pre-evento (ex: 66.0 cm)
        cota_pre_ant = reg.get("cota_pre_evento") or reg.get("cota_inicial") or cota_pre_evento
        reg["cota_pre_evento"] = min(float(cota_pre_ant), cota_pre_evento)
        reg.pop("cota_inicial", None)
        reg.pop("delta_cota", None)

    cota_pre = float(reg["cota_pre_evento"])
    delta_repique = round(cota_atual - cota_base_repique, 2)
    delta_total = round(cota_atual - cota_pre, 2)

    # Calcula lag ate a subida do repique atual (a partir do inicio do repique)
    t_base = datetime.fromisoformat(ts_base_repique[:19])
    if ponto_subida is not None:
        t_sub = datetime.fromisoformat(ponto_subida["timestamp"][:19])
        horas_ate_subida = round(max((t_sub - t_base).total_seconds() / 3600.0, 0.0), 2)
        ts_subida = ponto_subida["timestamp"]
    else:
        horas_ate_subida = None
        ts_subida = None

    # Calcula pico e lag ate o pico desde o inicio do repique
    cota_pico_ant = float(reg.get("cota_pico") or cota_atual)
    if cota_atual >= cota_pico_ant:
        t_pico = datetime.fromisoformat(erab["timestamp"][:19])
        cota_pico = cota_atual
        ts_pico = erab["timestamp"]
        horas_ate_pico = round(max((t_pico - t_base).total_seconds() / 3600.0, 0.0), 2)
    else:
        cota_pico = cota_pico_ant
        ts_pico = reg.get("ts_pico")
        horas_ate_pico = reg.get("horas_ate_pico")

    if delta_repique >= 3.0 and cota_atual >= cota_pico:
        status = "EM_SUBIDA"
    elif (cota_pico - cota_atual) >= 4.0 and vz_atual < 0:
        status = "RECESSAO"
    else:
        status = "ESTAVEL_OBSERVACAO"

    reg.update({
        "ultima_atualizacao": erab["timestamp"],
        "dominante_24h": dom_24h,
        "chuva_max_24h": round(max_24h, 2),
        "dominante_6h": dom_6h,
        "chuva_max_6h": round(max_6h, 2),
        "cota_pre_evento": cota_pre,
        "cota_base_repique": cota_base_repique,
        "ts_base_repique": ts_base_repique,
        "cota_atual": cota_atual,
        "delta_repique": delta_repique,
        "delta_total": delta_total,
        "cota_pico": cota_pico,
        "ts_pico": ts_pico,
        "ts_subida": ts_subida,
        "horas_ate_subida": horas_ate_subida,
        "horas_ate_pico": horas_ate_pico,
        "status": status,
        "chuvas_estacoes_24h": chuvas_24h,
        "chuvas_estacoes_6h": chuvas_6h,
    })

    LAG_FILE.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in registros) + "\n",
        encoding="utf-8",
    )
    print("=== REGISTRO ATUALIZADO EM data/lag_eventos.jsonl ===")
    print(json.dumps(reg, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
