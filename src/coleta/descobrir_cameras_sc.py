#!/usr/bin/env python3
"""
descobrir_cameras_sc.py — Varredura estadual profunda de câmeras públicas ao vivo (24h)
em todas as macrorregiões de Santa Catarina para o ARCTURUS CLIMATIK.
"""
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

JSON_PATH = Path("data/cameras_publicas.json")
LOG_PATH = Path("logs/cameras_publicas.log")

# Coordenadas de referência por município de SC (lat, lon, regiao_arcturus, prioridade)
MUNICIPIOS_SC = {
    # Prioridade 1: Bacia do Rio Tubarão
    "Tubarão": (-28.4713, -49.0144, "BACIA_TUBARAO", 1),
    "Laguna": (-28.4825, -48.7808, "BACIA_TUBARAO", 1),
    "Lauro Müller": (-28.3958, -49.5469, "BACIA_TUBARAO", 1),
    "Orleans": (-28.3586, -49.2914, "BACIA_TUBARAO", 1),
    "Braço do Norte": (-28.2753, -49.1647, "BACIA_TUBARAO", 1),
    "São Ludgero": (-28.3258, -49.1767, "BACIA_TUBARAO", 1),
    "Gravatal": (-28.3283, -49.0353, "BACIA_TUBARAO", 1),
    "Capivari de Baixo": (-28.4447, -48.9578, "BACIA_TUBARAO", 1),
    "Armazém": (-28.2619, -49.0175, "BACIA_TUBARAO", 1),
    "Grão-Pará": (-28.1850, -49.2150, "BACIA_TUBARAO", 1),
    "Jaguaruna": (-28.6150, -49.0256, "BACIA_TUBARAO", 1),
    # Prioridade 2: Sul SC e Serra Catarinense
    "Criciúma": (-28.6775, -49.3697, "SUL_SC", 2),
    "Içara": (-28.7133, -49.3003, "SUL_SC", 2),
    "Araranguá": (-28.9356, -49.4858, "SUL_SC", 2),
    "Balneário Rincão": (-28.8339, -49.2361, "SUL_SC", 2),
    "Balneário Arroio do Silva": (-28.9839, -49.4128, "SUL_SC", 2),
    "Sombrio": (-29.1128, -49.6289, "SUL_SC", 2),
    "Passo de Torres": (-29.3236, -49.7261, "SUL_SC", 2),
    "Urussanga": (-28.5186, -49.3208, "SUL_SC", 2),
    "Nova Veneza": (-28.6369, -49.4981, "SUL_SC", 2),
    "São Joaquim": (-28.2939, -49.9317, "SERRA_SC", 2),
    "Urubici": (-28.0156, -49.5925, "SERRA_SC", 2),
    "Bom Jardim da Serra": (-28.3369, -49.6247, "SERRA_SC", 2),
    "Lages": (-27.8161, -50.3261, "SERRA_SC", 2),
    "Urupema": (-27.9528, -49.8736, "SERRA_SC", 2),
    "Alfredo Wagner": (-27.7003, -49.3336, "SERRA_SC", 2),
    # Prioridade 3: Litoral SC
    "Garopaba": (-28.0233, -48.6192, "LITORAL_SC", 3),
    "Imbituba": (-28.2400, -48.6703, "LITORAL_SC", 3),
    "Palhoça": (-27.6453, -48.6678, "LITORAL_SC", 3),
    "São José": (-27.6147, -48.6278, "LITORAL_SC", 3),
    "Florianópolis": (-27.5935, -48.5656, "LITORAL_SC", 3),
    "Biguaçu": (-27.4942, -48.6556, "LITORAL_SC", 3),
    "Governador Celso Ramos": (-27.3147, -48.5586, "LITORAL_SC", 3),
    "Tijucas": (-27.2414, -48.6336, "LITORAL_SC", 3),
    "Porto Belo": (-27.1578, -48.5531, "LITORAL_SC", 3),
    "Bombinhas": (-27.1378, -48.4814, "LITORAL_SC", 3),
    "Itapema": (-27.0903, -48.6114, "LITORAL_SC", 3),
    "Balneário Camboriú": (-26.9926, -48.6305, "LITORAL_SC", 3),
    "Itajaí": (-26.9078, -48.6619, "LITORAL_SC", 3),
    "Navegantes": (-26.8986, -48.6542, "LITORAL_SC", 3),
    "Penha": (-26.7694, -48.6458, "LITORAL_SC", 3),
    "Balneário Piçarras": (-26.7647, -48.6717, "LITORAL_SC", 3),
    "Barra Velha": (-26.6322, -48.6847, "LITORAL_SC", 3),
    "São Francisco do Sul": (-26.2433, -48.6381, "LITORAL_SC", 3),
    "Itapoá": (-26.1169, -48.6161, "LITORAL_SC", 3),
    # Prioridade 4: Vale do Itajaí, Norte e Oeste SC
    "Blumenau": (-26.9189, -49.0658, "VALE_ITAJAI_NORTE", 4),
    "Brusque": (-27.0978, -48.9175, "VALE_ITAJAI_NORTE", 4),
    "Gaspar": (-26.9314, -48.9586, "VALE_ITAJAI_NORTE", 4),
    "Indaial": (-26.8978, -49.2317, "VALE_ITAJAI_NORTE", 4),
    "Timbó": (-26.8236, -49.2714, "VALE_ITAJAI_NORTE", 4),
    "Pomerode": (-26.7406, -49.1769, "VALE_ITAJAI_NORTE", 4),
    "Rio do Sul": (-27.2142, -49.6431, "VALE_ITAJAI_NORTE", 4),
    "Joinville": (-26.3044, -48.8487, "VALE_ITAJAI_NORTE", 4),
    "Jaraguá do Sul": (-26.4853, -49.0669, "VALE_ITAJAI_NORTE", 4),
    "São Bento do Sul": (-26.2494, -49.3831, "VALE_ITAJAI_NORTE", 4),
    "Chapecó": (-27.1004, -52.6152, "OESTE_SC", 4),
    "Concórdia": (-27.2336, -52.0278, "OESTE_SC", 4),
    "Joaçaba": (-27.1764, -51.5047, "OESTE_SC", 4),
    "Xanxerê": (-26.8769, -52.4042, "OESTE_SC", 4),
    "São Miguel do Oeste": (-26.7253, -53.5181, "OESTE_SC", 4),
    "Caçador": (-26.7753, -51.0150, "OESTE_SC", 4),
    "Videira": (-27.0083, -51.1517, "OESTE_SC", 4),
}

# Apelidos, praias, serras e pontos turísticos de SC mapeados para seus municípios
ALIASES_LOCAIS = {
    "serra do rio do rastro": "Lauro Müller",
    "morro da igreja": "Urubici",
    "serra do corvo branco": "Urubici",
    "praia do rosa": "Imbituba",
    "ibiraquera": "Imbituba",
    "ferrugem": "Garopaba",
    "silveira": "Garopaba",
    "guarda do embaú": "Palhoça",
    "pinheira": "Palhoça",
    "joaquina": "Florianópolis",
    "praia mole": "Florianópolis",
    "jurerê": "Florianópolis",
    "jurere": "Florianópolis",
    "canasvieiras": "Florianópolis",
    "santinho": "Florianópolis",
    "hercilio luz": "Florianópolis",
    "hercílio luz": "Florianópolis",
    "beira-mar norte": "Florianópolis",
    "campeche": "Florianópolis",
    "barra da lagoa": "Florianópolis",
    "ingleses": "Florianópolis",
    "meia praia": "Itapema",
    "quatro ilhas": "Bombinhas",
    "mariscal": "Bombinhas",
    "sepultura": "Bombinhas",
    "caixa d'aço": "Porto Belo",
    "praia brava": "Itajaí",
    "cabeçudas": "Itajaí",
    "beto carrero": "Penha",
    "armação": "Penha",
    "enseada": "São Francisco do Sul",
    "prainha": "São Francisco do Sul",
    "serra dona francisca": "Joinville",
    "arroio do silva": "Balneário Arroio do Silva",
    "rincão": "Balneário Rincão",
    "camacho": "Jaguaruna",
}

# Termos para descartar eventos esportivos/jogos que não são câmeras meteorológicas/urbanas
PALAVRAS_BLOQUEIO = [
    "futsal", "futebol", "campeonato", "jogo ao vivo", "ginásio", "ginasio",
    "culto", "missa", "sessão ordinária", "sessao ordinaria", "câmara municipal",
    "camara municipal", "podcast", "rádio", "radio", "notícias", "jornal",
]

QUERIES_VARREDURA_PROFUNDA = [
    # Agregadores estaduais conhecidos
    "Vejaomar ao vivo SC",
    "Maaxcam ao vivo Florianópolis",
    "Clima Ao Vivo Santa Catarina",
    "ConexãoDCTV ao vivo SC",
    "BNU.tv ao vivo",
    "Se-Connect ao vivo SC",
    # Litoral Sul e Grande Florianópolis
    "camera ao vivo Garopaba Praia do Rosa Imbituba",
    "camera ao vivo Guarda do Embaú Palhoça São José",
    "camera ao vivo Florianópolis Joaquina Jurerê Canasvieiras",
    "camera ao vivo Florianópolis Ponte Hercílio Luz Beira Mar",
    "camera ao vivo Governador Celso Ramos Tijucas",
    # Costa Esmeralda e Litoral Norte
    "camera ao vivo Itapema Meia Praia ao vivo",
    "camera ao vivo Bombinhas Porto Belo ao vivo",
    "camera ao vivo Balneário Camboriú ao vivo 24h",
    "camera ao vivo Itajaí Navegantes ao vivo",
    "camera ao vivo Penha Piçarras Barra Velha ao vivo",
    "camera ao vivo São Francisco do Sul Itapoá ao vivo",
    # Serra Catarinense e Sul SC
    "camera ao vivo Urubici Morro da Igreja Serra SC",
    "camera ao vivo Bom Jardim da Serra São Joaquim Lages Urupema",
    "camera ao vivo Criciúma Içara Araranguá Sombrio Passo de Torres",
    "camera ao vivo Tubarão Laguna Lauro Müller Orleans Braço do Norte",
    # Vale do Itajaí, Norte e Oeste SC
    "camera ao vivo Blumenau Gaspar Indaial Pomerode Timbó",
    "camera ao vivo Brusque Rio do Sul Itajaí-Açu",
    "camera ao vivo Joinville Jaraguá do Sul São Bento do Sul",
    "camera ao vivo Chapecó Concórdia Joaçaba Xanxerê",
    "camera ao vivo São Miguel do Oeste Caçador Videira",
    # Buscas amplas em inglês/português
    "live cam Santa Catarina Brazil 24h",
    "surf cam Santa Catarina ao vivo",
]


def log_msg(msg: str):
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    linha = f"[{ts}] {msg}"
    print(linha)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(linha + "\n")


def detectar_municipio(texto: str):
    t_low = texto.lower()
    if any(bad in t_low for bad in PALAVRAS_BLOQUEIO):
        return None, None

    # 1. Busca direta por nome oficial de município
    for mun, info in MUNICIPIOS_SC.items():
        if mun.lower() in t_low:
            return mun, info

    # 2. Busca por praias, serras e pontos conhecidos
    for alias, mun in ALIASES_LOCAIS.items():
        if alias in t_low and mun in MUNICIPIOS_SC:
            return mun, MUNICIPIOS_SC[mun]

    return None, None


def inferir_tipo(texto: str) -> str:
    t = texto.lower()
    if any(k in t for k in ["rio", "balsa", "ponte", "barragem", "lagoa", "canal"]):
        return "rio"
    if any(k in t for k in ["praia", "orla", "mar", "surf", "barra", "costa", "ilha"]):
        return "praia"
    if any(k in t for k in ["br101", "br-101", "rodovia", "transito", "trânsito", "viaduto", "serra", "sc-"]):
        return "transito"
    if any(k in t for k in ["clima", "tempo", "neve", "geada", "neblina", "morro"]):
        return "clima"
    return "cidade"


def buscar_lives_ytdlp(query: str, max_itens: int = 20):
    cmd = [
        ".venv/bin/yt-dlp",
        "--dump-json",
        "--no-warnings",
        "--ignore-errors",
        "--match-filter",
        "is_live",
        f"ytsearch{max_itens}:{query}",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        itens = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                itens.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return itens
    except Exception as e:
        log_msg(f"[WARN] Falha ao buscar query '{query}': {e}")
        return []


def main():
    cameras = json.loads(JSON_PATH.read_text(encoding="utf-8")) if JSON_PATH.exists() else []
    urls_existentes = {c.get("url_youtube", "").strip() for c in cameras}

    max_num = 26
    for c in cameras:
        m = re.match(r"cam_(\d+)", c.get("id", ""))
        if m:
            max_num = max(max_num, int(m.group(1)))

    novas = 0
    log_msg(f"[DEEP_STATEWIDE_SCAN_START] Varrendo {len(QUERIES_VARREDURA_PROFUNDA)} frentes em Santa Catarina...")

    for idx, q in enumerate(QUERIES_VARREDURA_PROFUNDA, start=1):
        print(f"🔎 [{idx}/{len(QUERIES_VARREDURA_PROFUNDA)}] Buscando: {q}")
        resultados = buscar_lives_ytdlp(q, max_itens=20)
        for item in resultados:
            vid = item.get("id")
            if not vid:
                continue
            url = f"https://www.youtube.com/watch?v={vid}"
            if url in urls_existentes:
                continue

            titulo = item.get("title", "")
            canal = item.get("uploader") or item.get("channel") or "YouTube Live"
            desc = (item.get("description") or "")[:350]
            texto_busca = f"{titulo} {canal} {desc}"

            mun, info = detectar_municipio(texto_busca)
            if not mun:
                continue

            lat, lon, regiao, prio = info
            offset_lat = ((novas % 9) - 4) * 0.0020
            offset_lon = (((novas * 3) % 9) - 4) * 0.0020
            max_num += 1
            cid = f"cam_{max_num:03d}"

            novo_reg = {
                "id": cid,
                "fonte": "youtube",
                "canal": canal,
                "titulo_stream": titulo,
                "url_youtube": url,
                "municipio": mun,
                "regiao_arcturus": regiao,
                "tipo": inferir_tipo(texto_busca),
                "status": "ATIVA",
                "validado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
                "prioridade": prio,
                "lat": round(lat + offset_lat, 4),
                "lon": round(lon + offset_lon, 4),
                "notas": f"Stream público ao vivo 24h em {mun} ({canal}).",
            }
            cameras.append(novo_reg)
            urls_existentes.add(url)
            novas += 1
            log_msg(f"[NEW_CAMERA] {cid} | {regiao} | P{prio} | {mun} ({canal}) -> {url}")

    JSON_PATH.write_text(json.dumps(cameras, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ativas = [c for c in cameras if c.get("status") == "ATIVA"]
    por_regiao = {}
    for c in ativas:
        r = c.get("regiao_arcturus", "OUTRA")
        por_regiao[r] = por_regiao.get(r, 0) + 1
    log_msg(f"[DEEP_STATEWIDE_SCAN_COMPLETE] +{novas} novas câmeras | Total ATIVAS: {len(ativas)} | Distribuição: {por_regiao}")


if __name__ == "__main__":
    main()
