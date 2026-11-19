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
        ativas = [c for c in dados if c.get("status") == "ATIVA"]
        return sorted(ativas, key=lambda x: (x.get("prioridade", 9), x.get("id", "")))
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

def renderizar_player_selecionado(cam: dict | None = None):
    if not cam:
        cams = carregar_cameras_ativas()
        cam = cams[0] if cams else None
    if not cam:
        return html.Div()

    vid = extrair_video_id(cam.get("url_youtube", ""))
    reg = cam.get("regiao_arcturus", "BACIA_TUBARAO")
    reg_nome, reg_cor = REGIOES_LABEL.get(reg, (reg, "info"))
    url = cam.get("url_youtube", "#")

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
                        "🔗 Abrir transmissão em tela cheia no YouTube",
                        href=url,
                        target="_blank",
                        className="btn btn-sm btn-outline-info",
                    ),
                ], xs=12, lg=5, className="mb-3 mb-lg-0 d-flex flex-column justify-content-center"),
                dbc.Col([
                    html.Iframe(
                        src=f"https://www.youtube.com/embed/{vid}?autoplay=1&mute=1&rel=0",
                        style={"width": "100%", "height": "300px", "border": "1px solid #A855F7", "borderRadius": "8px"},
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture",
                    ) if vid else html.Div("Stream indisponível", className="text-muted"),
                ], xs=12, lg=7),
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
        vid = extrair_video_id(c.get("url_youtube", ""))
        reg = c.get("regiao_arcturus", "BACIA_TUBARAO")
        reg_nome, reg_cor = REGIOES_LABEL.get(reg, (reg, "secondary"))
        prio = c.get("prioridade", 4)
        url = c.get("url_youtube", "#")

        player_box = (
            html.Div(
                html.Iframe(
                    src=f"https://www.youtube.com/embed/{vid}?autoplay=0&mute=1&rel=0",
                    style={"width": "100%", "height": "210px", "border": "0", "borderRadius": "6px"},
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture",
                ),
                className="mb-2",
            )
            if vid
            else html.Div("Stream indisponível", className="text-muted small mb-2")
        )

        card = dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.Div([
                        dbc.Badge(f"{c.get('id', '').upper()} • P{prio}", color="dark", className="me-1 border border-secondary"),
                        dbc.Badge(reg_nome, color=reg_cor, className="me-1"),
                        dbc.Badge("● AO VIVO", color="danger", className="float-end"),
                    ], className="mb-2"),
                    html.H6(f"{c.get('municipio', '')} — {c.get('canal', '')}", className="text-white fw-bold mb-1"),
                    player_box,
                    html.P(c.get("notas", ""), className="text-muted small mb-2", style={"minHeight": "38px"}),
                    html.A(
                        "🔗 Abrir em tela cheia no YouTube",
                        href=url,
                        target="_blank",
                        className="btn btn-sm btn-outline-info w-100",
                    ),
                ]),
                className="bg-dark border-secondary shadow-sm h-100",
            ),
            xs=12, md=6, lg=4, className="mb-3",
        )
        cards.append(card)

    return dbc.Row(cards)
