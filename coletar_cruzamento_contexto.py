#!/usr/bin/env python3
"""
coletar_cruzamento_contexto.py — Coleta fontes oficiais acessíveis (HTTP/RSS)
e páginas/notícias/fóruns extras SOMENTE para cruzamento contextual isolado.
Não altera telemetria, y_true, previsões nem calibração.
"""
import html
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import requests

BASE = Path.home() / "projetos" / "ARCTURUS_CLIMATIK"
OUT = BASE / "data" / "cruzamento_contexto_atual.json"

FONTES = {
    "defesa_civil_sc_rss": "https://www.defesacivil.sc.gov.br/feed/",
    "sctd_rss": "https://sctd.com.br/feed/",
    "ndmais_rss": "https://ndmais.com.br/feed/",
    # Adicione aqui URLs de páginas, fóruns ou comunicados extras para cruzamento:
    # "forum_ou_pagina_extra": "https://exemplo.com.br/topico-ou-pagina",
}

PALAVRAS_CHAVE = [
    "tubarão", "tubarao", "orleans", "lauro müller", "lauro muller",
    "grão-pará", "grao-para", "são ludgero", "sao ludgero",
    "braço do norte", "braco do norte", "capivari", "gravatal",
    "laguna", "urussanga", "defesa civil", "inmet", "chuva",
    "enchente", "alagamento", "cheia", "rio", "temporal", "maré", "mare",
]


def limpar_texto(s: str) -> str:
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.DOTALL)
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def idade_em_horas(pub_str: str, agora_utc: datetime):
    if not pub_str:
        return None
    try:
        dt = parsedate_to_datetime(pub_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return round((agora_utc - dt.astimezone(timezone.utc)).total_seconds() / 3600.0, 2)
    except Exception:
        return None


def extrair_fonte(nome: str, url: str, agora_utc: datetime) -> dict:
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "ARCTURUS_CLIMATIK_XREF/1.0"})
        status = resp.status_code
        if status != 200:
            return {"fonte": nome, "url": url, "status_http": status, "itens": []}

        corpo = resp.text
        itens_xml = re.findall(r"<item>(.*?)</item>|<entry>(.*?)</entry>", corpo, flags=re.DOTALL)
        achados = []

        if itens_xml:
            for grp in itens_xml[:30]:
                raw = grp[0] or grp[1]
                t_m = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.DOTALL)
                d_m = re.search(r"<pubDate[^>]*>(.*?)</pubDate>|<updated[^>]*>(.*?)</updated>", raw, flags=re.DOTALL)
                l_m = re.search(r"<link[^>]*>(.*?)</link>|<link[^>]*href=[\"']([^\"']+)[\"']", raw, flags=re.DOTALL)
                titulo = limpar_texto(t_m.group(1)) if t_m else ""
                pub_raw = (d_m.group(1) or d_m.group(2)) if d_m else ""
                pub_str = limpar_texto(pub_raw)
                link = limpar_texto((l_m.group(1) or l_m.group(2))) if l_m else url
                texto_busca = f"{titulo} {limpar_texto(raw)}".lower()
                if any(k in texto_busca for k in PALAVRAS_CHAVE):
                    achados.append({
                        "titulo": titulo[:180],
                        "data_raw": pub_str,
                        "idade_horas": idade_em_horas(pub_str, agora_utc),
                        "link": link,
                    })
        else:
            # Fallback para página HTML / fórum: extrai títulos e trechos com palavra-chave
            titulo_pag = ""
            h_m = re.search(r"<title[^>]*>(.*?)</title>", corpo, flags=re.DOTALL | re.IGNORECASE)
            if h_m:
                titulo_pag = limpar_texto(h_m.group(1))
            texto_limpo = limpar_texto(corpo)
            for match in re.finditer(r".{0,120}(?:tubar[aã]o|orleans|lauro m[uü]ller|defesa civil|inmet|enchente|alagamento|cheia).{0,120}", texto_limpo, flags=re.IGNORECASE):
                trecho = match.group(0).strip()
                if trecho and len(achados) < 15:
                    achados.append({
                        "titulo": titulo_pag[:120] or nome,
                        "trecho": trecho,
                        "link": url,
                    })

        return {"fonte": nome, "url": url, "status_http": status, "itens": achados}
    except Exception as e:
        return {"fonte": nome, "url": url, "erro": str(e), "itens": []}


def main():
    agora_utc = datetime.now(timezone.utc)
    resultados = [extrair_fonte(k, v, agora_utc) for k, v in FONTES.items()]
    payload = {
        "coletado_em_local": datetime.now().astimezone().isoformat(),
        "finalidade": "cruzamento_contextual_isolado_nao_usar_como_sensor_nem_y_true",
        "fontes": resultados,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Salvo em {OUT}")
    for r in resultados:
        print(f" - {r['fonte']}: http={r.get('status_http')} erro={r.get('erro')} itens={len(r.get('itens', []))}")
        for it in r.get("itens", [])[:3]:
            print(f"     * {it.get('titulo') or it.get('trecho','')[:95]}")


if __name__ == "__main__":
    main()
