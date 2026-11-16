from src.relatorios.dashboard_kpis import obter_kpis_operacionais
import dash
import json
from pathlib import Path

CLIMA_JSON = Path.home() / "projetos" / "arcturus_coleta" / "data" / "clima_consolidado.json"

def get_clima_consolidado():
    if CLIMA_JSON.exists():
        return json.loads(CLIMA_JSON.read_text())
    return None

from dashboard_correcoes import get_chuva_48h, get_status_unificado, get_selo_confianca, get_cota_v11c
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
    health_status, cor, score = get_status_unificado()
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
            health_status, cor, score = get_status_unificado()
            health_color = "text-success"
        else:
            health_status, cor, score = get_status_unificado()
            health_color = "text-warning"
    except Exception:
        pass

    if FILE_REGIME.exists():
        try:
            with open(FILE_REGIME, "r") as f:
                reg = json.load(f)
                status, cor, score = get_status_unificado()
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
    candidatos = (
        FILE_IMPACT_2019,
        BASE / "resultados" / "atlas_impacto_2019.json.bak",
    )
    arquivo_impacto = next((path for path in candidatos if path.is_file()), FILE_IMPACT_2019)
    try:
        with arquivo_impacto.open("r", encoding="utf-8") as arquivo:
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

def gerar_grafico_cota(escala_modo="local"):
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
                    LIMIT 120
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

        cota_min = float(df["cota_cm"].min())
        cota_max = float(df["cota_cm"].max())
        if escala_modo == "completa":
            y_min, y_max = 0.0, 1000.0
        else:
            folga = max(12.0, (cota_max - cota_min) * 0.25)
            y_min = max(0.0, cota_min - folga)
            y_max = cota_max + folga

        # === FAIXAS DE FUNDO (cores da Defesa Civil) ===
        zonas = [
            (0, 50, "rgba(0, 119, 255, 0.15)", "Baixo (<0,5m)"),
            (50, 250, "rgba(0, 200, 0, 0.15)", "Normal (0,5-2,5m)"),
            (250, 350, "rgba(255, 200, 0, 0.20)", "Atenção (2,5-3,5m)"),
            (350, 600, "rgba(255, 120, 0, 0.20)", "Alerta (3,5-6,0m)"),
            (600, 1000, "rgba(255, 0, 0, 0.20)", "Emergência (>6,0m)"),
        ]
        for y0, y1, cor, nome in zonas:
            if y1 < y_min or y0 > y_max:
                continue
            y0_vis = max(y0, y_min)
            y1_vis = min(y1, y_max)
            fig.add_shape(
                type="rect",
                x0=df["timestamp"].min(),
                x1=agora + timedelta(minutes=10),
                y0=y0_vis,
                y1=y1_vis,
                line=dict(width=0),
                fillcolor=cor,
                layer="below",
            )
            fig.add_annotation(
                xref="paper",
                x=1.01,
                y=(y0_vis + y1_vis) / 2,
                text=nome,
                showarrow=False,
                xanchor="left",
                font=dict(size=10, color="rgba(255,255,255,0.75)"),
            )

        def cor_por_cota(cota):
            if cota < 50:
                return "#0077FF"
            elif cota < 250:
                return "#00C800"
            elif cota < 350:
                return "#FFC800"
            elif cota < 600:
                return "#FF7800"
            else:
                return "#FF0000"

        cores = [cor_por_cota(c) for c in df["cota_cm"]]
        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df["cota_cm"],
            mode="lines+markers",
            name="Cota (cm)",
            line=dict(color="#38bdf8", width=2.2),
            marker=dict(size=7, color=cores, line=dict(width=1, color="white")),
            hovertemplate="<b>%{x|%d/%m/%Y %H:%M}</b><br>Cota: %{y:.1f} cm<extra></extra>",
        ))

        fig.add_shape(
            type="line",
            x0=agora,
            x1=agora,
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color="#ff6b6b", width=2, dash="dot"),
        )
        fig.add_annotation(
            x=agora,
            y=1,
            yref="paper",
            text=f"Agora: {agora.strftime('%H:%M:%S')}",
            showarrow=False,
            xanchor="right",
            yanchor="bottom",
            font=dict(size=10, color="#ff6b6b"),
        )

        titulo_escala = "Escala Local (Zoom)" if escala_modo != "completa" else "Escala Completa (0–1000 cm)"
        fig.update_layout(
            title=f"Cota do Rio Tubarão (Tempo Real) — {titulo_escala}",
            xaxis_title="Data / Hora",
            yaxis_title="Cota (cm)",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=50, r=130, t=60, b=45),
            yaxis=dict(range=[y_min, y_max]),
            xaxis=dict(
                range=[df["timestamp"].min(), agora + timedelta(minutes=10)],
                tickformat="%d/%m<br>%H:%M",
                tickangle=-45,
                tickfont=dict(size=9),
            ),
        )
        return fig
    except Exception as e:
        logging.exception("Não foi possível carregar as leituras do PostgreSQL para o gráfico.")
        fig = go.Figure()
        fig.add_annotation(text=f"Erro PostgreSQL: {e}", showarrow=False, font=dict(color="red"))
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
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

# MAPA DE PREVISÃO DO TEMPO (Plotly Scattermap) — CORRIGIDO
def get_mapa_clima():
    """Lê o clima_consolidado.json e monta o mapa com a data de hoje."""
    import json
    from pathlib import Path
    import plotly.graph_objects as go
    from datetime import datetime

    CLIMA_JSON = Path.home() / "projetos" / "arcturus_coleta" / "data" / "clima_consolidado.json"

    if not CLIMA_JSON.exists():
        return go.Figure().update_layout(
            title="Clima consolidado não disponível",
            height=400,
        )

    clima = json.loads(CLIMA_JSON.read_text())
    dias = clima.get("dias", [])
    data_consulta = clima.get("data_consulta", datetime.now().strftime("%Y-%m-%d"))

    # Prepara os dados para o mapa
    # Usa as coordenadas do JSON (ou as padrão da bacia)
    lat = clima.get("lat", -28.5)
    lon = clima.get("lon", -49.0)

    # Cria uma lista de pontos com a chuva média
    lats = []
    lons = []
    textos = []
    cores = []

    for i, dia in enumerate(dias[:7]):  # 7 dias
        # Espalha os pontos ao redor do centro da bacia (simulação de grid)
        # Para um mapa real, use as coordenadas das cidades.
        lat_offset = lat + (i % 3 - 1) * 0.1
        lon_offset = lon + (i // 3 - 1) * 0.1
        lats.append(lat_offset)
        lons.append(lon_offset)
        chuva = dia.get("media_mm", 0)
        data = dia.get("date", "N/A")
        cor = "green" if chuva < 5 else ("yellow" if chuva < 20 else "red")
        cores.append(cor)
        textos.append(f"{data}: {chuva:.1f} mm (média de 3 fontes)")

    fig = go.Figure(go.Scattermap(
        lat=lats,
        lon=lons,
        mode="markers",
        marker=dict(size=20, color=cores),
        text=textos,
        hoverinfo="text",
    ))

    fig.update_layout(
        title=f"Previsão do Tempo — Bacia do Rio Tubarão (Data: {data_consulta})",
        map=dict(
            style="open-street-map",
            center=dict(lat=lat, lon=lon),
            zoom=8,
        ),
        height=500,
        margin=dict(l=0, r=0, t=40, b=0),
    )

    return fig

def ler_previsao_v11c():
    """Lê a última previsão do v11c (modo sombra) do log."""
    import pandas as pd
    from pathlib import Path
    log_path = Path.home() / "projetos" / "arcturus_coleta" / "data" / "log_previsoes_sombra.csv"
    if not log_path.exists():
        return None
    try:
        df = pd.read_csv(log_path)
        if len(df) == 0:
            return None
        ultima = df.iloc[-1]
        return {
            "data_previsao": ultima.get("data_previsao", ""),
            "cota_hoje": float(ultima.get("cota_hoje_cm", 0)),
            "delta": float(ultima.get("delta_previsto_cm", 0)),
            "cota_amanha": float(ultima.get("cota_prevista_amanha_cm", 0)),
        }
    except Exception as e:
        print(f"[AVISO] Erro ao ler log do v11c: {e}")
        return None

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
    dcc.Interval(
        id='intervalo-atualizacao',
        interval=30*1000, # Atualiza a cada 30 segundos
        n_intervals=0
    ),
    dbc.Row([
        dbc.Col([
            # === SPRINT 1: BARRA EXECUTIVA DE KPIs OPERACIONAIS (3 SEGUNDOS) ===
            dbc.Row([
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.Small("🌊 COTA ATUAL (ERAB)", className="text-muted fw-bold d-block"),
                    html.H3(id="kpi-cota-val", children="-- cm", className="text-info mb-0 mt-1"),
                    html.Small(id="kpi-cota-sub", children="Δ 24h: --", className="text-light"),
                ]), className="border-info bg-dark shadow-sm h-100"), xs=12, md=2),

                dbc.Col(dbc.Card(dbc.CardBody([
                    html.Small("📈 TENDÊNCIA / VELOCIDADE", className="text-muted fw-bold d-block"),
                    html.H5(id="kpi-tend-val", children="--", className="mb-1 mt-2 fw-bold"),
                    html.Small(id="kpi-tend-sub", children="az: --", className="text-muted"),
                ]), className="border-secondary bg-dark shadow-sm h-100"), xs=12, md=3),

                dbc.Col(dbc.Card(dbc.CardBody([
                    html.Small("🌧️ CHUVA MÁX (24H)", className="text-muted fw-bold d-block"),
                    html.H3(id="kpi-chuva-val", children="-- mm", className="text-primary mb-0 mt-1"),
                    html.Small(id="kpi-chuva-sub", children="Estação: --", className="text-light"),
                ]), className="border-primary bg-dark shadow-sm h-100"), xs=12, md=3),

                dbc.Col(dbc.Card(dbc.CardBody([
                    html.Small("🚦 ESTADO OPERACIONAL", className="text-muted fw-bold d-block"),
                    html.H3(id="kpi-estado-val", children="--", className="mb-0 mt-1 fw-bold"),
                    html.Small(id="kpi-estado-sub", children="DCSC: --", className="text-light"),
                ]), className="border-warning bg-dark shadow-sm h-100"), xs=12, md=2),

                dbc.Col(dbc.Card(dbc.CardBody([
                    html.Small("🕒 ÚLTIMA LEITURA", className="text-muted fw-bold d-block"),
                    html.H4(id="kpi-ts-val", children="--", className="text-white mb-0 mt-1"),
                    html.Small("Ciclo automático 15m", className="text-muted"),
                ]), className="border-secondary bg-dark shadow-sm h-100"), xs=12, md=2),
            ], className="g-2 mb-3 mt-2"),
            dcc.Store(id="store-escala-cota", data="local"),
            html.Hr(),
            dbc.Row([
                dbc.Col(criar_card("Cota Atual (ERAB)", "cota-val", "cota-sub"), width=3),
                dbc.Col(criar_card("Previsão v11c (D+1)", "v11c-cota-amanha", "v11c-delta"), width=3),
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
        dbc.Col(dcc.Graph(id="mapa-previsao-tempo", figure=get_mapa_clima()), width=12),
    ]),
    html.Hr(),
dbc.Row([
                dbc.Col([
                    dbc.ButtonGroup([
                        dbc.Button("🔍 Escala Local (Zoom)", id="btn-escala-local", color="info", size="sm"),
                        dbc.Button("🌐 Escala Completa (0–1000 cm)", id="btn-escala-completa", color="outline-secondary", size="sm"),
                    ], className="mb-2"),
                    dcc.Graph(id="grafico-cota", figure=gerar_grafico_cota("local")),
                ], width=12),
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
        ], width=12, style={"padding": "20px"})
    ], className="g-0"),
    ], style={"marginLeft": "250px"}),
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
        score_status, cor, score = get_status_unificado()
    elif score >= 50:
        score_color = "text-warning"
        score_status, cor, score = get_status_unificado()
    elif score >= 25:
        score_color = "text-warning"
        score_status, cor, score = get_status_unificado()
    else:
        score_color = "text-danger"
        score_status, cor, score = get_status_unificado()

    return cota_val, cota_sub, chuva_val, chuva_sub, prob_val, prob_sub, regime_val, regime_class, regime_sub, msg, fig, health_status, health_status, health_color, score_status, score_status, score_color, ler_ultimo_alerta()




@app.callback(
    Output("v11c-cota-amanha", "children"),
    Output("v11c-delta", "children"),
    Input("intervalo-atualizacao", "n_intervals"),
)
def update_v11c_card(n):
    prev = ler_previsao_v11c()
    if prev is None:
        return "-- cm", "Sem previsão"
    cota_amanha = prev["cota_amanha"]
    delta = prev["delta"]
    # SEMPRE 🟡 SOMBRA (não é confiança ALTA)
    return f"{cota_amanha:.1f} cm 🟡", f"SOMBRA | Delta: {delta:+.1f} cm (MAE ±22 cm)"


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


@app.callback(
    [Output("store-escala-cota", "data"),
     Output("btn-escala-local", "color"),
     Output("btn-escala-completa", "color")],
    [Input("btn-escala-local", "n_clicks"),
     Input("btn-escala-completa", "n_clicks")],
    prevent_initial_call=True,
)
def alternar_escala_cota(n_local, n_comp):
    ctx = dash.callback_context
    if not ctx.triggered:
        return "local", "info", "outline-secondary"
    btn_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if btn_id == "btn-escala-completa":
        return "completa", "outline-info", "secondary"
    return "local", "info", "outline-secondary"


@app.callback(
    [Output("kpi-cota-val", "children"),
     Output("kpi-cota-sub", "children"),
     Output("kpi-tend-val", "children"),
     Output("kpi-tend-val", "style"),
     Output("kpi-tend-sub", "children"),
     Output("kpi-chuva-val", "children"),
     Output("kpi-chuva-sub", "children"),
     Output("kpi-estado-val", "children"),
     Output("kpi-estado-val", "style"),
     Output("kpi-estado-sub", "children"),
     Output("kpi-ts-val", "children"),
     Output("grafico-cota", "figure", allow_duplicate=True)],
    [Input("btn-atualizar", "n_clicks"),
     Input("intervalo-atualizacao", "n_intervals"),
     Input("store-escala-cota", "data")],
    prevent_initial_call="initial_duplicate",
)
def atualizar_kpis_e_zoom(n_clicks, n_intervals, escala_modo):
    k = obter_kpis_operacionais()
    cota_txt = f"{k['cota_cm']:.1f} cm" if k["cota_cm"] is not None else "-- cm"
    delta_txt = f"Δ 24h: {k['delta_24h_cm']:+.1f} cm" if k["delta_24h_cm"] is not None else "Δ 24h: --"
    tend_txt = k["tendencia_label"]
    tend_style = {"color": k["tendencia_cor"]}
    az_txt = f"Aceleração az: {k['az_cm_h2']:+.2f} cm/h²"
    chuva_txt = f"{k['chuva_max_24h_mm']:.1f} mm"
    est_txt = f"{k['estacao_dominante']} (6h: {k['chuva_6h_mm']:.1f} mm)"
    estado_txt = k["estado_operacional"]
    estado_style = {"color": k["estado_cor"]}
    idade = f"{k['dcsc_idade_min']} min" if k["dcsc_idade_min"] is not None else "N/D"
    dcsc_txt = f"DCSC {k['dcsc_validas']} • {idade}"
    ts_txt = k["ts_leitura"]
    fig = gerar_grafico_cota(escala_modo or "local")
    return (
        cota_txt, delta_txt,
        tend_txt, tend_style, az_txt,
        chuva_txt, est_txt,
        estado_txt, estado_style, dcsc_txt,
        ts_txt, fig
    )
