from datetime import datetime
from html.parser import HTMLParser

from telegram_formatador import (
    LIMITE_TELEGRAM,
    _comprimento_renderizado,
    avaliar_frescor_telemetria,
    estado_coleta_defesacivil,
    enviar_com_fallback,
    formatar_boletim,
    formatar_resumo_previsao,
)


class TelegramHTMLValidator(HTMLParser):
    allowed_tags = {"b", "i", "code", "blockquote"}

    def __init__(self):
        super().__init__()
        self.stack = []

    def handle_starttag(self, tag, attrs):
        assert tag in self.allowed_tags
        if tag == "blockquote":
            assert ("expandable", None) in attrs
        if tag != "blockquote":
            self.stack.append(tag)

    def handle_endtag(self, tag):
        assert tag in self.allowed_tags
        if tag != "blockquote":
            assert self.stack.pop() == tag


def _base_dados(**overrides):
    dados = {
        "agora": datetime(2026, 11, 15, 16, 17),
        "chuva_24h_mm": 57.6,
        "fonte_chuva": "Defesa Civil SC",
        "cota_cm": 69,
        "tendencia": "estável",
        "projecoes": {"1h": -0.49, "3h": 2.82, "6h": 4.43},
        "probabilidade_pct": 0.43,
        "estacoes": [
            {"nome": "São Ludgero", "mm_1h": 14, "mm_24h": 57.6, "rio_m": 40.39},
        ],
        "previsao_html": (
            "☁️ <b>Previsão</b>\n"
            "<b>🏔️ Cabeceira</b>\n"
            "<blockquote expandable>Lauro Müller · 15/11 · 16–25°C</blockquote>"
        ),
    }
    dados.update(overrides)
    return dados


def test_separa_niveis_de_chuva_e_rio_e_usa_faixas_do_dashboard():
    mensagem = formatar_boletim(_base_dados())

    assert "🌧️ <b>Chuva: 🔴 Extremo</b>" in mensagem
    assert "🌊 <b>Rio: 🟢 Normal</b> · 69 cm" in mensagem
    assert "🔭 <b>Projeção experimental · modo sombra</b>" in mensagem
    assert "Probabilidade de cheia: indisponível" in mensagem
    assert "0,43%" not in mensagem
    assert "−0 cm" not in mensagem
    assert "<code>0 cm</code>" in mensagem
    assert "<code>+3 cm</code>" in mensagem
    assert "não são alerta oficial de perigo" in mensagem
    assert "<blockquote expandable>" in mensagem
    TelegramHTMLValidator().feed(mensagem)
    assert not TelegramHTMLValidator().stack


def test_classificacao_do_rio_segue_limites_do_dashboard():
    esperados = [
        (49, "🔵 Baixo"),
        (50, "🟢 Normal"),
        (249, "🟢 Normal"),
        (250, "🟡 Atenção"),
        (350, "🟠 Alerta"),
        (600, "🔴 Emergência"),
    ]
    for cota, esperado in esperados:
        mensagem = formatar_boletim(_base_dados(cota_cm=cota, chuva_24h_mm=0))
        assert f"🌊 <b>Rio: {esperado}</b>" in mensagem


def test_pior_caso_corta_detalhes_e_preserva_resumo_abaixo_do_limite():
    estacoes = [
        {
            "nome": f"Estação de monitoramento extensa {i} & <subestação>",
            "mm_1h": 100.0,
            "mm_24h": 1000.0,
            "rio_m": 12.34,
        }
        for i in range(120)
    ]
    previsao = (
        "☁️ <b>Previsão por todas as regiões</b>\n"
        + "\n".join(
            "<b>Região</b><blockquote expandable>"
            + ("Cidade &lt;teste&gt; · 15/11 · 20–30°C · chuva 50 mm\n" * 100)
            + "</blockquote>"
            for _ in range(3)
        )
    )

    mensagem = formatar_boletim(
        _base_dados(estacoes=estacoes, previsao_html=previsao)
    )

    assert _comprimento_renderizado(mensagem) <= LIMITE_TELEGRAM
    assert "🌧️ <b>Chuva:" in mensagem
    assert "🌊 <b>Rio:" in mensagem
    assert "Tendência:" in mensagem
    assert "não são alerta oficial de perigo" in mensagem
    assert "🔭 <b>Projeção experimental" in mensagem
    assert "Estação de monitoramento extensa" not in mensagem
    assert "Previsão por todas as regiões" not in mensagem
    TelegramHTMLValidator().feed(mensagem)


def test_escapa_valores_dinamicos_com_ampersand_e_menor_que():
    mensagem = formatar_boletim(
        _base_dados(
            fonte_chuva="Defesa & Civil <SC>",
            estacoes=[
                {"nome": "Estação A & <B>", "mm_1h": 1, "mm_24h": 2},
            ],
        )
    )

    assert "Defesa &amp; Civil &lt;SC&gt;" in mensagem
    assert "Estação A &amp; &lt;B&gt;" in mensagem
    TelegramHTMLValidator().feed(mensagem)


def test_telemetria_antiga_fica_explicita_e_nao_classifica_chuva():
    agora = datetime(2026, 11, 15, 16, 0)
    atual, status = avaliar_frescor_telemetria(
        datetime(2026, 11, 15, 14, 29), agora
    )
    assert not atual
    assert status == "dados de 14:29 (desatualizados)"

    mensagem = formatar_boletim(
        _base_dados(
            chuva_24h_mm=None,
            fonte_chuva="Defesa Civil SC",
            status_defesacivil=status,
            estacoes=[],
        )
    )
    assert "Chuva: ⚪ Indisponível" in mensagem
    assert "dados de 14:29 (desatualizados)" in mensagem
    assert "Chuva: 🔴 Extremo" not in mensagem


def test_falha_da_ultima_coleta_nao_reutiliza_snapshot_anterior():
    coleta_ok, status = estado_coleta_defesacivil(
        {"ok": False, "ultima_tentativa": "2026-11-15T16:20:00-03:00"}
    )

    assert not coleta_ok
    assert status == "sem dados da Defesa Civil (falha na coleta às 16:20)"


def test_resumo_diario_usa_media_maximo_e_datas_dos_registros():
    nomes = {
        "lauro_muller": "Lauro Müller",
        "orleans": "Orleans",
        "sao_bonifacio": "São Bonifácio",
    }
    regioes = [("🏔️ Cabeceira", list(nomes))]
    chuva = {
        "lauro_muller": {"2026-11-16": 0.1, "2026-11-17": 14.2},
        "orleans": {"2026-11-16": 1.1, "2026-11-17": 8.2},
        "sao_bonifacio": {"2026-11-16": 0.6, "2026-11-17": 11.2},
    }

    texto = formatar_resumo_previsao(
        chuva,
        nomes,
        regioes,
        ["2026-11-16", "2026-11-17"],
        datetime(2026, 11, 15, 6, 0),
    )

    assert "16/11: média 0,6 · máx 1,1 mm (Orleans)" in texto
    assert "17/11: média 11,2 · máx 14,2 mm (Lauro Müller)" in texto
    assert "Consulta feita em 15/11 06:00" in texto
    assert "não informa a rodada" in texto
    assert "234,4" not in texto
    assert texto.count("<blockquote expandable>") == 1
    TelegramHTMLValidator().feed(texto)


def test_reenvia_sem_formatacao_se_telegram_rejeitar_entidades():
    class Response:
        def __init__(self, status_code, description=""):
            self.status_code = status_code
            self._description = description
            self.text = description

        def json(self):
            return {"description": self._description}

    calls = []

    def fake_post(url, data, timeout):
        calls.append(data.copy())
        if len(calls) == 1:
            return Response(400, "Bad Request: can't parse entities")
        return Response(200)

    resposta, usou_fallback = enviar_com_fallback(
        fake_post,
        "https://telegram.invalid/sendMessage",
        "test-chat",
        "🌊 <b>Rio</b> &amp; chuva",
    )

    assert resposta.status_code == 200
    assert usou_fallback
    assert calls[0]["parse_mode"] == "HTML"
    assert "parse_mode" not in calls[1]
    assert calls[1]["text"] == "🌊 Rio & chuva"
