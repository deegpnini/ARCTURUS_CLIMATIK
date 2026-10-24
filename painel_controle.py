import streamlit as st
import subprocess
from pathlib import Path
from datetime import datetime
import json
import os
import pandas as pd
import re
import time

BASE = Path(__file__).resolve().parent
LOG_FILE = BASE / "monitor_ciclone.log"
JSON_COTA = BASE / "tubarao_saneamento_dados.json"
PREV_CHUVA = BASE / "data" / "previsao_chuva_bacia.csv"
PROB_FILE = BASE / "data" / "probabilidade_cheia.json"
REGIME_FILE = BASE / "data" / "regime_atual.json"

st.set_page_config(page_title="ARCTURUS CLIMATIK", page_icon="🌊", layout="wide")

def monitor_ativo():
    result = subprocess.run(["pgrep", "-f", "monitor_continuo.py"], capture_output=True, text=True)
    return result.returncode == 0

def carregar_cota():
    if JSON_COTA.exists():
        with open(JSON_COTA, "r") as f:
            return json.load(f)
    return {}

def carregar_chuva_48h():
    if PREV_CHUVA.exists():
        try:
            prev = pd.read_csv(PREV_CHUVA, index_col=0, parse_dates=True)
            col = "chuva_prevista_mm" if "chuva_prevista_mm" in prev.columns else prev.columns[0]
            return float(prev[col].iloc[:48].sum())
        except Exception:
            return None
    return None

def carregar_probabilidade():
    if PROB_FILE.exists():
        with open(PROB_FILE, "r") as f:
            return float(json.load(f).get("probabilidade", 0.0))
    return 0.0

def carregar_regime():
    if REGIME_FILE.exists():
        with open(REGIME_FILE, "r") as f:
            return json.load(f)
    return {"regime": "NORMAL", "delta_60m": 0.0, "motivo": ""}

def cor_probabilidade(prob):
    if prob < 1:
        return "normal"
    elif prob < 10:
        return "atencao"
    return "alerta"

def atualizar_tudo():
    resultados = []
    script_cota = BASE / "src" / "relatorios" / "coletar_tubarao_saneamento.py"
    if script_cota.exists():
        r = subprocess.run(["python", str(script_cota)], capture_output=True, text=True)
        resultados.append(("Cota", r.returncode == 0, r.stdout + r.stderr))
    else:
        resultados.append(("Cota", False, "Script não encontrado"))

    script_chuva = BASE / "src" / "relatorios" / "alerta_chuva.py"
    if script_chuva.exists():
        r = subprocess.run(["python", str(script_chuva)], capture_output=True, text=True)
        resultados.append(("Chuva", r.returncode == 0, r.stdout + r.stderr))
    else:
        resultados.append(("Chuva", False, "Script não encontrado"))

    script_class = BASE / "src" / "modelo" / "simular_previsao_chuva.py"
    if script_class.exists():
        r = subprocess.run(["python", str(script_class)], capture_output=True, text=True)
        match = re.search(r"Probabilidade de cheia.*?: ([\d.]+)%", r.stdout, re.IGNORECASE)
        if match:
            prob_nova = float(match.group(1))
            PROB_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(PROB_FILE, "w") as f:
                json.dump({"probabilidade": prob_nova, "atualizado": datetime.now().isoformat()}, f)
        resultados.append(("Classificador", r.returncode == 0, r.stdout + r.stderr))
    else:
        resultados.append(("Classificador", False, "Script não encontrado"))

    script_regime = BASE / "src" / "modelo" / "detector_regime.py"
    if script_regime.exists():
        r = subprocess.run(["python", str(script_regime)], capture_output=True, text=True)
        resultados.append(("Detector de Regime", r.returncode == 0, r.stdout + r.stderr))
    else:
        resultados.append(("Detector de Regime", False, "Script não encontrado"))

    return resultados

if monitor_ativo():
    try:
        st.autorefresh(interval=5 * 60 * 1000, key="auto_refresh_monitor")
    except Exception:
        pass

with st.sidebar:
    if os.path.exists("logo_arcturus.jpg"):
        st.image("logo_arcturus.jpg", use_container_width=True)
    else:
        st.markdown("### 🌊 ARCTURUS")
    st.markdown("---")
    st.subheader("Status do Sistema")
    dados_side = carregar_cota()
    if dados_side:
        st.metric("Cota Atual (ERAB)", f"{dados_side.get('cota_cm', 0):.0f} cm")
        extracao = str(dados_side.get("data_extracao", ""))[:16]
        st.caption(f"Extraído: {extracao}")
    else:
        st.warning("Cota indisponível")
    st.markdown("---")
    if monitor_ativo():
        st.success("🟢 Monitor em background")
    else:
        st.warning("🔴 Monitor parado")
    st.markdown("---")
    st.caption("ARCTURUS CLIMATIK — NEXUS OIKOS")

dados = carregar_cota()
cota = dados.get("cota_cm", None)
chuva_48h = carregar_chuva_48h()
prob = carregar_probabilidade()
regime_data = carregar_regime()
regime = regime_data.get("regime", "NORMAL")
delta = float(regime_data.get("delta_60m", 0.0))
motivo_regime = regime_data.get("motivo", "")

if regime == "EXTREMO" or prob >= 10:
    st.error("🚨 **REGIME EXTREMO / ALERTA ATIVO** — Atenção redobrada necessária", icon="🚨")
elif prob >= 1 or delta >= 15:
    st.warning("⚠️ **ATENÇÃO** — Aceleração ou probabilidade elevada detectada", icon="⚠️")
else:
    st.success("✅ **SISTEMA EM MODO NORMAL** — Sem sinais de risco elevado no momento", icon="✅")

st.title("🌊 ARCTURUS CLIMATIK — Painel de Controle")
st.markdown("**Sistema de Alerta Hidrológico — Bacia do Tubarão**")
st.markdown("---")

c1, c2, c3, c4 = st.columns(4)
with c1:
    if cota is not None:
        st.metric("Cota Atual (ERAB)", f"{cota:.0f} cm")
    else:
        st.metric("Cota Atual (ERAB)", "N/A")
with c2:
    if chuva_48h is not None:
        st.metric("Chuva Prevista (48h)", f"{chuva_48h:.1f} mm")
    else:
        st.metric("Chuva Prevista (48h)", "N/A")
with c3:
    nivel = cor_probabilidade(prob)
    if nivel == "normal":
        st.success(f"**Prob. de Cheia**\n\n{prob:.2f}% ✅ Seguro")
    elif nivel == "atencao":
        st.warning(f"**Prob. de Cheia**\n\n{prob:.2f}% ⚠️ Atenção")
    else:
        st.error(f"**Prob. de Cheia**\n\n{prob:.2f}% 🚨 Alerta")
with c4:
    if regime == "EXTREMO":
        st.error(f"**Regime**\n\n🚨 EXTREMO\nΔ60m: {delta:+.1f} cm/h")
    else:
        st.info(f"**Regime**\n\n🟢 NORMAL\nΔ60m: {delta:+.1f} cm/h")
    if motivo_regime:
        st.caption(motivo_regime)

st.markdown("---")

col_atualiza, col_info = st.columns([1, 3])
with col_atualiza:
    if st.button("🔄 Atualizar Tudo", use_container_width=True, type="primary"):
        with st.spinner("Atualizando cota → chuva → classificador → regime..."):
            resultados = atualizar_tudo()
        sucessos = sum(1 for _, ok, _ in resultados if ok)
        total = len(resultados)
        if sucessos == total:
            st.success(f"✅ Tudo atualizado com sucesso ({sucessos}/{total})")
        else:
            st.warning(f"⚠️ Atualizado parcialmente ({sucessos}/{total})")
        with st.expander("Detalhes da atualização"):
            for nome, ok, saida in resultados:
                if ok:
                    st.markdown(f"**{nome}:** ✅ OK")
                else:
                    st.markdown(f"**{nome}:** ❌ Falhou")
                    if saida and saida.strip():
                        st.code(saida[-600:])
        time.sleep(0.8)
        st.rerun()
with col_info:
    st.caption("Roda em sequência: Cota → Chuva → Classificador de Cheia → Detector de Regime")

st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    st.subheader("📊 1. Coleta de Dados")
    if st.button("🚀 Coletar Cota (Tubarão Saneamento)", use_container_width=True, type="primary"):
        with st.spinner("Coletando cota..."):
            result = subprocess.run(["python", str(BASE / "src" / "relatorios" / "coletar_tubarao_saneamento.py")], capture_output=True, text=True)
            if result.returncode == 0:
                st.success("✅ Cota coletada!")
                st.rerun()
            else:
                st.error("❌ Erro na coleta.")
                st.code(result.stderr or result.stdout)
    if st.button("🛰️ Coletar Chuva (NASA POWER / Open-Meteo)", use_container_width=True):
        with st.spinner("Consultando previsão de chuva..."):
            script = BASE / "src" / "relatorios" / "alerta_chuva.py"
            if script.exists():
                result = subprocess.run(["python", str(script)], capture_output=True, text=True)
                st.text(result.stdout)
            else:
                st.warning("Script de chuva não encontrado.")

with col2:
    st.subheader("🤖 2. Previsão e Alerta")
    if st.button("🔮 Rodar Classificador de Cheia", use_container_width=True, type="primary"):
        with st.spinner("Simulando probabilidade..."):
            script = BASE / "src" / "modelo" / "simular_previsao_chuva.py"
            if script.exists():
                result = subprocess.run(["python", str(script)], capture_output=True, text=True)
                st.text(result.stdout)
                match = re.search(r"Probabilidade de cheia.*?: ([\d.]+)%", result.stdout, re.IGNORECASE)
                if match:
                    prob_nova = float(match.group(1))
                    PROB_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with open(PROB_FILE, "w") as f:
                        json.dump({"probabilidade": prob_nova, "atualizado": datetime.now().isoformat()}, f)
                    st.success(f"Probabilidade atualizada: {prob_nova:.2f}%")
                    st.rerun()
            else:
                st.warning("Script do classificador não encontrado.")
    if st.button("🚨 Verificar Alerta Crítico / Regime", use_container_width=True):
        with st.spinner("Verificando limiares e regime..."):
            detector = BASE / "src" / "modelo" / "detector_regime.py"
            if detector.exists():
                result = subprocess.run(["python", str(detector)], capture_output=True, text=True)
                st.text(result.stdout)
            alerta = BASE / "src" / "relatorios" / "alerta_critico.py"
            if alerta.exists():
                result = subprocess.run(["python", str(alerta)], capture_output=True, text=True)
                st.text(result.stdout)

st.markdown("---")

col3, col4 = st.columns(2)
with col3:
    st.subheader("🗺️ 3. Gêmeo Digital (GEE)")
    if st.button("📄 Gerar Relatório de Risco", use_container_width=True):
        with st.spinner("Gerando relatório..."):
            script = BASE / "relatorio_risco.py"
            if script.exists():
                result = subprocess.run(["python", str(script)], capture_output=True, text=True)
                relatorio_path = BASE / "docs" / "RELATORIO_RISCO.md"
                if relatorio_path.exists():
                    st.markdown("### Relatório Gerado:")
                    st.markdown(relatorio_path.read_text())
                else:
                    st.text(result.stdout)
            else:
                st.warning("Script de relatório não encontrado.")
    if st.button("🌍 Abrir Mapa no Google Earth", use_container_width=True):
        try:
            subprocess.run(["/mnt/c/Program Files/Google/Google Earth Pro/client/googleearth.exe", r"C:\Users\Administrador\Desktop\mancha_inundacao.kml"])
            st.success("Google Earth aberto no Windows.")
        except Exception as e:
            st.error(f"Não foi possível abrir o Google Earth: {e}")

with col4:
    st.subheader("🔁 4. Monitoramento Contínuo")
    if monitor_ativo():
        if st.button("🛑 PARAR Monitor", type="primary", use_container_width=True):
            subprocess.run("pkill -f monitor_continuo.py", shell=True)
            st.success("Monitor interrompido.")
            time.sleep(0.5)
            st.rerun()
    else:
        if st.button("▶️ INICIAR Monitor (30 min)", type="primary", use_container_width=True):
            cmd = f"nohup python {BASE / 'src' / 'relatorios' / 'monitor_continuo.py'} > {LOG_FILE} 2>&1 &"
            subprocess.Popen(cmd, shell=True)
            st.success("Monitor iniciado em background.")
            time.sleep(0.5)
            st.rerun()
    if st.button("📊 Ver Histórico (CSV)", use_container_width=True):
        csv_path = BASE / "resultados" / "historico_previsoes.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            st.dataframe(df.tail(15), use_container_width=True)
        else:
            st.info("Histórico ainda vazio.")
    if LOG_FILE.exists():
        with st.expander("📝 Ver Log do Monitor (últimas linhas)"):
            linhas = LOG_FILE.read_text().split("\n")
            st.code("\n".join(linhas[-25:]))

st.markdown("---")
st.caption(f"ARCTURUS CLIMATIK — NEXUS OIKOS | Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
