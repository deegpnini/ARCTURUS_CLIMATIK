import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import json
import logging
import subprocess
from pathlib import Path
import pandas as pd
from src.relatorios.postgres_db import get_postgres_connection

BASE = Path.cwd()
DATA_DIR = BASE / "data"

FILE_COTA = BASE / "tubarao_saneamento_dados.json"
FILE_ENSEMBLE = DATA_DIR / "chuva_ensemble_consolidada.json"
FILE_SIMULACAO = DATA_DIR / "simulacao_probabilidade_atual.json"
FILE_REGIME = DATA_DIR / "regime_atual.json"
FILE_HEALTH = DATA_DIR / "health_check.json"
FILE_IMPACT_2019 = BASE / "resultados" / "impacto_2019.json"

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


def ler_ultimo_alerta():
    try:
        with FILE_HEALTH.open("r", encoding="utf-8") as arquivo:
            health = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        logging.exception("Não foi possível ler o último alerta do health check.")
        return "Status do alerta indisponível"

    if health.get("status") == "OK":
        return "✅ Nenhum alerta recente"
    if health.get("status") == "ALERTA":
        vz_cm_h = health.get("vz_cm_h")
        try:
            vz_text = f"{float(vz_cm_h):g}"
        except (TypeError, ValueError):
            vz_text = "indisponível"
        return f"⚠️ Alerta enviado ao Telegram (Vz = {vz_text} cm/h)"
    return "Status do alerta indisponível"


def ler_resumo_impacto_2019():
    try:
        with FILE_IMPACT_2019.open("r", encoding="utf-8") as arquivo:
            impacto = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        logging.exception("Não foi possível ler o relatório de impacto de 2019.")
        return None

    try:
        edificacoes = int(impacto["edificacoes_afetadas"])
        escolas = int(impacto["escolas_afetadas"])
        ubs = int(impacto["ubs_afetadas"])
        populacao = impacto["populacao_estimada_afetada"]
        limitacao = impacto["populacao_limitacao"]
    except (KeyError, TypeError, ValueError):
        logging.error("O relatório de impacto de 2019 contém campos inválidos.")
        return None

    return {
        "edificacoes": f"{edificacoes:,}".replace(",", "."),
        "escolas": escolas,
        "ubs": ubs,
        "populacao": "N/D" if populacao is None else f"{int(populacao):,}".replace(",", "."),
        "limitacao_populacao": limitacao,
    }



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
        if health.get("status") == "OK":
            score += 50
        idade = float(health["idade_min"])
        if idade < 20:
            score += 25
        vz_cm_h = float(health["vz_cm_h"])
        if vz_cm_h < 12:
            score += 25
        return score
    except Exception:
        logging.exception("Não foi possível calcular o score operacional.")
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
        connection = get_postgres_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT timestamp, cota_cm
                    FROM leituras
                    WHERE cota_cm IS NOT NULL
                    ORDER BY timestamp DESC, id DESC
                    LIMIT 100
                """)
                rows = cursor.fetchall()
        finally:
            connection.close()

        df = pd.DataFrame(rows, columns=["timestamp", "cota_cm"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        agora = datetime.now()
        df = df.dropna(subset=["timestamp", "cota_cm"])
        df = df[df["timestamp"] >= (agora - timedelta(days=7))]
        df = df.sort_values("timestamp")

        fig = go.Figure()
        if df.empty:
            fig.add_annotation(
                text="Sem leituras recentes no PostgreSQL",
                showarrow=False,
                font=dict(color="#ffcc00"),
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            return fig

        # === FAIXAS DE FUNDO (cores da Defesa Civil) ===
        zonas = [
            (0, 50, "rgba(0, 119, 255, 0.15)", "Baixo (<0,5m)"),          # Azul
            (50, 250, "rgba(0, 200, 0, 0.15)", "Normal (0,5-2,5m)"),       # Verde
            (250, 350, "rgba(255, 200, 0, 0.20)", "Atenção (2,5-3,5m)"),   # Amarelo
            (350, 600, "rgba(255, 120, 0, 0.20)", "Alerta (3,5-6,0m)"),    # Laranja
            (600, 1000, "rgba(255, 0, 0, 0.20)", "Emergência (>6,0m)"),    # Vermelho
        ]
        for y0, y1, cor, nome in zonas:
            fig.add_shape(
                type="rect", x0=df["timestamp"].min(), x1=agora + timedelta(minutes=10),
                y0=y0, y1=y1, line=dict(width=0), fillcolor=cor, layer="below"
            )
            # Rótulo da zona (lado direito)
            fig.add_annotation(
                x=agora + timedelta(minutes=8), y=(y0 + y1) / 2,
                text=nome, showarrow=False, xanchor="left",
                font=dict(size=9, color="rgba(255,255,255,0.6)")
            )

        # === LINHA COLORIDA (muda de cor conforme a cota) ===
        def cor_por_cota(cota):
            if cota < 50: return "#0077FF"      # Azul (Baixo)
            elif cota < 250: return "#00C800"    # Verde (Normal)
            elif cota < 350: return "#FFC800"   # Amarelo (Atenção)
            elif cota < 600: return "#FF7800"   # Laranja (Alerta)
            else: return "#FF0000"              # Vermelho (Emergência)

        cores = [cor_por_cota(c) for c in df["cota_cm"]]
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["cota_cm"],
            mode='lines+markers', name='Cota (cm)',
            line=dict(color='#00d2ff', width=1, dash='dot'),
            marker=dict(size=8, color=cores, line=dict(width=1, color='white')),
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
            xaxis=dict(range=[df['timestamp'].min(), agora + timedelta(minutes=10)],
                       tickformat="%d/%m<br>%H:%M", tickangle=-45, tickfont=dict(size=9))
        )
        return fig
    except Exception as e:
        logging.exception("Não foi possível carregar as leituras do PostgreSQL para o gráfico.")
        fig = go.Figure()
        fig.add_annotation(text=f"Erro PostgreSQL: {e}", showarrow=False, font=dict(color="red"))
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


# ============================================================
# MAPA DE PREVISÃO DO TEMPO (Plotly Scattermapbox)
# ============================================================
def gerar_mapa_previsao_tempo():
    """Gera o mapa interativo da bacia com as previsões do tempo."""
    import json
    from pathlib import Path
    
    BASE = Path(__file__).resolve().parent
    tempo_file = BASE / "data" / "previsao_tempo.json"
    
    if not tempo_file.exists():
        return go.Figure().update_layout(
            title="Previsão do tempo indisponível",
            height=500,
        )
    
    with open(tempo_file, "r") as f:
        tempo = json.load(f)
    
    # Coordenadas das cidades
    COORDENADAS = {
        "lauro_muller": (-28.39, -49.39),
        "orleans": (-28.35, -49.30),
        "anitapolis": (-27.90, -49.13),
        "sao_bonifacio": (-27.90, -48.93),
        "grao_para": (-28.18, -49.22),
        "rio_fortuna": (-28.13, -49.10),
        "santa_rosa_de_lima": (-28.03, -49.13),
        "braco_do_norte": (-28.27, -49.17),
        "sao_ludgero": (-28.32, -49.20),
        "pedras_grandes": (-28.43, -49.18),
        "armazem": (-28.26, -49.02),
        "gravatal": (-28.33, -49.05),
        "sao_martinho": (-28.16, -48.98),
        "tubarao": (-28.48, -49.02),
        "capivari_de_baixo": (-28.45, -48.98),
        "treze_de_maio": (-28.55, -49.15),
        "jaguaruna": (-28.61, -49.03),
        "sangao": (-28.63, -49.13),
        "laguna": (-28.48, -48.78),
    }
    
    lats, lons, textos, cores = [], [], [], []
    
    for cidade, (lat, lon) in COORDENADAS.items():
        if cidade not in tempo:
            continue
        t = tempo[cidade]
        hoje = t.get("hoje", {})
        chuva_hoje = hoje.get("chuva", 0)
        
        if chuva_hoje >= 20:
            cor = "#FF0000"
        elif chuva_hoje >= 5:
            cor = "#FF7800"
        elif chuva_hoje >= 1:
            cor = "#FFC800"
        else:
            cor = "#00C800"
        
        texto = f"<b>{cidade.replace('_', ' ').title()}</b><br>"
        for dia_nome, dia_chave in [("Hoje", "hoje"), ("Amanhã", "amanha"), ("Depois", "depois_amanha")]:
            d = t.get(dia_chave, {})
            texto += f"<b>{dia_nome}:</b> {d.get('temp_min', 0):.0f}°C a {d.get('temp_max', 0):.0f}°C | Chuva: {d.get('chuva', 0):.1f} mm<br>"
        
        lats.append(lat)
        lons.append(lon)
        textos.append(texto)
        cores.append(cor)
    
    fig = go.Figure(go.Scattermap(
        lat=lats,
        lon=lons,
        mode="markers",
        marker=dict(size=15, color=cores, opacity=0.9),
        text=textos,
        hoverinfo="text",
    ))
    
    fig.update_layout(
        map=dict(
            style="open-street-map",
            center=dict(lat=-28.45, lon=-49.10),
            zoom=9,
        ),
        height=500,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
    )
    
    return fig

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
                dbc.Col(
                    html.Div([
                        criar_card(
                            "Probabilidade de Cheia",
                            "prob-val",
                            "prob-sub",
                            "text-success",
                        ),
                        html.Small(
                            "Modo Sombra — Não é sistema de alerta "
                            "(LOEO reprovado: PR-AUC 0.30, Recall 0.16)",
                            className="text-warning d-block mt-2",
                        ),
                    ]),
                    width=3,
                ),
                dbc.Col(criar_card("Regime Hidráulico", "regime-val", "regime-sub", "text-success"), width=3),
                dbc.Col(criar_card("Saúde do Sistema", "health-val", "health-sub", "text-success"), width=3),
                dbc.Col(html.Div([
                    html.H5("Último Alerta", className="card-title"),
                    html.P(ler_ultimo_alerta(), id="ultimo-alerta-val", className="card-text"),
                ], className="card-body"), width=3),
                dbc.Col(criar_card("ARCTURUS STATUS", "score-val", "score-sub", "text-success"), width=3),
            ], className="mb-4"),

            dbc.Row([
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.H5("A.C. Atlas — Impacto 2019", className="card-title"),
                            html.Div(
                                [
                                    html.P(
                                        f"Edificações afetadas: {impacto['edificacoes']}"
                                    ),
                                    html.P(
                                        f"Escolas afetadas: {impacto['escolas']}"
                                    ),
                                    html.P(f"UBS afetadas: {impacto['ubs']}"),
                                    html.P(
                                        f"População estimada: {impacto['populacao']}"
                                    ),
                                    html.Small(
                                        impacto["limitacao_populacao"],
                                        className="text-muted",
                                    ),
                                ]
                                if (impacto := ler_resumo_impacto_2019())
                                else [html.P("Relatório de impacto indisponível.")]
                            ),
                        ]),
                        color="dark",
                        outline=True,
                    ),
                    width=12,
                )
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
            
            
    # ============================================================
    # SEÇÃO: MAPA DE PREVISÃO DO TEMPO (Bacia do Rio Tubarão)
    # ============================================================
    html.Hr(),
    html.H3("🌤️ Previsão do Tempo — Bacia do Rio Tubarão", className="text-center mt-4"),
    html.P("Cores indicam a chuva prevista para hoje. Passe o mouse para ver os detalhes.", className="text-center text-muted small"),
    dbc.Row([
        dbc.Col(dcc.Graph(id="mapa-previsao-tempo", figure=gerar_mapa_previsao_tempo()), width=12),
    ]),
    html.Hr(),
dbc.Row([
                dbc.Col(dcc.Graph(id="grafico-cota", figure=gerar_grafico_cota()), width=12),
                # === LEGENDA DAS CORES (Defesa Civil) ===
                dbc.Row([
                    dbc.Col(html.Div([
                        html.Div(style={"backgroundColor": "#0077FF", "width": "20px", "height": "20px", "display": "inline-block", "marginRight": "5px", "verticalAlign": "middle"}),
                        html.Span("Baixo (<0,5m)", style={"fontSize": "12px", "color": "#aaa", "verticalAlign": "middle"}),
                    ], style={"display": "inline-block", "marginRight": "15px"}), width="auto"),
                    dbc.Col(html.Div([
                        html.Div(style={"backgroundColor": "#00C800", "width": "20px", "height": "20px", "display": "inline-block", "marginRight": "5px", "verticalAlign": "middle"}),
                        html.Span("Normal (0,5-2,5m)", style={"fontSize": "12px", "color": "#aaa", "verticalAlign": "middle"}),
                    ], style={"display": "inline-block", "marginRight": "15px"}), width="auto"),
                    dbc.Col(html.Div([
                        html.Div(style={"backgroundColor": "#FFC800", "width": "20px", "height": "20px", "display": "inline-block", "marginRight": "5px", "verticalAlign": "middle"}),
                        html.Span("Atenção (2,5-3,5m)", style={"fontSize": "12px", "color": "#aaa", "verticalAlign": "middle"}),
                    ], style={"display": "inline-block", "marginRight": "15px"}), width="auto"),
                    dbc.Col(html.Div([
                        html.Div(style={"backgroundColor": "#FF7800", "width": "20px", "height": "20px", "display": "inline-block", "marginRight": "5px", "verticalAlign": "middle"}),
                        html.Span("Alerta (3,5-6,0m)", style={"fontSize": "12px", "color": "#aaa", "verticalAlign": "middle"}),
                    ], style={"display": "inline-block", "marginRight": "15px"}), width="auto"),
                    dbc.Col(html.Div([
                        html.Div(style={"backgroundColor": "#FF0000", "width": "20px", "height": "20px", "display": "inline-block", "marginRight": "5px", "verticalAlign": "middle"}),
                        html.Span("Emergência (>6,0m)", style={"fontSize": "12px", "color": "#aaa", "verticalAlign": "middle"}),
                    ], style={"display": "inline-block", "marginRight": "15px"}), width="auto"),
                ], justify="center", style={"marginTop": "10px", "marginBottom": "20px"})
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
     Output("score-val", "children"), Output("score-sub", "children"), Output("score-val", "className"),
     Output("ultimo-alerta-val", "children")],
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
        connection = get_postgres_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT cota_cm
                    FROM leituras
                    WHERE cota_cm IS NOT NULL
                    ORDER BY timestamp DESC, id DESC
                    LIMIT 2
                """)
                ultimas_cotas = cursor.fetchall()
        finally:
            connection.close()

        if len(ultimas_cotas) >= 2:
            cota_atual = ultimas_cotas[0][0]
            cota_anterior = ultimas_cotas[1][0]
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
    except Exception:
        logging.exception("Não foi possível calcular os insights com dados PostgreSQL.")
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

    return cota_val, cota_sub, chuva_val, chuva_sub, prob_val, prob_sub, regime_val, regime_class, regime_sub, msg, fig, health_status, health_status, health_color, score_status, score_status, score_color, ler_ultimo_alerta()


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
