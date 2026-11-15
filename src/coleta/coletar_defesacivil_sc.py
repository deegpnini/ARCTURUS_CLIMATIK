#!/usr/bin/env python3
"""
ARCTURUS_CLIMATIK — Coletor Oficial em Tempo Real (Defesa Civil SC via ARIA DOM)
Extrai chuva acumulada (1h, 6h, 12h, 24h, 48h, 72h, 168h) e cota do rio (m)
das estações da bacia do Rio Tubarão e região Sul de SC, gravando snapshot
atual e histórico contínuo (JSONL) para calibração futura do modelo v11c.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

OUT_SNAPSHOT = DATA_DIR / "chuva_defesacivil_realtime.json"
OUT_HISTORICO = DATA_DIR / "historico_defesacivil_bacia.jsonl"

# Códigos exatos das estações da Bacia do Rio Tubarão e Sul de SC
ESTACOES_ALVO = {
    "DCSC-00054": "Lauro Müller (Cabeceira)",
    "DCSC-00046": "Orleans (Cabeceira)",
    "DCSC-00122": "São Ludgero (Médio Curso)",
    "DCSC-00151": "Grão-Pará (Cabeceira/Afluente)",
    "DCSC-00048": "Tubarão - Guarda (Baixo Curso)",
    "DCSC-00075": "Urussanga (Sul/Referência)",
}

TERMOS_PESQUISA = ["Orleans", "São Ludgero", "Lauro", "Grão", "Tubarao", "Urussanga"]


def parse_float_br(val: str):
    val = val.strip().replace(",", ".")
    if not val or val == "-":
        return None
    try:
        return float(val)
    except ValueError:
        return None


async def coletar_defesa_civil() -> dict:
    encontradas = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        await page.goto(
            "https://monitoramento.defesacivil.sc.gov.br/mapa",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await asyncio.sleep(4)
        await page.get_by_text("Tabela", exact=True).click()
        await asyncio.sleep(2)

        caixa = page.get_by_role("textbox").first

        for termo in TERMOS_PESQUISA:
            await caixa.fill("")
            await caixa.fill(termo)
            await asyncio.sleep(1.0)

            linhas = page.get_by_role("row")
            qtd = await linhas.count()

            for i in range(qtd):
                celulas = await linhas.nth(i).get_by_role("gridcell").all_inner_texts()
                cols = [c.strip() for c in celulas]
                if len(cols) >= 11 and cols[0] in ESTACOES_ALVO:
                    cod = cols[0]
                    encontradas[cod] = {
                        "codigo": cod,
                        "trecho_bacia": ESTACOES_ALVO[cod],
                        "nome_oficial": cols[1],
                        "atualizacao_estacao": cols[2],
                        "chuva_1h_mm": parse_float_br(cols[3]),
                        "chuva_6h_mm": parse_float_br(cols[4]),
                        "chuva_12h_mm": parse_float_br(cols[5]),
                        "chuva_24h_mm": parse_float_br(cols[6]),
                        "chuva_48h_mm": parse_float_br(cols[7]),
                        "chuva_72h_mm": parse_float_br(cols[8]),
                        "chuva_168h_mm": parse_float_br(cols[9]),
                        "rio_m": parse_float_br(cols[10]),
                    }

        await browser.close()

    lista = list(encontradas.values())
    chuvas_1h = [e["chuva_1h_mm"] for e in lista if e["chuva_1h_mm"] is not None]
    chuvas_6h = [e["chuva_6h_mm"] for e in lista if e["chuva_6h_mm"] is not None]
    chuvas_24h = [e["chuva_24h_mm"] for e in lista if e["chuva_24h_mm"] is not None]

    payload = {
        "timestamp_coleta": datetime.now().isoformat(timespec="seconds"),
        "fonte": "Defesa Civil SC (ARIA gridcell)",
        "total_estacoes": len(lista),
        "pior_caso_bacia": {
            "max_chuva_1h_mm": max(chuvas_1h) if chuvas_1h else None,
            "max_chuva_6h_mm": max(chuvas_6h) if chuvas_6h else None,
            "max_chuva_24h_mm": max(chuvas_24h) if chuvas_24h else None,
        },
        "estacoes": lista,
    }
    return payload


def main():
    try:
        payload = asyncio.run(coletar_defesa_civil())
        if payload["total_estacoes"] == 0:
            print("[AVISO] Defesa Civil SC retornou 0 estações da bacia. Mantendo snapshot anterior.")
            return

        OUT_SNAPSHOT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        with open(OUT_HISTORICO, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

        pior = payload["pior_caso_bacia"]
        print(
            f"[OK] Defesa Civil SC: {payload['total_estacoes']} estações | "
            f"Pior caso bacia -> 1h={pior['max_chuva_1h_mm']}mm | "
            f"6h={pior['max_chuva_6h_mm']}mm | 24h={pior['max_chuva_24h_mm']}mm"
        )
        for e in payload["estacoes"]:
            print(
                f"     - {e['trecho_bacia']} [{e['codigo']}]: "
                f"1h={e['chuva_1h_mm']}mm | 6h={e['chuva_6h_mm']}mm | Rio={e['rio_m']}m"
            )
    except Exception as exc:
        print(f"[ERRO] Falha na coleta Defesa Civil SC (fallback Open-Meteo segue ativo): {exc}")


if __name__ == "__main__":
    main()
