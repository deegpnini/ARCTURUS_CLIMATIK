#!/usr/bin/env python3
"""
validar_contexto_noticias.py — Coleta notícias e comunicados oficiais de SC
e cruza com os dados do ARCTURUS para validação contextual (não primária).
"""

import html
import json
import re
import requests
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

FONTES = {
    "SCTODODIA": "https://sctd.com.br/feed/",
    "Portal Click Sul": "https://portalclicksul.com.br/feed/",
    "ND Mais": "https://ndmais.com.br/feed/",
}

PALAVRAS_CHAVE = [
    "tubarão", "rio tubarão", "enchente", "alagamento", "chuva",
    "defesa civil", "el niño", "cheia", "temporal", "sul de sc",
]

MUNICIPIOS_BACIA_SUL = [
    "tubarão", "capivari de baixo", "são ludgero", "braço do norte",
    "orleans", "lauro müller", "lauro muller", "grão-pará", "grao-para",
    "pedras grandes", "gravatal", "armazém", "armazem", "são martinho",
    "sao martinho", "laguna", "jaguaruna", "sangão", "sangao",
    "treze de maio", "urussanga", "amurel", "sul de sc", "litoral sul",
]


def limpar_texto_rss(raw: str) -> str:
    sem_tags = re.sub(r"<[^>]+>", "", raw)
    return html.unescape(sem_tags).strip()


def buscar_noticias_rss(url: str, nome_fonte: str) -> list[dict]:
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "ARCTURUS_CLIMATIK/1.0"})
        if r.status_code != 200:
            return []

        itens = re.findall(r"<item>(.*?)</item>", r.text, re.DOTALL)
        noticias = []
        for item in itens[:20]:
            titulo = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
            link = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
            data = re.search(r"<pubDate>(.*?)</pubDate>", item, re.DOTALL)
            if not titulo:
                continue

            titulo_limpo = limpar_texto_rss(titulo.group(1))
            texto_completo = (titulo_limpo + " " + limpar_texto_rss(item)).lower()

            if any(p in texto_completo for p in PALAVRAS_CHAVE):
                noticias.append({
                    "fonte": nome_fonte,
                    "titulo": titulo_limpo,
                    "link": link.group(1).strip() if link else "",
                    "data": data.group(1).strip() if data else "",
                })
        return noticias
    except Exception as e:
        print(f"   ⚠️ {nome_fonte}: {e}")
        return []


def buscar_noticias_defesa_civil() -> list[dict]:
    try:
        url = "https://www.defesacivil.sc.gov.br/feed/"
        r = requests.get(url, timeout=15, headers={"User-Agent": "ARCTURUS_CLIMATIK/1.0"})
        if r.status_code != 200:
            return []

        itens = re.findall(r"<item>(.*?)</item>", r.text, re.DOTALL)
        noticias = []
        for item in itens[:12]:
            titulo = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
            link = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
            data = re.search(r"<pubDate>(.*?)</pubDate>", item, re.DOTALL)
            if titulo:
                noticias.append({
                    "fonte": "Defesa Civil SC",
                    "titulo": limpar_texto_rss(titulo.group(1)),
                    "link": link.group(1).strip() if link else "",
                    "data": data.group(1).strip() if data else "",
                })
        return noticias
    except Exception as e:
        print(f"   ⚠️ Defesa Civil SC: {e}")
        return []


def cruzar_com_arcturus(noticias: list[dict]) -> tuple[dict, list[dict]]:
    arcturus_data = {}

    try:
        import psycopg2
        conn = psycopg2.connect("postgresql:///arcturus")
        cur = conn.cursor()
        cur.execute("SELECT timestamp, cota_cm FROM leituras WHERE qc = 'VALIDO' ORDER BY timestamp DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            arcturus_data["cota_atual"] = {"timestamp": row[0].isoformat(), "cota_cm": float(row[1])}
        cur.close()
        conn.close()
    except Exception:
        arcturus_data["cota_atual"] = None

    try:
        log_sombra = BASE_DIR / "logs" / "sombra_v11c.jsonl"
        if log_sombra.exists():
            linhas = log_sombra.read_text(encoding="utf-8").strip().split("\n")
            if linhas:
                ultima = json.loads(linhas[-1])
                arcturus_data["v11c"] = {
                    "cota_atual_cm": ultima.get("cota_atual_cm"),
                    "delta_pred_24h_cm": ultima.get("delta_pred_24h_cm"),
                    "cota_prevista_24h_cm": ultima.get("cota_prevista_24h_cm"),
                    "confianca": ultima.get("confianca_operacional"),
                }
    except Exception:
        arcturus_data["v11c"] = None

    noticias_classificadas = []
    for n in noticias:
        titulo_lower = n["titulo"].lower()
        na_bacia_sul = any(m in titulo_lower for m in MUNICIPIOS_BACIA_SUL)
        escopo = "BACIA_TUBARAO_SUL" if na_bacia_sul else "ESTADUAL_GERAL"

        if any(k in titulo_lower for k in ("cheia", "enchente", "alagamento", "temporal")):
            relevancia = "alta_local" if na_bacia_sul else "alta_estadual"
        elif "el niño" in titulo_lower or "defesa civil" in titulo_lower or "nota meteorológica" in titulo_lower:
            relevancia = "media"
        else:
            relevancia = "geral"

        n["escopo"] = escopo
        n["relevancia"] = relevancia
        noticias_classificadas.append(n)

    return arcturus_data, noticias_classificadas


def main():
    print("=" * 70)
    print("VALIDAÇÃO CONTEXTUAL — ARCTURUS vs NOTÍCIAS OFICIAIS")
    print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 70)

    todas_noticias = []
    for nome, url in FONTES.items():
        noticias = buscar_noticias_rss(url, nome)
        todas_noticias.extend(noticias)
        print(f"   {nome}: {len(noticias)} relevantes")

    noticias_dc = buscar_noticias_defesa_civil()
    todas_noticias.extend(noticias_dc)
    print(f"   Defesa Civil SC: {len(noticias_dc)} comunicados")

    arcturus_data, noticias_relevantes = cruzar_com_arcturus(todas_noticias)

    ordem = {"alta_local": 0, "alta_estadual": 1, "media": 2, "geral": 3}
    noticias_relevantes.sort(key=lambda x: ordem.get(x["relevancia"], 3))

    print("\n" + "=" * 70)
    print("DADOS DO ARCTURUS")
    print("=" * 70)
    if arcturus_data.get("cota_atual"):
        c = arcturus_data["cota_atual"]
        print(f"🌊 Cota atual: {c['cota_cm']:.1f} cm ({c['cota_cm']/100:.2f} m) [{c['timestamp']}]")
    if arcturus_data.get("v11c"):
        v = arcturus_data["v11c"]
        print(f"🔭 Previsão v11c (24h): {v['cota_prevista_24h_cm']:.1f} cm ({v['delta_pred_24h_cm']:+.1f} cm) · {v['confianca']}")

    print("\n" + "=" * 70)
    print("NOTÍCIAS E COMUNICADOS CLASSIFICADOS")
    print("=" * 70)
    icones = {"alta_local": "🚨", "alta_estadual": "🟠", "media": "🟡", "geral": "⚪"}
    for n in noticias_relevantes[:15]:
        print(f"\n{icones.get(n['relevancia'], '⚪')} [{n['fonte']} | {n['escopo']}] {n['titulo']}")
        if n.get("data"):
            print(f"   Data: {n['data']}")

    resultado = {
        "timestamp_consulta": datetime.now().isoformat(),
        "arcturus": arcturus_data,
        "noticias": noticias_relevantes[:15],
    }
    saida = DATA_DIR / "validacao_contextual_noticias.json"
    saida.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")

    alta_local = [n for n in noticias_relevantes if n["relevancia"] == "alta_local"]
    alta_est = [n for n in noticias_relevantes if n["relevancia"] == "alta_estadual"]

    print("\n" + "=" * 70)
    print("VEREDITO CONTEXTUAL")
    print("=" * 70)
    print(f"🚨 Alertas na Bacia do Tubarão / Sul: {len(alta_local)}")
    print(f"🟠 Alertas em outras regiões de SC:   {len(alta_est)}")
    print(f"✅ JSON salvo em: {saida}")


if __name__ == "__main__":
    main()
