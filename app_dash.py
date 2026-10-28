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
    health_status = "⚪ Health Check indisponível"
    health_color = "text-muted"
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
                prob_val = 'INDISPONÍVEL'
                prob_sub = 'Estimativa em revisão. Use Defesa Civil / Epagri-Ciram / INMET'
        except: pass

    # --- LEITURA DO HEALTH CHECK ---
    try:
        with open("data/health_check.json", "r") as f:
            health = json.load(f)
        if (health.get("sensor_erab", {}).get("status", "").startswith("🟢") and
            health.get("pipeline_regime", {}).get("status", "").startswith("🟢")):
            health_status = "🟢 Todos os sistemas operacionais"
            health_color = "text-success"
        else:
            health_status = "🟡 Atenção ao sistema"
            health_color = "text-warning"
    except Exception:
        pass

    if FILE_REGIME.exists():
        try:
            with open(FILE_REGIME, "r") as f:
                reg = json.load(f)
                status = reg.get("regime", "NORMAL")
                vz = reg.get("delta_60m", 0.0)
                regime_val = status
                sinal = "+" if vz > 0 else ""
                regime_sub = f"Vz: {sinal}{vz:.1f} cm/h"

                az_val = reg.get("aceleracao_az", 0.0)
                if az_val > 5:
                    regime_sub += f" | Az = +{az_val:.1f} cm/h² (acelerando)"
                elif az_val < -5:
                    regime_sub += f" | Az = {az_val:.1f} cm/h² (desacelerando)"
                else:
                    regime_sub += f" | Az = {az_val:.1f} cm/h² (estável)"
                
                # --- TEMPO ATÉ O LIMIAR ---
                t200 = reg.get("tempo_para_200h")
                t300 = reg.get("tempo_para_300h")
                if t200 or t300:
                    tempos = []
                    if t200: tempos.append(f"200cm em {t200:.1f}h")
                    if t300: tempos.append(f"300cm em {t300:.1f}h")
                    regime_sub += f" | Est: {' / '.join(tempos)}"
                else:
                    regime_sub += " | Est: rio estável"
                
                if status == "NORMAL": regime_color = "text-success"
                elif status == "ATENCAO": regime_color = "text-warning"
                else: regime_color = "text-danger"
        except: pass

    return cota_val, chuva_val, chuva_sub, prob_val, prob_sub, regime_val, regime_sub, regime_color, health_status, health_color



def ler_ultimos_incidentes(n=5):
    """Lê os últimos N incidentes do log_incidentes.jsonl."""
    from pathlib import Path
    log_path = Path("data/log_incidentes.jsonl")
    if not log_path.exists():
        return []
    try:
        import json
        with open(log_path, "r") as f:
            linhas = f.readlines()
        ultimos = linhas[-n:]
        return [json.loads(l) for l in ultimos if l.strip()]
    except Exception:
        return []





def calcular_score_operacional():
    """Calcula o score de 0 a 100 baseado no health_check.json."""
    try:
        with open("data/health_check.json", "r") as f:
            health = json.load(f)
        score = 0
        # Sensor ERAB online (+25)
        if health.get("sensor_erab", {}).get("status", "").startswith("🟢"):
            score += 25
        # Pipeline online (+25)
        if health.get("pipeline_regime", {}).get("status", "").startswith("🟢"):
            score += 25
        # Banco online (+25) - verifica se o SQLite existe e tem dados
        from pathlib import Path
        if Path("data/arcturus.db").exists():
            score += 25
        # Última leitura < 20 min (+25)
        idade = health.get("sensor_erab", {}).get("idade_min", 999)
        if idade < 20:
            score += 25
        return score
    except Exception:
        return 0

def gerar_resumo_executivo(cota, vz, az, regime):
    """Gera uma frase em linguagem natural a partir dos números."""
    if regime == "EXTREMO":
        return f"🚨 EMERGÊNCIA: Rio em {cota:.1f} cm, subindo a {vz:.1f} cm/h com aceleração de {az:.1f} cm/h². Evacuação imediata."
    elif regime == "ATENCAO":
        return f"⚠️ ATENÇÃO: Rio em {cota:.1f} cm, subindo a {vz:.1f} cm/h. A aceleração é de {az:.1f} cm/h². Monitore de perto."
    else:
        if vz > 0:
            return f"✅ NORMAL: Rio em {cota:.1f} cm, subindo lentamente ({vz:.1f} cm/h). A aceleração é de {az:.1f} cm/h²."
        elif vz < 0:
            return f"✅ NORMAL: Rio em {cota:.1f} cm, em queda de {abs(vz):.1f} cm/h. A desaceleração é de {az:.1f} cm/h²."
        else:
            return f"✅ NORMAL: Rio em {cota:.1f} cm, estável. Sem tendência de subida ou queda."

def gerar_grafico_cota():
    import pandas as pd
    import plotly.graph_objects as go
    from datetime import datetime, timedelta
    
    try:
        df = pd.read_csv("resultados/historico_previsoes.csv")
        df['timestamp_execucao'] = pd.to_datetime(df['timestamp_execucao'], format='mixed', errors='coerce')
        agora = datetime.now()
        
        # FILTRO: mostra apenas os últimos 7 dias (evita picos antigos)
        df = df[df['timestamp_execucao'] >= (agora - timedelta(days=7))]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp_execucao'], y=df['cota_atual_cm'],
            mode='lines+markers', name='Cota (cm)',
            line=dict(color='#00d2ff', width=3), marker=dict(size=6),
            hovertemplate='<b>%{x|%d/%m/%Y %H:%M}</b><br>Cota: %{y:.1f} cm<extra></extra>'
        ))
        
        # WORKAROUND: add_shape + add_annotation separados (evita bug do Plotly)
        fig.add_shape(type="line", x0=agora, x1=agora, y0=0, y1=1, yref="paper",
                      line=dict(color="#ff6b6b", width=2, dash="dot"))
        fig.add_annotation(x=agora, y=1, yref="paper", text=f"Agora: {agora.strftime('%d/%m/%Y %H:%M:%S')}",
                           showarrow=False, xanchor="left", yanchor="bottom",
                           font=dict(size=10, color="#ff6b6b"))

        fig.update_layout(
            title="Cota do Rio Tubarão (Tempo Real)", xaxis_title="Data / Hora", yaxis_title="Cota (cm)",
            template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=40, r=20, t=60, b=40),
            xaxis=dict(range=[df['timestamp_execucao'].min(), agora + timedelta(minutes=10)],
                       tickformat="%d/%m<br>%H:%M", tickangle=-45, tickfont=dict(size=9))
        )
        return fig
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(text=f"Erro: {e}", showarrow=False, font=dict(color="red"))
        fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        return fig

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
    # --- BARRA LATERAL (SIDEBAR) ---
    html.Div([
        # Logo do ARCTURUS (preservada)
        html.Img(src="assets/logo_arcturus.jpg", style={"width": "100%", "marginBottom": "20px"}),
        html.H4("A.C.", className="text-white mb-3"),
        html.Hr(),
        dbc.Nav([
            dbc.NavLink("📊 A.C. Monitor", href="/", active="exact", className="text-white"),
            dbc.NavLink("📷 A.C. Vision (Câmera ERAB)", href="https://tubaraosaneamento.com.br/nivelriotubarao_termometro/get_historico", target="_blank", className="text-white"),
            dbc.Button(
                "🗺️ A.C. Geo (Mapa 2019)",
                id="btn-mapa-geo",
                color="dark",
                className="text-white text-start w-100",
            ),
            dbc.NavLink("🛰️ A.C. Sentinel (Satélite)", href="https://earth.google.com/web/@-28.48,-49.02,100a,1000d,35y,0h,0t,0r", target="_blank", className="text-white"),
        ], vertical=True, pills=True),
    ], style={
        "backgroundColor": "#1a1a1a", 
        "padding": "20px", 
        "height": "100vh", 
        "overflowY": "auto",
        "position": "fixed", 
        "width": "250px", 
        "left": 0, 
        "top": 0, 
        "zIndex": 1000
    }),
    # --- CONTEÚDO PRINCIPAL (com margem à esquerda para não ficar atrás da barra) ---
    html.Div([
        # (o conteúdo original do dbc.Container começa aqui)
    ], style={"marginLeft": "250px"}),
    dcc.Interval(
        id='intervalo-atualizacao',
        interval=30*1000, # Atualiza a cada 30 segundos
        n_intervals=0
    ),
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
                dbc.Col(criar_card("Saúde do Sistema", "health-val", "health-sub", "text-success"), width=3),
                dbc.Col(html.Div([
                    html.H5("A.C. Vision", className="card-title"),
                    html.P("📷 Câmera ERAB", className="card-text"),
                    html.A("Abrir Câmera", href="https://tubaraosaneamento.com.br/nivelriotubarao_termometro/get_historico", target="_blank", className="btn btn-primary btn-sm")
                ], className="card-body"), width=3),
                dbc.Col(criar_card("ARCTURUS STATUS", "score-val", "score-sub", "text-success"), width=3),
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
            ]),
            html.Div(
                [
                    html.H3("Mapa de Inundação — Tubarão, Maio/2019"),
                    html.Img(
                        src="/assets/mapa_inundacao_tubarao_2019_satelite.png",
                        alt="Mapa de inundação de Tubarão em maio de 2019",
                        style={"width": "100%", "height": "auto"},
                    ),
                    html.A(
                        "Abrir arquivo original",
                        href="/assets/mapa_inundacao_tubarao_2019_satelite.png",
                        target="_blank",
                        className="btn btn-outline-info mt-2",
                    ),
                ],
                id="secao-mapa-geo",
                style={"display": "none", "marginTop": "24px"},
            ),
        ], width=10, style={"padding": "20px"})
    ], className="g-0")
], fluid=True, style={"minHeight": "100vh", "backgroundColor": "#000"})

@app.callback(
    Output("secao-mapa-geo", "style"),
    Input("btn-mapa-geo", "n_clicks"),
)
def alternar_mapa_geo(n_clicks):
    if n_clicks and n_clicks % 2:
        return {"display": "block", "marginTop": "24px"}
    return {"display": "none", "marginTop": "24px"}


@app.callback(
    [Output("cota-val", "children"), Output("cota-sub", "children"),
     Output("chuva-val", "children"), Output("chuva-sub", "children"),
     Output("prob-val", "children"), Output("prob-sub", "children"),
     Output("regime-val", "children"), Output("regime-val", "className"), Output("regime-sub", "children"),
     Output("status-msg", "children"), Output("grafico-cota", "figure"),
     Output("health-val", "children"), Output("health-sub", "children"), Output("health-val", "className"),
     Output("score-val", "children"), Output("score-sub", "children"), Output("score-val", "className")],
    [Input("btn-atualizar", "n_clicks"),
     Input("intervalo-atualizacao", "n_intervals")]
)
def atualizar_painel(n_clicks, n_intervals):
    # O Dash apenas LÊ os dados atualizados pelo cron. Não roda mais subprocessos em loop.
    # --- RESUMO EXECUTIVO (IDEIA DO ENGENHEIRO) ---
    try:
        with open("data/regime_atual.json", "r") as f:
            reg_data = json.load(f)
            cota_n = float(cota_val.replace(" cm", "")) if cota_val != "-- cm" else 0.0
            vz_n = reg_data.get("delta_60m", 0.0)
            az_n = reg_data.get("aceleracao_az", 0.0)
            regime_n = reg_data.get("regime", "NORMAL")
            msg = gerar_resumo_executivo(cota_n, vz_n, az_n, regime_n)
    except Exception:
        msg = f"🔄 Atualizado (Ciclo {n_intervals})" if n_intervals else "✅ Painel carregado."
    
    try:
        import json
        from datetime import datetime
        with open("data/regime_atual.json", "r") as f:
            regime_data = json.load(f)
            hora_raw = regime_data.get("atualizado", "Desconhecida")
            hora_dt = datetime.fromisoformat(hora_raw)
            hora_formatada = hora_dt.strftime("%H:%M:%S")
    except Exception:
        hora_formatada = "Desconhecida"

    cota_val, chuva_val, chuva_sub, prob_val, prob_sub, regime_val, regime_sub, regime_color, health_status, health_color = ler_dados()
    
    cota_sub = f"Última leitura: {hora_formatada}"
    regime_class = f"card-title {regime_color}"
    fig = gerar_grafico_cota()

    # --- MOTOR DE INTELIGÊNCIA (INSIGHTS) ---
    try:
        import pandas as pd
        df = pd.read_csv("resultados/historico_previsoes.csv")
        if len(df) >= 2:
            cota_atual = df.iloc[-1]['cota_atual_cm']
            cota_anterior = df.iloc[-2]['cota_atual_cm']
            variacao = cota_atual - cota_anterior
            
            # Lê o JSON de chuva
            import json
            with open("data/chuva_ensemble_consolidada.json", "r") as f:
                chuva = json.load(f)
                chuva_pior = chuva.get("pior_caso_48h_mm", 0)
                
            if variacao > 2:
                direcao = f"subiu {variacao:.1f} cm"
                causa = f"provavelmente influenciado pela chuva prevista de {chuva_pior} mm"
            elif variacao < -2:
                direcao = f"baixou {abs(variacao):.1f} cm"
                causa = "devido à estiagem nas cabeceiras"
            else:
                direcao = "estabilizou"
                causa = "mantendo o nível atual"
                
            # O Resumo Executivo já foi definido acima (gerar_resumo_executivo).
            # Este bloco antigo foi removido para não sobrescrever o resumo.
            pass
    except Exception as e:
        pass
    # ----------------------------------------

    # --- SCORE OPERACIONAL (IDEIA DO ENGENHEIRO) ---
    score = calcular_score_operacional()
    if score >= 75:
        score_color = "text-success"
        score_status = f"🟢 {score}/100 (Saudável)"
    elif score >= 50:
        score_color = "text-warning"
        score_status = f"🟡 {score}/100 (Atenção)"
    elif score >= 25:
        score_color = "text-warning"
        score_status = f"🟠 {score}/100 (Degradado)"
    else:
        score_color = "text-danger"
        score_status = f"🔴 {score}/100 (Crítico)"

    return cota_val, cota_sub, chuva_val, chuva_sub, prob_val, prob_sub, regime_val, regime_class, regime_sub, msg, fig, health_status, health_status, health_color, score_status, score_status, score_color


if __name__ == "__main__":
    import threading
    import time
    import os
    import subprocess

    def abrir_chrome():
        # Espera o Dash carregar completamente (3.5 segundos é o tempo médio do Flask subir)
        time.sleep(3.5)
        # Tenta abrir usando os comandos do WSL (explorer ou wslview)
        os.system("explorer.exe 'http://localhost:8050' 2>/dev/null || wslview 'http://localhost:8050' 2>/dev/null &")

    # Inicia a thread que abre o navegador em paralelo
    threading.Thread(target=abrir_chrome, daemon=True).start()

    # Inicia o servidor Dash (use_reloader=False impede que ele abra duas abas e quebre a thread)
    app.run(debug=False, use_reloader=False, host="0.0.0.0", port=8050)
