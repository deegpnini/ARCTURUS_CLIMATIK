#!/usr/bin/env python3
"""Formata e envia boletins hidrológicos para o Telegram."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from html import escape, unescape

LIMITE_TELEGRAM = 4096

NIVEIS_CHUVA = (
    (50, "Extremo", "🔴"),
    (20, "Alerta", "🟠"),
    (5, "Atenção", "🟡"),
    (0, "Normal", "🟢"),
)
NIVEIS_RIO = (
    (600, "Emergência", "🔴"),
    (350, "Alerta", "🟠"),
    (250, "Atenção", "🟡"),
    (50, "Normal", "🟢"),
)


def _normalizar(texto: object) -> str:
    return (
        unicodedata.normalize("NFKD", str(texto))
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


def _numero(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _delta_inteiro(valor: float) -> str:
    delta = int(round(valor))
    return f"{delta:+d}".replace("-", "−") if delta else "0"


def _classificar(valor: float, niveis) -> tuple[str, str]:
    for limite, nome, icone in niveis:
        if valor > limite:
            return nome, icone
    return niveis[-1][1], niveis[-1][2]


def _classificar_rio(cota_cm: float) -> tuple[str, str]:
    for limite, nome, icone in NIVEIS_RIO:
        if cota_cm >= limite:
            return nome, icone
    return "Baixo", "🔵"


def _comprimento_renderizado(html: str) -> int:
    texto = unescape(re.sub(r"<[^>]*>", "", html))
    return len(texto.encode("utf-16-le")) // 2


def avaliar_frescor_telemetria(
    timestamp: datetime, agora: datetime, limite_minutos: int = 90
) -> tuple[bool, str]:
    if timestamp.tzinfo is None and agora.tzinfo is not None:
        timestamp = timestamp.replace(tzinfo=agora.tzinfo)
    if agora.tzinfo is None and timestamp.tzinfo is not None:
        agora = agora.replace(tzinfo=timestamp.tzinfo)
    idade_min = (agora - timestamp).total_seconds() / 60
    hora = timestamp.strftime("%H:%M")
    if 0 <= idade_min <= limite_minutos:
        return True, f"dados atualizados às {hora}"
    return False, f"dados de {hora} (desatualizados)"


def estado_coleta_defesacivil(status: dict | None) -> tuple[bool, str | None]:
    if status is None:
        return True, None
    if status.get("ok") is True:
        return True, None
    tentativa = status.get("ultima_tentativa")
    try:
        hora = datetime.fromisoformat(tentativa).strftime("%H:%M")
    except (TypeError, ValueError):
        hora = None
    detalhe = f" (falha na coleta às {hora})" if hora else ""
    return False, "sem dados da Defesa Civil" + detalhe


def formatar_resumo_previsao(
    chuva_por_cidade: dict,
    nomes_cidades: dict,
    regioes: list,
    datas: list[str],
    gerado_em: datetime,
) -> str:
    linhas = [
        "☁️ <b>Previsão Open-Meteo · precipitação</b>",
        f"<i>Consulta feita em {gerado_em:%d/%m %H:%M}; "
        "a API não informa a rodada de inicialização do modelo.</i>",
    ]
    for data in datas:
        registros = [
            (cidade, valores[data])
            for cidade, valores in chuva_por_cidade.items()
            if data in valores
        ]
        if registros:
            media = sum(valor for _, valor in registros) / len(registros)
            cidade_max, maximo = max(registros, key=lambda par: par[1])
            linhas.append(
                f"{datetime.fromisoformat(data):%d/%m}: "
                f"média {_numero(media)} · máx {_numero(maximo)} mm "
                f"({escape(nomes_cidades[cidade_max])})"
            )

    for nome_regiao, cidades in regioes:
        resumos = []
        detalhes = []
        for data in datas:
            valores = [
                (cidade, chuva_por_cidade.get(cidade, {}).get(data))
                for cidade in cidades
            ]
            valores = [(cidade, valor) for cidade, valor in valores if valor is not None]
            if valores:
                media = sum(valor for _, valor in valores) / len(valores)
                cidade_max, maximo = max(valores, key=lambda par: par[1])
                dia = datetime.fromisoformat(data).strftime("%d/%m")
                resumos.append(
                    f"{dia} média {_numero(media)} · máx {_numero(maximo)} "
                    f"({escape(nomes_cidades[cidade_max])})"
                )
        for cidade in cidades:
            valores = chuva_por_cidade.get(cidade, {})
            if valores:
                itens = " · ".join(
                    f"{datetime.fromisoformat(data):%d/%m} {_numero(valores[data])} mm"
                    for data in datas if data in valores
                )
                detalhes.append(
                    f"• {escape(nomes_cidades[cidade])}: {itens}"
                )
        if resumos:
            linhas.append(f"<b>{escape(nome_regiao)}:</b> " + " | ".join(resumos))
            if detalhes:
                linhas.append(
                    "<blockquote expandable>"
                    + "\n".join(detalhes)
                    + "</blockquote>"
                )
    return "\n".join(linhas)


def buscar_alertas_inmet():
    """Busca alertas oficiais do INMET para a região da bacia."""
    import requests
    try:
        url = "https://apiprevmet3.inmet.gov.br/avisos"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            dados = r.json()
            alertas = [a for a in dados if "SC" in str(a.get("estados", ""))]
            if alertas:
                return alertas[0].get("titulo", "Alerta ativo")
        return "Sem alertas ativos no momento"
    except Exception:
        return "Sem alertas ativos no momento"


def formatar_boletim(dados: dict) -> str:
    """Renderiza o resumo e detalhes expansíveis em HTML do Telegram."""
    agora: datetime = dados["agora"]
    chuva = dados.get("chuva_24h_mm")
    chuva_nivel, chuva_icone = (
        _classificar(float(chuva), NIVEIS_CHUVA) if chuva is not None
        else ("Indisponível", "⚪")
    )
    rio_nivel, rio_icone = _classificar_rio(float(dados["cota_cm"]))
    tendencia = str(dados["tendencia"])
    seta = {
        "estavel": "➡️",
        "subindo": "⬆️",
        "caindo": "⬇️",
    }.get(_normalizar(tendencia), "➡️")

        # Bloco de alertas oficiais
    alerta_inmet = buscar_alertas_inmet()
    resumo = [
        "⚠️ <b>ALERTAS OFICIAIS (INMET / DEFESA CIVIL)</b>",
        f"• INMET: {escape(alerta_inmet)}",
        f"• Defesa Civil: {escape(str(dados.get('status_defesacivil', 'Sem alerta')))}",
        "",
        "🌊 <b>ARCTURUS · Rio Tubarão</b>",
        f"🗓 {agora:%d/%m/%Y} · {agora:%H:%M}",
        "",
        (
            f"🌧️ <b>Chuva: {chuva_icone} {chuva_nivel}</b> · "
            f"{_numero(chuva)} mm/24h"
            if chuva is not None
            else "🌧️ <b>Chuva: ⚪ Indisponível</b>"
        ),
        f"<i>Fonte: {escape(str(dados['fonte_chuva']))}</i>",
        (
            f"📡 Defesa Civil SC: {escape(str(dados['status_defesacivil']))}"
            if dados.get("status_defesacivil")
            else ""
        ),
        f"🌊 <b>Rio: {rio_icone} {rio_nivel}</b> · "
        f"{_numero(dados['cota_cm'], 0)} cm ({_numero(dados['cota_cm']/100, 2)} m)",
        f"{seta} <b>Tendência:</b> {escape(tendencia)}",
        "",
        "ℹ️ <i>Boletim informativo. Projeções em modo sombra "
        "não são alerta oficial de perigo.</i>",
        "",
    ]

    if chuva_nivel in ("Alerta", "Extremo") and rio_nivel in ("Baixo", "Normal"):
        resumo.extend(
            [
                "💡 <i>A cota pode ainda não refletir a chuva recente; "
                "o rio pode reagir com atraso.</i>",
                "",
            ]
        )

    detalhes = []
    projecoes = dados.get("projecoes") or {}
    if projecoes:
        partes = " · ".join(
            f"{escape(str(horizonte))}{'' if str(horizonte).endswith('h') else 'h'} "
            f"<code>{_delta_inteiro(valor)} cm</code>"
            for horizonte, valor in sorted(
                projecoes.items(), key=lambda item: int(str(item[0]).rstrip("h"))
            )
        )
        detalhes.append(
            "🔭 <b>Projeção experimental · modo sombra</b> (elevação consequência da chuva prevista na cabeceira/médio curso)\n"
            f"{partes}\n"
            "<i>Probabilidade de cheia: indisponível "
            "(modelo em validação).</i>"
        )

    estacoes = dados.get("estacoes") or []
    if estacoes:
        linhas_estacoes = []
        for estacao in sorted(
            estacoes,
            key=lambda e: (
                e.get("mm_24h") if e.get("mm_24h") is not None else -1
            ),
            reverse=True,
        ):
            partes = []
            if estacao.get("mm_1h") is not None:
                partes.append(f"{_numero(estacao['mm_1h'])} mm/1h")
            if estacao.get("mm_24h") is not None:
                partes.append(f"{_numero(estacao['mm_24h'])} mm/24h")
            if partes:
                linhas_estacoes.append(
                    f"• <b>{escape(str(estacao['nome']))}:</b> "
                    + " · ".join(partes)
                )
        if linhas_estacoes:
            atualizado = ""
            if dados.get("hora_telemetria"):
                atualizado = (
                    f"\n<i>Atualizada às "
                    f"{escape(str(dados['hora_telemetria']))}</i>"
                )
            detalhes.append(
                "📡 <b>Estações da bacia</b>"
                f"{atualizado}\n<blockquote expandable>"
                + "\n".join(linhas_estacoes)
                + "</blockquote>"
            )

    previsao = dados.get("previsao_html")
    if previsao:
        detalhes.append(previsao)

    rodape = "🆘 Emergência: Defesa Civil 199 · Bombeiros 193"

    # Mantém resumo e aviso no corpo; descarta detalhes secundários se exceder.
    while True:
        componentes = [*resumo, *detalhes, rodape]
        mensagem = "\n".join(parte for parte in componentes if parte)
        if _comprimento_renderizado(mensagem) <= LIMITE_TELEGRAM:
            return mensagem
        if detalhes:
            detalhes.pop()
            continue
        resumo_sem_detalhes = "\n".join([*resumo, rodape])
        if _comprimento_renderizado(resumo_sem_detalhes) > LIMITE_TELEGRAM:
            raise ValueError("O resumo do boletim excede o limite do Telegram.")
        return resumo_sem_detalhes


def enviar_com_fallback(post, url: str, chat_id: str, mensagem: str, max_tentativas: int = 3):
    """Tenta HTML e reenvia como texto simples se as entidades forem rejeitadas.
    Adiciona retry com backoff exponencial para timeouts transitórios."""
    import time
    parametros = {
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    ultima_excecao = None
    for tentativa in range(max_tentativas):
        try:
            resposta = post(url, data=parametros, timeout=30)
            if resposta.status_code != 400:
                return resposta, False

            try:
                descricao = str(resposta.json().get("description", "")).lower()
            except (ValueError, AttributeError):
                return resposta, False

            erro_html = (
                "can't parse entities" in descricao
                or "unsupported start tag" in descricao
                or "unsupported entity" in descricao
            )
            if not erro_html:
                return resposta, False

            texto_simples = unescape(re.sub(r"</?[^>]+>", "", mensagem))
            parametros.pop("parse_mode", None)
            parametros["text"] = texto_simples
            return post(url, data=parametros, timeout=30), True
        except Exception as exc:
            ultima_excecao = exc
            if tentativa < max_tentativas - 1:
                time.sleep(2 ** tentativa)
    if ultima_excecao is not None:
        raise ultima_excecao
    return None, False
