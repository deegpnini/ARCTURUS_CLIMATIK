import json
import re
from pathlib import Path
from dash import html
import dash_bootstrap_components as dbc

REGIOES_LABEL = {
    "BACIA_TUBARAO": ("🌊 Bacia do Tubarão", "info"),
    "SUL_SC": ("🏖️ Sul SC", "warning"),
    "SERRA_SC": ("⛰️ Serra SC", "success"),
    "LITORAL_SC": ("🌴 Litoral SC", "primary"),
    "VALE_ITAJAI_NORTE": ("🏞️ Vale / Norte SC", "secondary"),
    "OESTE_SC": ("🌾 Oeste SC", "dark"),
}

def carregar_cameras_ativas():
    p = Path("data/cameras_publicas.json")
    if not p.exists():
        return []
    try:
        dados = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(dados, dict):
            lista = dados.get("cameras", [])
        elif isinstance(dados, list):
            lista = dados
        else:
            return []
        ativas = [c for c in lista if isinstance(c, dict) and c.get("status") == "ATIVA"]
        return sorted(ativas, key=lambda x: (int(x.get("prioridade", 9)), 0 if x.get("id") == "cam_000" else 1, x.get("id", "")))
    except Exception:
        return []

def extrair_video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url or "")
    return m.group(1) if m else ""

def buscar_camera_por_id(cam_id: str):
    for c in carregar_cameras_ativas():
        if c.get("id") == cam_id:
            return c
    return None

def _is_web_oficial(cam: dict) -> bool:
    return cam.get("fonte") == "web_oficial" or bool(cam.get("url_web"))

def _painel_web_oficial(cam: dict, altura: str = "210px"):
    embed_url = cam.get("url_embed") or "https://rtsp.me/embed/G24fSDZB/"
    return html.Div(
        html.Iframe(
            src=embed_url,
            style={
                "width": "100%",
                "height": altura,
                "border": "1px solid #0dcaf0",
                "borderRadius": "6px",
                "backgroundColor": "#000",
            },
            allow="autoplay; fullscreen; encrypted-media; picture-in-picture",
        ),
        className="mb-2",
    )

def renderizar_player_selecionado(cam: dict | None = None):
    if not cam:
        cams = carregar_cameras_ativas()
        cam = cams[0] if cams else None
    if not cam:
        return html.Div()

    eh_web = _is_web_oficial(cam)
    vid = "" if eh_web else extrair_video_id(cam.get("url_youtube", ""))
    reg = cam.get("regiao_arcturus", "BACIA_TUBARAO")
    reg_nome, reg_cor = REGIOES_LABEL.get(reg, (reg, "info"))
    url = cam.get("url_web") if eh_web else cam.get("url_youtube", "#")
    texto_botao = "🔗 Abrir portal oficial da Tubarão Saneamento" if eh_web else "🔗 Abrir transmissão em tela cheia no YouTube"

    if eh_web:
        media_component = _painel_web_oficial(cam, altura="260px")
    elif vid:
        media_component = html.Iframe(
            src=f"https://www.youtube.com/embed/{vid}?autoplay=1&mute=1&rel=0",
            style={"width": "100%", "height": "300px", "border": "1px solid #A855F7", "borderRadius": "8px"},
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture",
        )
    else:
        media_component = html.Div("Stream indisponível", className="text-muted")

    return dbc.Card(
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        dbc.Badge("🎯 MONITORAMENTO INSTANTÂNEO (CLIQUE NO MAPA)", color="danger", className="me-2"),
                        dbc.Badge(f"{cam.get('id', '').upper()} • Prioridade {cam.get('prioridade', 1)}", color="dark", className="me-1 border border-info"),
                        dbc.Badge(reg_nome, color=reg_cor),
                    ], className="mb-2"),
                    html.H5(f"📹 {cam.get('municipio', '')} — {cam.get('canal', '')}", className="text-info fw-bold mb-1"),
                    html.P(cam.get("titulo_stream", ""), className="text-white small mb-1"),
                    html.P(cam.get("notas", ""), className="text-muted small mb-2"),
                    html.A(
                        texto_botao,
                        href=url,
                        target="_blank",
                        rel="noopener noreferrer",
                        className="btn btn-sm btn-outline-info",
                    ),
                ], xs=12, lg=5, className="mb-3 mb-lg-0 d-flex flex-column justify-content-center"),
                dbc.Col([media_component], xs=12, lg=7),
            ]),
        ]),
        className="bg-dark border-info shadow mt-3 mb-3",
    )

def renderizar_grade_cameras(filtro_regiao: str = "TODAS"):
    cams = carregar_cameras_ativas()
    if filtro_regiao and filtro_regiao != "TODAS":
        cams = [c for c in cams if c.get("regiao_arcturus") == filtro_regiao]

    if not cams:
        return dbc.Alert("Nenhuma câmera ativa cadastrada ainda para esta macrorregião.", color="secondary")

    cards = []
    for c in cams:
        eh_web = _is_web_oficial(c)
        vid = "" if eh_web else extrair_video_id(c.get("url_youtube", ""))
        reg = c.get("regiao_arcturus", "BACIA_TUBARAO")
        reg_nome, reg_cor = REGIOES_LABEL.get(reg, (reg, "secondary"))
        prio = c.get("prioridade", 4)
        url = c.get("url_web") if eh_web else c.get("url_youtube", "#")
        texto_botao = "🔗 Abrir portal oficial da Tubarão Saneamento" if eh_web else "🔗 Abrir em tela cheia no YouTube"

        if eh_web:
            player_box = _painel_web_oficial(c, altura="210px")
        elif vid:
            player_box = html.Div(
                html.Iframe(
                    src=f"https://www.youtube.com/embed/{vid}?autoplay=0&mute=1&rel=0",
                    style={"width": "100%", "height": "210px", "border": "0", "borderRadius": "6px"},
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture",
                ),
                className="mb-2",
            )
        else:
            player_box = html.Div("Stream indisponível", className="text-muted small mb-2")

        card = dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.Div([
                        dbc.Badge(f"{c.get('id', '').upper()} • P{prio}", color="dark", className="me-1 border border-info" if eh_web else "me-1 border border-secondary"),
                        dbc.Badge(reg_nome, color=reg_cor, className="me-1"),
                        dbc.Badge("● OFICIAL" if eh_web else "● AO VIVO", color="info" if eh_web else "danger", className="float-end"),
                    ], className="mb-2"),
                    html.H6(f"{c.get('municipio', '')} — {c.get('canal', '')}", className="text-white fw-bold mb-1"),
                    player_box,
                    html.P(c.get("notas", ""), className="text-muted small mb-2", style={"minHeight": "38px"}),
                    html.A(
                        texto_botao,
                        href=url,
                        target="_blank",
                        rel="noopener noreferrer",
                        className="btn btn-sm btn-info fw-bold w-100" if eh_web else "btn btn-sm btn-outline-info w-100",
                    ),
                ]),
                className="bg-dark border-info shadow h-100" if eh_web else "bg-dark border-secondary shadow-sm h-100",
            ),
            xs=12, md=6, lg=4, className="mb-3",
        )
        cards.append(card)

    return dbc.Row(cards)
