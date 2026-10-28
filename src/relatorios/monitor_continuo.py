import time
import subprocess
import math
from pathlib import Path
from datetime import datetime
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
INTERVALO_MIN = 30
HISTORICO = BASE / "resultados" / "historico_previsoes.csv"

def determinar_qc(cota, cota_anterior=None, qc_existente=None):
    status = str(qc_existente or "").strip().upper()
    if status in {"MANUAL", "CORROMPIDO", "SUSPEITO"}:
        return status

    try:
        valor = float(cota)
    except (TypeError, ValueError):
        return "CORROMPIDO"
    if not math.isfinite(valor) or valor <= 0:
        return "CORROMPIDO"

    if cota_anterior is not None:
        try:
            anterior = float(cota_anterior)
        except (TypeError, ValueError):
            anterior = None
        if (
            anterior is not None
            and math.isfinite(anterior)
            and abs(valor - anterior) > 30
        ):
            return "SUSPEITO"
    return "VALIDO"


def salvar_no_historico(dados_override=None):
    """Lê a cota atual do JSON e salva no histórico."""
    import json
    json_path = BASE / "tubarao_saneamento_dados.json"
    if dados_override is None:
        if not json_path.exists():
            return None
        with json_path.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    else:
        dados = dados_override

    cota = dados.get("cota_cm")
    cota_anterior = None
    if HISTORICO.exists():
        historico = pd.read_csv(HISTORICO)
        if "cota_atual_cm" in historico.columns:
            cotas = pd.to_numeric(historico["cota_atual_cm"], errors="coerce").dropna()
            if not cotas.empty:
                cota_anterior = cotas.iloc[-1]
    qc = determinar_qc(cota, cota_anterior, dados.get("qc"))
    timestamp = datetime.now().isoformat()

    linha = {
        "timestamp_execucao": timestamp,
        "cota_atual_cm": cota,
        "cota_1h_cm": None,
        "delta_1h_cm": None,
        "cota_3h_cm": None,
        "delta_3h_cm": None,
        "cota_6h_cm": None,
        "delta_6h_cm": None,
        "qc": qc,
    }

    df_novo = pd.DataFrame([linha])
    if HISTORICO.exists():
        df_novo.to_csv(HISTORICO, mode="a", header=False, index=False)
    else:
        df_novo.to_csv(HISTORICO, index=False)
    if qc == "CORROMPIDO":
        print(f"⚠️ Leitura salva no histórico com QC={qc}.")
    else:
        print(f"✅ Cota salva no histórico: {float(cota):.0f} cm (QC={qc})")
    return qc

def rodar_ciclo():
    print(f"\n{'='*50}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Novo ciclo...")

    # 1. Coletar a cota da Tubarão Saneamento
    print("1. Coletando cota da Tubarão Saneamento...")
    subprocess.run(["python", str(BASE / "src" / "relatorios" / "coletar_tubarao_saneamento.py")], cwd=str(BASE))
    
    # Salvar no histórico
    salvar_no_historico()

    # 2. Rodar o modelo operacional
    print("2. Rodando o modelo operacional...")
    subprocess.run(["python", str(BASE / "src" / "relatorios" / "insight_operacional.py")], cwd=str(BASE))

    # 3. Calcular a derivada (Vz)
    print("3. Calculando derivada da cota (Vz)...")
    try:
        subprocess.run(["python3", str(BASE / "src" / "relatorios" / "monitor_derivada.py")], check=True)
        print("✅ Derivada calculada e regime atualizado.")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Falha ao executar o monitor de derivada: {e}")

if __name__ == "__main__":
    print(f"=== MONITOR CONTÍNUO ARCTURUS (intervalo: {INTERVALO_MIN} min) ===")
    print("Pressione Ctrl+C para parar.\n")

    while True:
        try:
            rodar_ciclo()
            print(f"\nAguardando {INTERVALO_MIN} minutos...")
            time.sleep(INTERVALO_MIN * 60)
        except KeyboardInterrupt:
            print("\n\nMonitor interrompido pelo Comandante.")
            break
