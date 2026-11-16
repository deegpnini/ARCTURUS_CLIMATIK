#!/usr/bin/env python3
"""
atualizar_lag_eventos.py — Rastreia a resposta hidrologica (lag e amplitude)
em duas escalas temporais (evento completo vs. repique local) e calcula
a assinatura espacial da chuva por setor da bacia (cabeceira vs. medio curso).
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
EVENTO_FILE = BASE_DIR / "data" / "evento_atual_bacia.json"
DCSC_FILE = BASE_DIR / "data" / "chuva_defesacivil_realtime.json"
LAG_FILE = BASE_DIR / "data" / "lag_eventos.jsonl"

CODIGOS_CABECEIRA = {"DCSC-00054", "DCSC-00046", "DCSC-00151"}  # Lauro Muller, Orleans, Grao-Para
CODIGOS_MEDIO_CURSO = {"DCSC-00122"}  # Sao Ludgero
CODIGOS_BACIA_PRINCIPAL = CODIGOS_CABECEIRA | CODIGOS_MEDIO_CURSO | {"DCSC-00048"}  # + Tubarao/Guarda


def ler_serie_erab(horas=12):
    """Busca leituras validas das ultimas N horas ordenadas cronologicamente."""
    sql = f"""
    SELECT
        to_char(timestamp, 'YYYY-MM-DD"T"HH24:MI:SS'),
        ROUND(cota_cm::numeric, 2),
        ROUND(COALESCE(vz_cm_h, 0)::numeric, 2)
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
            "cota_cm": round(float(cota_s), 2),
            "vz_cm_h": round(float(vz_s), 2),
        })
    return serie


def _media(vals):
    validos = [v for v in vals if v is not None]
    return round(sum(validos) / len(validos), 2) if validos else None


def ler_telemetria_dcsc():
    """
    Extrai acumulados de 24h e 6h por estacao (usando trecho_bacia / nome_oficial),
    identifica dominante_24h e dominante_6h, e calcula medias espaciais por setor.
    """
    if not DCSC_FILE.exists():
        return {}

    dados = json.loads(DCSC_FILE.read_text(encoding="utf-8"))
    lista = dados.get("estacoes") or dados.get("pontos") or []

    chuvas_24h = {}
    chuvas_6h = {}
    dom_24h, max_24h = None, -1.0
    dom_6h, max_6h = None, -1.0

    vals_cab_24h, vals_med_24h, vals_bacia_24h = [], [], []
    vals_cab_6h, vals_med_6h, vals_bacia_6h = [], [], []

    for est in lista:
        cod = (est.get("codigo") or "").strip()
        nome = (
            est.get("trecho_bacia")
            or est.get("nome_oficial")
            or est.get("nome")
            or est.get("estacao")
            or cod
        ).strip()
        if not nome:
            continue

        c24 = est.get("chuva_24h_mm") if est.get("chuva_24h_mm") is not None else est.get("chuva_24h")
        c6 = est.get("chuva_6h_mm") if est.get("chuva_6h_mm") is not None else est.get("chuva_6h")

        if c24 is not None:
            v24 = round(float(c24), 2)
            chuvas_24h[nome] = v24
            if v24 > max_24h:
                max_24h = v24
                dom_24h = nome
            if cod in CODIGOS_CABECEIRA:
                vals_cab_24h.append(v24)
            if cod in CODIGOS_MEDIO_CURSO:
                vals_med_24h.append(v24)
            if cod in CODIGOS_BACIA_PRINCIPAL:
                vals_bacia_24h.append(v24)

        if c6 is not None:
            v6 = round(float(c6), 2)
            chuvas_6h[nome] = v6
            if v6 > max_6h:
                max_6h = v6
                dom_6h = nome
            if cod in CODIGOS_CABECEIRA:
                vals_cab_6h.append(v6)
            if cod in CODIGOS_MEDIO_CURSO:
                vals_med_6h.append(v6)
            if cod in CODIGOS_BACIA_PRINCIPAL:
                vals_bacia_6h.append(v6)

    return {
        "chuvas_24h": chuvas_24h,
        "chuvas_6h": chuvas_6h,
        "dom_24h": dom_24h,
        "max_24h": round(max(max_24h, 0.0), 2),
        "dom_6h": dom_6h,
        "max_6h": round(max(max_6h, 0.0), 2),
        "chuva_media_bacia": _media(vals_bacia_24h),
        "chuva_cabeceira": _media(vals_cab_24h),
        "chuva_medio_curso": _media(vals_med_24h),
        "chuva_media_bacia_6h": _media(vals_bacia_6h),
        "chuva_cabeceira_6h": _media(vals_cab_6h),
        "chuva_medio_curso_6h": _media(vals_med_6h),
    }


def detectar_base_repique(serie):
    """
    Identifica o ultimo patamar estavel (variacao <= 1 cm) imediatamente antes
    da subida atual (ex: 97 cm as 21:00 antes do salto para 105 cm as 21:15).
    """
    if len(serie) < 2:
        pt = serie[-1]
        return pt["cota_cm"], pt["timestamp"], None

    idx_base = len(serie) - 1
    for i in range(len(serie) - 2, -1, -1):
        diff = serie[idx_base]["cota_cm"] - serie[i]["cota_cm"]
        if diff >= 2.0:
            idx_base = i
        elif abs(diff) <= 1.0 and idx_base < len(serie) - 1:
            idx_base = i
        elif idx_base < len(serie) - 1:
            break

    cota_base = serie[idx_base]["cota_cm"]

    idx_fim_patamar = idx_base
    while idx_fim_patamar + 1 < len(serie) and abs(serie[idx_fim_patamar + 1]["cota_cm"] - cota_base) <= 1.0:
        idx_fim_patamar += 1

    fim_patamar_pt = serie[idx_fim_patamar]
    ponto_subida = next(
        (p for p in serie[idx_fim_patamar + 1:] if (p["cota_cm"] - cota_base) >= 3.0),
        None,
    )
    return cota_base, fim_patamar_pt["timestamp"], ponto_subida


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

    pt_pre = min(serie, key=lambda x: x["cota_cm"])
    cota_pre_evento = pt_pre["cota_cm"]

    cota_base_repique, ts_base_repique, ponto_subida = detectar_base_repique(serie)
    tel = ler_telemetria_dcsc()

    agora = datetime.now()
    evento_id = str(
        evento.get("evento_id")
        or evento.get("id")
        or agora.strftime("%Y%m%d")
    )

    dom_24h = tel.get("dom_24h") or evento.get("estacao_dominante") or "Desconhecida"
    max_24h = tel.get("max_24h") if tel.get("dom_24h") else round(float(evento.get("chuva_max_24h") or 0.0), 2)

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
        cota_pre_ant = reg.get("cota_pre_evento") or reg.get("cota_inicial") or cota_pre_evento
        reg["cota_pre_evento"] = round(min(float(cota_pre_ant), cota_pre_evento), 2)
        reg.pop("cota_inicial", None)
        reg.pop("delta_cota", None)

    cota_pre = round(float(reg["cota_pre_evento"]), 2)
    delta_repique = round(cota_atual - cota_base_repique, 2)
    delta_total = round(cota_atual - cota_pre, 2)

    t_base = datetime.fromisoformat(ts_base_repique[:19])
    if ponto_subida is not None:
        t_sub = datetime.fromisoformat(ponto_subida["timestamp"][:19])
        horas_ate_subida = round(max((t_sub - t_base).total_seconds() / 3600.0, 0.0), 2)
        ts_subida = ponto_subida["timestamp"]
    else:
        horas_ate_subida = None
        ts_subida = None

    cota_pico_ant = round(float(reg.get("cota_pico") or cota_atual), 2)
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
        "chuva_max_24h": max_24h,
        "dominante_6h": tel.get("dom_6h"),
        "chuva_max_6h": tel.get("max_6h"),
        "chuva_media_bacia": tel.get("chuva_media_bacia"),
        "chuva_cabeceira": tel.get("chuva_cabeceira"),
        "chuva_medio_curso": tel.get("chuva_medio_curso"),
        "chuva_media_bacia_6h": tel.get("chuva_media_bacia_6h"),
        "chuva_cabeceira_6h": tel.get("chuva_cabeceira_6h"),
        "chuva_medio_curso_6h": tel.get("chuva_medio_curso_6h"),
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
        "chuvas_estacoes_24h": tel.get("chuvas_24h", {}),
        "chuvas_estacoes_6h": tel.get("chuvas_6h", {}),
    })

    LAG_FILE.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in registros) + "\n",
        encoding="utf-8",
    )
    print("=== REGISTRO ESPACIAL E TEMPORAL ATUALIZADO ===")
    print(json.dumps(reg, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
