#!/usr/bin/env python3
"""
cruzar_boletim_fontes.py — Cruza o estado atual do ARCTURUS (snapshot, previsão,
contexto salvo) com feeds públicos acessíveis (Defesa Civil SC / imprensa regional),
sem alterar o pipeline nem os modelos.
"""
import html
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import requests

BASE = Path.home() / "projetos" / "ARCTURUS_CLIMATIK"
OUT = BASE / "data" / "cruzamento_web_oficial_20261127.json"

FEEDS = {
    "Defesa Civil SC": "https://www.defesacivil.sc.gov.br/feed/",
    "SCTODODIA": "https://sctd.com.br/feed/",
    "Portal Click Sul": "https://portalclicksul.com.br/feed/",
    "ND Mais": "https://ndmais.com.br/feed/",
}

TERMOS = [
    "tubarão", "tubarao", "orleans", "lauro müller", "lauro muller",
    "grão-pará", "grao-para", "são ludgero", "sao ludgero",
    "braço do norte", "braco do norte", "capivari", "gravatal",
    "laguna", "urussanga", "defesa civil", "inmet", "chuva",
    "enchente", "alagamento", "cheia", "rio", "temporal",
]


def ler_json_seguro(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        return {"_erro": str(e)}


def limpar_xml(s: str) -> str:
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.DOTALL)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def coletar_feeds():
    achados = []
    agora_utc = datetime.now(timezone.utc)
    for nome, url in FEEDS.items():
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "ARCTURUS_CLIMATIK/1.0"})
            if r.status_code != 200:
                achados.append({"fonte": nome, "status_http": r.status_code, "itens": []})
                continue
            itens_xml = re.findall(r"<item>(.*?)</item>", r.text, flags=re.DOTALL)
            filtrados = []
            for raw in itens_xml[:25]:
                t_m = re.search(r"<title>(.*?)</title>", raw, flags=re.DOTALL)
                d_m = re.search(r"<pubDate>(.*?)</pubDate>", raw, flags=re.DOTALL)
                l_m = re.search(r"<link>(.*?)</link>", raw, flags=re.DOTALL)
                titulo = limpar_xml(t_m.group(1)) if t_m else ""
                pub_str = limpar_xml(d_m.group(1)) if d_m else ""
                link = limpar_xml(l_m.group(1)) if l_m else ""
                idade_h = None
                try:
                    dt = parsedate_to_datetime(pub_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    idade_h = round((agora_utc - dt.astimezone(timezone.utc)).total_seconds() / 3600.0, 2)
                except Exception:
                    pass
                texto = f"{titulo} {limpar_xml(raw)}".lower()
                if any(k in texto for k in TERMOS):
                    filtrados.append({
                        "titulo": titulo,
                        "pubDate": pub_str,
                        "idade_horas": idade_h,
                        "link": link,
                    })
            achados.append({"fonte": nome, "status_http": 200, "itens": filtrados})
        except Exception as e:
            achados.append({"fonte": nome, "erro": str(e), "itens": []})
    return achados


def main():
    dc_rt = ler_json_seguro(BASE / "data" / "chuva_defesacivil_realtime.json")
    prev_t = ler_json_seguro(BASE / "data" / "previsao_tempo.json")
    ctx_n = ler_json_seguro(BASE / "data" / "validacao_contextual_noticias.json")
    feeds = coletar_feeds()

    relatorio = {
        "executado_em": datetime.now().astimezone().isoformat(),
        "arcturus_defesa_civil_rt": {
            "timestamp_coleta": dc_rt.get("timestamp_coleta") if isinstance(dc_rt, dict) else None,
            "pior_caso_bacia": dc_rt.get("pior_caso_bacia") if isinstance(dc_rt, dict) else None,
            "estacoes": dc_rt.get("estacoes") if isinstance(dc_rt, dict) else None,
        },
        "arcturus_previsao_tubarao": (
            prev_t.get("tubarao") if isinstance(prev_t, dict) and "tubarao" in prev_t else None
        ),
        "arcturus_contexto_salvo_ts": (
            ctx_n.get("timestamp_consulta") if isinstance(ctx_n, dict) else None
        ),
        "feeds_ao_vivo": feeds,
    }

    OUT.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Relatorio salvo em {OUT}")
    print("DC Realtime ts:", relatorio["arcturus_defesa_civil_rt"]["timestamp_coleta"],
          "| Pior caso:", relatorio["arcturus_defesa_civil_rt"]["pior_caso_bacia"])
    for f in feeds:
        print(f" - {f['fonte']}: http={f.get('status_http')} | itens_filtrados={len(f.get('itens', []))}")
        for it in f.get("itens", [])[:3]:
            print(f"     * ({it.get('idade_horas')}h) {it.get('titulo')[:90]}")


if __name__ == "__main__":
    main()
