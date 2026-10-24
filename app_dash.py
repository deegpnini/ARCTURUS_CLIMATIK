import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import json
import subprocess
from pathlib import Path
import pandas as pd

BASE = Path.cwd()
DATA_DIR = BASE / "data"

FILE_COTA = BASE / "tubarao_saneamento_dados.json"
FILE_ENSEMBLE = DATA_DIR / "chuva_ensemble_consolidada.json"
FILE_SIMULACAO = DATA_DIR / "simulacao_probabilidade_atual.json"
FILE_REGIME = DATA_DIR / "regime_atual.json"
FILE_HISTORICO = BASE / "resultados" / "historico_previsoes.csv"

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], title="ARCTURUS CLIMATIK")

def ler_dados():
    cota_val = "-- cm"
    chuva_val = "-- mm"
    chuva_sub = "Aguardando dados..."
    prob_val = "-- %"
    prob_sub = "Aguardando simulação..."
    regime_val = "DESCONHECIDO"
    regime_sub = "Vz = -- cm/h"
    regime_color = "text-muted"
    
    if FILE_COTA.exists():
        try:
            with open(FILE_COTA, "r") as f:
                cota_val = f"{json.load(f).get('cota_cm', 0):.1f} cm"
        except: pass

    if FILE_ENSEMBLE.exists():
        try:
            with open(FILE_ENSEMBLE, "r") as f:
                ens = json.load(f)
                chuva_val = f"{ens.get('pior_caso_48h_mm', 0):.1f} mm"
                diferenca = ens.get('diferenca_mm', 0)
                chuva_sub = f"Δ Incerteza: {diferenca:.1f} mm"
        except: pass

    if FILE_SIMULACAO.exists():
        try:
            with open(FILE_SIMULACAO, "r") as f:
                sim = json.load(f)
                prob = sim.get('prob_pior_caso', 0)
                prob_val = f"{prob:.2f}%"
                prob_sub = "Seguro" if prob < 20 else "Risco Elevado"
        except: pass

    if FILE_REGIME.exists():
        try:
            with open(FILE_REGIME, "r") as f:
                reg = json.load(f)
                status = reg.get("regime", "NORMAL")
                vz = reg.get("delta_60m", 0.0)
                regime_val = status
                sinal = "+" if vz > 0 else ""
                regime_sub = f"Vz: {sinal}{vz:.1f} cm/h"
                
                if status == "NORMAL": regime_color = "text-success"
                elif status == "ATENCAO": regime_color = "text-warning"
                else: regime_color = "text-danger"
        except: pass

    return cota_val, chuva_val, chuva_sub, prob_val, prob_sub, regime_val, regime_sub, regime_color

def gerar_grafico_cota():
    if not FILE_HISTORICO.exists():
        return go.Figure()
    
    try:
        df = pd.read_csv(FILE_HISTORICO)
        df = df.tail(20)  # Últimas 20 leituras
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["timestamp_execucao"], 
            y=df["cota_atual_cm"],
            mode="lines+markers",
            name="Cota (cm)",
            line=dict(color="#00bfff", width=3)
        ))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#000",
            plot_bgcolor="#000",
            margin=dict(l=20, r=20, t=20, b=20),
            height=200,
            xaxis_title="Tempo",
            yaxis_title="Cota (cm)"
        )
        return fig
    except:
        return go.Figure()

def criar_card(titulo, id_valor, id_sub, color_class="text-white", card_color="#111"):
    return dbc.Card(
        dbc.CardBody([
            html.H6(titulo, className="card-subtitle text-muted mb-2"),
            html.H2(id=id_valor, className=f"card-title {color_class}"),
            html.Small(id=id_sub, className="text-info")
        ]),
        className="shadow-sm border-secondary",
        style={"backgroundColor": card_color}
    )

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.Img(src="/assets/logo_arcturus.jpg", style={"width": "150px"}),
            html.H2("🌊 ARCTURUS CLIMATIK", className="text-primary mt-2"),
            html.P("Painel de Controle — Gêmeo Digital Hidrológico", className="text-muted"),
        ], width=2, style={"backgroundColor": "#0a0a0a", "padding": "20px", "minHeight": "100vh"}),
        
        dbc.Col([
            html.Hr(),
            dbc.Row([
                dbc.Col(criar_card("Cota Atual (ERAB)", "cota-val", "cota-sub"), width=3),
                dbc.Col(criar_card("Chuva Prevista (48h Pior Caso)", "chuva-val", "chuva-sub"), width=3),
                dbc.Col(criar_card("Probabilidade de Cheia", "prob-val", "prob-sub", "text-success"), width=3),
                dbc.Col(criar_card("Regime Hidráulico", "regime-val", "regime-sub", "text-success"), width=3),
            ], className="mb-4"),
            
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        id="loading-atualizar",
                        type="circle",
                        children=[
                            dbc.Button("🔄 Atualizar Tudo", id="btn-atualizar", color="danger", className="w-100 mb-2")
                        ]
                    ),
                    html.Div(id="status-msg", className="text-center text-muted small")
                ], width=4)
            ], className="justify-content-center mb-4"),
            
            dbc.Row([
                dbc.Col(dcc.Graph(id="grafico-cota", figure=gerar_grafico_cota()), width=12)
            ])
        ], width=10, style={"padding": "20px"})
    ], className="g-0")
], fluid=True, style={"minHeight": "100vh", "backgroundColor": "#000"})

@app.callback(
    [Output("cota-val", "children"), Output("cota-sub", "children"),
     Output("chuva-val", "children"), Output("chuva-sub", "children"),
     Output("prob-val", "children"), Output("prob-sub", "children"),
     Output("regime-val", "children"), Output("regime-val", "className"), Output("regime-sub", "children"),
     Output("status-msg", "children"), Output("grafico-cota", "figure")],
    [Input("btn-atualizar", "n_clicks")]
)
def atualizar_painel(n_clicks):
    msg = "Aguardando comando..."
    
    if n_clicks and n_clicks > 0:
        try:
            subprocess.run(["python3", "src/relatorios/comparar_fontes_chuva.py"], check=True)
            subprocess.run(["python3", "src/modelo/simular_ensemble.py"], check=True)
            msg = "✅ Pipeline executado. Dados atualizados."
        except subprocess.CalledProcessError as e:
            msg = f"❌ Erro na execução: {e}"

    cota_val, chuva_val, chuva_sub, prob_val, prob_sub, regime_val, regime_sub, regime_color = ler_dados()
    
    regime_class = f"card-title {regime_color}"
    cota_sub = "Sensor Online"
    
    fig = gerar_grafico_cota()

    return cota_val, cota_sub, chuva_val, chuva_sub, prob_val, prob_sub, regime_val, regime_class, regime_sub, msg, fig

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
