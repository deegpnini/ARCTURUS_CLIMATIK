
def buscar_alertas_inmet():
    """Busca alertas oficiais do INMET para a região da bacia."""
    import requests
    # API pública do INMET (simplificada)
    try:
        url = "https://apiprevmet3.inmet.gov.br/avisos"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            dados = r.json()
            # Filtrar por SC
            alertas = [a for a in dados if "SC" in a.get("estados", "") or "Santa Catarina" in a.get("estados", "")]
            if alertas:
                return alertas[0].get("titulo", "Alerta ativo")
        return "Sem alertas ativos no momento"
    except Exception:
        return "Sem alertas ativos no momento"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Boletim informativo do rio para o Telegram (com proveniência e telemetria real Defesa Civil SC)."""

import json
import os
import sys
import requests
import psycopg2
from datetime import datetime, timedelta
from html import escape
import math
from pathlib import Path
from telegram_formatador import (
    avaliar_frescor_telemetria,
    estado_coleta_defesacivil,
    enviar_com_fallback,
    formatar_boletim,
    formatar_resumo_previsao,
)

BASE = Path(__file__).resolve().parent
DB_URL = os.environ.get("DATABASE_URL", "postgresql:///arcturus")


def _numero(valor, casas=1):
    return f"{valor:.{casas}f}".replace(".", ",")

# Carrega token/chat do .env
env_file = BASE / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v.strip('"').strip("'"))

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DRY_RUN = "--dry-run" in sys.argv

if not DRY_RUN and (not TOKEN or not CHAT_ID):
    print("[ERRO] TELEGRAM_TOKEN/TELEGRAM_CHAT_ID não definidos no .env")
    sys.exit(1)

# --- 1) Cota atual, anterior e taxa horária (vz) ---
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT timestamp, cota_cm FROM leituras
    WHERE cota_cm IS NOT NULL
    ORDER BY timestamp DESC LIMIT 2
""")
rows = cur.fetchall()
if not rows:
    print("[ERRO] Sem leituras no banco")
    sys.exit(1)

ts_atual, cota_atual = rows[0]
cota_anterior = rows[1][1] if len(rows) > 1 else None
variacao = (cota_atual - cota_anterior) if cota_anterior is not None else 0.0

# --- 2) Previsão (última predição) ---
cur.execute("""
    SELECT horizonte, y_score FROM predicoes_shadow
    WHERE timestamp > NOW() - INTERVAL '20 minutes'
      AND stale = false
    ORDER BY timestamp DESC, horizonte
    LIMIT 3
""")
previsoes = {h: y for h, y in cur.fetchall()}
cur.close()
conn.close()

# --- 4) Frescor e faixa plausível da telemetria Defesa Civil SC ---
agora_local = datetime.now().astimezone()
dc_file = BASE / "data" / "chuva_defesacivil_realtime.json"
dc_status = "sem dados da Defesa Civil"
dc_fresco = False
hora_telemetria = None
estacoes_boletim = []
chuva_dc_max = None
dc_status_file = BASE / "data" / "status_defesacivil_coleta.json"
try:
    status_coleta = (
        json.loads(dc_status_file.read_text(encoding="utf-8"))
        if dc_status_file.exists()
        else None
    )
    coleta_ok, falha_coleta = estado_coleta_defesacivil(status_coleta)
    if not coleta_ok:
        dc_status = falha_coleta
except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
    print(f"[AVISO] Status da coleta Defesa Civil inválido: {exc}")
    coleta_ok = False
limites_chuva = {
    "chuva_1h_mm": 300,
    "chuva_6h_mm": 600,
    "chuva_12h_mm": 800,
    "chuva_24h_mm": 1000,
    "chuva_48h_mm": 1500,
    "chuva_72h_mm": 2000,
    "chuva_168h_mm": 3000,
}
try:
    if coleta_ok and dc_file.exists():
        dc_dados = json.loads(dc_file.read_text(encoding="utf-8"))
        ts_coleta = datetime.fromisoformat(dc_dados["timestamp_coleta"])
        if ts_coleta.tzinfo is None:
            ts_coleta = ts_coleta.replace(tzinfo=agora_local.tzinfo)
        hora_telemetria = ts_coleta.strftime("%H:%M")
        estacoes_brutas = dc_dados.get("estacoes")
        if not isinstance(estacoes_brutas, list) or not estacoes_brutas:
            raise ValueError("snapshot sem estações")

        snapshot_fresco, snapshot_status = avaliar_frescor_telemetria(
            ts_coleta, agora_local
        )
        chuva_valida = []
        horarios_frescos = []
        horarios_antigos = []
        for est in estacoes_brutas:
            if not isinstance(est, dict):
                continue
            try:
                ts_estacao = datetime.strptime(
                    est["atualizacao_estacao"], "%d/%m/%Y %H:%M:%S"
                ).replace(tzinfo=agora_local.tzinfo)
            except (KeyError, TypeError, ValueError):
                continue
            estacao_fresca, _ = avaliar_frescor_telemetria(
                ts_estacao, agora_local
            )
            if not estacao_fresca:
                horarios_antigos.append(ts_estacao)
                continue
            horarios_frescos.append(ts_estacao)
            for campo, maximo in limites_chuva.items():
                valor = est.get(campo)
                if valor is not None:
                    try:
                        numero = float(valor)
                        if not 0 <= numero <= maximo:
                            est[campo] = None
                    except (TypeError, ValueError):
                        est[campo] = None
            chuva24 = est.get("chuva_24h_mm")
            if chuva24 is not None:
                chuva_valida.append(float(chuva24))
            nome = est.get("trecho_bacia") or est.get("nome_oficial") or est.get("codigo")
            estacoes_boletim.append(
                {
                    "nome": nome,
                    "mm_1h": est.get("chuva_1h_mm"),
                    "mm_24h": est.get("chuva_24h_mm"),
                }
            )
        if snapshot_fresco and horarios_frescos:
            dc_fresco = True
            hora_mais_recente = max(horarios_frescos)
            hora_telemetria = hora_mais_recente.strftime("%H:%M")
            dc_status = (
                f"dados atualizados às {hora_telemetria} "
                f"({len(horarios_frescos)} estações)"
            )
        elif horarios_antigos:
            hora_antiga = max(horarios_antigos)
            dc_fresco = False
            dc_status = (
                f"dados de {hora_antiga:%H:%M} (desatualizados)"
            )
            estacoes_boletim = []
        else:
            dc_fresco = False
            dc_status = snapshot_status if not snapshot_fresco else "sem dados da Defesa Civil"
            estacoes_boletim = []
        if chuva_valida:
            chuva_dc_max = max(chuva_valida)
except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
    print(f"[AVISO] Telemetria Defesa Civil indisponível/inválida: {exc}")
    dc_status = "sem dados da Defesa Civil"
    dc_fresco = False
    estacoes_boletim = []
    hora_telemetria = None

if not coleta_ok:
    dc_fresco = False
    estacoes_boletim = []
    chuva_dc_max = None
    hora_telemetria = None

# Snapshot antigo pode ser exibido com rótulo explícito, mas não dirige o estado.
if not dc_fresco and dc_status.startswith("dados de"):
    estacoes_boletim = []

# --- 5) Chuva atual: usar apenas fontes com proveniência e frescor conhecidos ---
chuva_24h = chuva_dc_max if dc_fresco else None
fonte_chuva_label = (
    "Defesa Civil SC — Telemetria" if dc_fresco else "Defesa Civil SC"
)
if not dc_fresco:
    fonte_chuva_label = "Defesa Civil SC — " + dc_status

prov_file = BASE / "data" / "proveniencia_observacoes.jsonl"
try:
    if prov_file.exists():
        linhas_prov = [
            linha.strip()
            for linha in prov_file.read_text(encoding="utf-8").splitlines()
            if linha.strip()
        ]
        if linhas_prov:
            prov = json.loads(linhas_prov[-1])
            ts_prov = datetime.fromisoformat(prov["ts_ciclo_gravacao"])
            if ts_prov.tzinfo is None:
                ts_prov = ts_prov.replace(tzinfo=agora_local.tzinfo)
            idade_prov = (agora_local - ts_prov).total_seconds() / 60
            fonte = str(prov.get("fonte_dominante", ""))
            valor_prov = float(prov["estimativa_conservadora_24h_mm"])
            fonte_permitida = (
                "DEFESA_CIVIL" in fonte and dc_fresco
            ) or ("OPEN_METEO" in fonte and not dc_fresco)
            if 0 <= idade_prov <= 90 and 0 <= valor_prov <= 1000 and fonte_permitida:
                chuva_24h = max(chuva_24h or 0, valor_prov)
                fonte_chuva_label = (
                    "Fusão conservadora · Defesa Civil SC + Open-Meteo"
                    if "DEFESA_CIVIL" in fonte
                    else "Open-Meteo — Grade Bacia"
                )
except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
    print(f"[AVISO] Proveniência de chuva indisponível: {exc}")

# --- 6) Previsão do tempo com validação da data real e da atualização ---
previsao_html = ""
tempo_file = BASE / "data" / "previsao_tempo.json"
if tempo_file.exists():
    nomes_cidades = {
        "lauro_muller": "Lauro Müller",
        "orleans": "Orleans",
        "anitapolis": "Anitápolis",
        "sao_bonifacio": "São Bonifácio",
        "grao_para": "Grão-Pará",
        "rio_fortuna": "Rio Fortuna",
        "santa_rosa_de_lima": "Santa Rosa de Lima",
        "braco_do_norte": "Braço do Norte",
        "sao_ludgero": "São Ludgero",
        "pedras_grandes": "Pedras Grandes",
        "armazem": "Armazém",
        "gravatal": "Gravatal",
        "sao_martinho": "São Martinho",
        "tubarao": "Tubarão",
        "capivari_de_baixo": "Capivari de Baixo",
        "treze_de_maio": "Treze de Maio",
        "jaguaruna": "Jaguaruna",
        "sangao": "Sangão",
        "laguna": "Laguna",
    }
    regioes = [
        ("🏔️ Cabeceira (Serra)", ["lauro_muller", "orleans", "anitapolis", "sao_bonifacio",
                                  "grao_para", "rio_fortuna", "santa_rosa_de_lima"]),
        ("🌳 Médio curso", ["braco_do_norte", "sao_ludgero", "pedras_grandes", "armazem",
                          "gravatal", "sao_martinho"]),
        ("🌊 Foz e litoral", ["tubarao", "capivari_de_baixo", "treze_de_maio", "jaguaruna",
                             "sangao", "laguna"]),
    ]
    try:
        tempo = json.loads(tempo_file.read_text(encoding="utf-8"))
        meta_file = BASE / "data" / "previsao_tempo_meta.json"
        gerado_em = None
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            gerado_em = datetime.fromisoformat(meta["consulta_em"])
        else:
            gerado_em = datetime.fromtimestamp(
                tempo_file.stat().st_mtime, tz=agora_local.tzinfo
            )
        if gerado_em.tzinfo is None:
            gerado_em = gerado_em.replace(tzinfo=agora_local.tzinfo)
        idade_previsao_h = (agora_local - gerado_em).total_seconds() / 3600
        if not 0 <= idade_previsao_h <= 18:
            previsao_html = (
                "☁️ <b>Previsão meteorológica indisponível</b>\n"
                f"<i>Dados coletados em {gerado_em:%d/%m %H:%M} "
                "(desatualizados; rodada do modelo não disponível).</i>"
            )
        else:
            hoje = agora_local.date()
            datas_alvo = [
                (hoje + timedelta(days=i)).isoformat() for i in range(3)
            ]
            chuva_por_data = {data: [] for data in datas_alvo}
            chuva_por_cidade = {}
            for cidade, dias in tempo.items():
                if cidade not in nomes_cidades or not isinstance(dias, dict):
                    continue
                chuva_por_cidade[cidade] = {}
                for registro in dias.values():
                    if not isinstance(registro, dict):
                        continue
                    data = registro.get("data")
                    valor = registro.get("chuva")
                    if data not in chuva_por_data or valor is None:
                        continue
                    try:
                        valor = float(valor)
                    except (TypeError, ValueError):
                        continue
                    if not math.isfinite(valor) or not 0 <= valor <= 1000:
                        continue
                    chuva_por_data[data].append((cidade, valor))
                    chuva_por_cidade[cidade][data] = valor

            if not any(chuva_por_cidade.values()):
                previsao_html = (
                    "☁️ <b>Previsão meteorológica indisponível</b>\n"
                    "<i>A consulta recente não retornou valores válidos.</i>"
                )
            else:
                previsao_html = formatar_resumo_previsao(
                    chuva_por_cidade,
                    nomes_cidades,
                    regioes,
                    datas_alvo,
                    gerado_em,
                )
            if (
                previsao_html.startswith("☁️ <b>Previsão Open-Meteo")
                and dc_fresco
                and chuva_24h is not None
                and chuva_por_data[hoje.isoformat()]
            ):
                media_hoje = sum(
                    valor for _, valor in chuva_por_data[hoje.isoformat()]
                ) / len(chuva_por_data[hoje.isoformat()])
                previsao_html += "\n" + (
                    "⚠️ Hoje: observação Defesa Civil "
                    f"{_numero(chuva_24h)} mm/24h vs previsão diária média "
                    f"{_numero(media_hoje)} mm; períodos diferentes, "
                    "mas a previsão subestimou a chuva observada."
                )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"[AVISO] Erro ao ler previsão do tempo: {exc}")
        previsao_html = "☁️ <b>Previsão meteorológica indisponível.</b>"

tendencia = "subindo" if variacao > 0.5 else "caindo" if variacao < -0.5 else "estável"
msg = formatar_boletim(
    {
        "agora": ts_atual,
        "chuva_24h_mm": chuva_24h,
        "fonte_chuva": fonte_chuva_label,
        "status_defesacivil": dc_status,
        "cota_cm": cota_atual,
        "tendencia": tendencia,
        "projecoes": previsoes,
        "estacoes": estacoes_boletim,
        "hora_telemetria": hora_telemetria,
        "previsao_html": previsao_html,
    }
)

# --- 6.5) Camada Hidrológica: Risco Urbano vs. Fluvial + Eixo dos 3 Braços ---
try:
    from src.hidrologia.vulnerabilidade import carregar_pontos_vulnerabilidade

    pontos_vuln = carregar_pontos_vulnerabilidade()
    dc_estacoes = []
    dc_rt = BASE / "data" / "chuva_defesacivil_realtime.json"
    if dc_rt.exists():
        dc_payload = json.loads(dc_rt.read_text(encoding="utf-8"))
        dc_estacoes = dc_payload.get("estacoes") or []

    def _max_chuva_braco(termos):
        vals = [0.0]
        for est in dc_estacoes:
            if not isinstance(est, dict):
                continue
            rotulo = f"{est.get('trecho_bacia', '')} {est.get('nome_oficial', '')} {est.get('nome', '')}".lower()
            if any(t in rotulo for t in termos):
                v24 = est.get("chuva_24h_mm")
                if v24 is not None:
                    vals.append(float(v24))
        return max(vals)

    c_oeste = _max_chuva_braco(["lauro", "orleans"])
    c_norte = _max_chuva_braco(["ludgero", "grão", "grao", "braço", "braco"])
    c_leste = _max_chuva_braco(["martinho", "gravatal", "armazém", "armazem"])
    c_local_tub = _max_chuva_braco(["tubarão", "tubarao", "guarda"])

    eixos = [
        ("Ramo Oeste (Rio Tubarão — Lauro Müller/Orleans)", c_oeste),
        ("Ramo Norte (Rio Braço do Norte — São Ludgero/Grão-Pará)", c_norte),
        ("Ramo Leste (Rio Capivari — São Martinho/Gravatal)", c_leste),
    ]
    eixo_dom, chuva_eixo_dom = max(eixos, key=lambda x: x[1])

    risco_fluvial = (
        (cota_atual is not None and float(cota_atual) >= 220.0)
        or (variacao is not None and float(variacao) >= 5.0)
        or (chuva_eixo_dom >= 15.0)
    )
    risco_urbano = c_local_tub >= 15.0

    if risco_fluvial and risco_urbano:
        diag_risco = "⚠️ <b>Vigilância Combinada (Fluvial + Urbano):</b> Onda de montante + chuva local na planície."
        tipos_alvo = {"fluvial", "urbano", "misto", "confluencia", "planicie"}
    elif risco_fluvial:
        diag_risco = "🌊 <b>Risco Fluvial (Calha Principal):</b> Propagação de onda vinda de montante pela régua ERAB."
        tipos_alvo = {"fluvial", "misto", "confluencia", "planicie"}
    elif risco_urbano:
        diag_risco = "🏙️ <b>Risco Urbano (Macro/Microdrenagem):</b> Chuva concentrada em Tubarão; calha ainda sob controle."
        tipos_alvo = {"urbano", "drenagem", "misto"}
    else:
        diag_risco = "🟢 <b>Baixo Risco Hidrológico:</b> Sem gatilho ativo de transbordamento fluvial ou alagamento urbano."
        tipos_alvo = set()

    bloco_hidro = [
        "",
        "🧭 <b>Diagnóstico Espacial (3 Braços & Vulnerabilidade)</b>",
        diag_risco,
        f"• <b>Eixo dominante:</b> {eixo_dom} ({chuva_eixo_dom:.1f} mm/24h)",
    ]

    if tipos_alvo and pontos_vuln:
        filtrados = [
            p for p in pontos_vuln
            if any(t in str(p.get("tipo", "")).lower() for t in tipos_alvo)
        ][:3]
        if filtrados:
            nomes_pts = ", ".join(p.get("nome", "") for p in filtrados if p.get("nome"))
            bloco_hidro.append(f"• <b>Pontos críticos em atenção:</b> {nomes_pts}")

    msg = msg.rstrip() + "\n" + "\n".join(bloco_hidro)
except Exception as exc_hidro:
    print(f"[AVISO] Camada espacial nao anexada ao boletim: {exc_hidro}")


def anexar_contexto_defesa_civil(texto_msg: str) -> str:
    """Anexa comunicados da Defesa Civil SC apenas se houver alerta para a Bacia do Tubarão/Sul."""
    try:
        arq_ctx = BASE / "data" / "validacao_contextual_noticias.json"
        if not arq_ctx.exists():
            return texto_msg
        dados_ctx = json.loads(arq_ctx.read_text(encoding="utf-8"))
        alertas_locais = [
            n for n in dados_ctx.get("noticias", [])
            if n.get("relevancia") == "alta_local"
        ]
        if alertas_locais:
            titulos = "\n".join(f"• {a['titulo']}" for a in alertas_locais[:2])
            return texto_msg.rstrip() + f"\n\n🚨 <b>Comunicado Oficial — Sul / Bacia:</b>\n{titulos}"
    except Exception:
        pass
    return texto_msg

msg = anexar_contexto_defesa_civil(msg)

if DRY_RUN:
    print("=== DRY-RUN: MENSAGEM QUE SERÁ ENVIADA AO TELEGRAM ===")
    print(msg)
    sys.exit(0)

# --- 7) Envia para o Telegram ---
url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
resp, usou_fallback = enviar_com_fallback(requests.post, url, CHAT_ID, msg)
if resp.status_code == 200:
    detalhe_envio = " em texto simples (fallback)" if usou_fallback else ""
    print(
        f"[OK] Boletim enviado{detalhe_envio} "
        f"às {datetime.now().strftime('%H:%M')}"
    )
else:
    print(f"[ERRO] Telegram retornou {resp.status_code}: {resp.text}")
    sys.exit(1)
