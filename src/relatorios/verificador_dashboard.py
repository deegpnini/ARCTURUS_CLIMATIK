"""verificador_dashboard.py — Carrega o JSON do verificador e monta KPIs."""
import json
from pathlib import Path
import dash_bootstrap_components as dbc
from dash import html


def carregar_verificacao():
    p = Path("data/verificacao_previsoes.json")
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def renderizar_kpis_verificador():
    dados = carregar_verificacao()
    if not dados or "resumo" not in dados:
        return html.Div("Verificador indisponível", className="text-muted")
    cards = []
    for h in ["1h", "3h", "6h"]:
        r = dados["resumo"].get(h)
        if not r:
            continue
        cor = "success" if r["taxa_acerto_aproximado"] >= 80 else "warning" if r["taxa_acerto_aproximado"] >= 50 else "danger"
        cards.append(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H6(f"Horizonte {h}", className="text-info"),
                        html.H4(f"{r['taxa_acerto_aproximado']}%", className=f"text-{cor}"),
                        html.Small(f"MAE {r['mae_cm']} cm | n={r['total']}"),
                        html.Br(),
                        html.Small(f"Exato: {r['taxa_acerto_exato']}% | Graves: {r['graves']}", className="text-muted"),
                    ]),
                    className=f"bg-dark border-{cor}",
                ),
                xs=12, md=4,
            )
        )
    return dbc.Row(cards, className="mb-4")
