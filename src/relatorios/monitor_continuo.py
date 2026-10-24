import time
import subprocess
from pathlib import Path
from datetime import datetime
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
INTERVALO_MIN = 30
HISTORICO = BASE / "resultados" / "historico_previsoes.csv"

def salvar_no_historico():
    """Lê a cota atual do JSON e salva no histórico."""
    import json
    json_path = BASE / "tubarao_saneamento_dados.json"
    if not json_path.exists():
        return
    
    with open(json_path, "r") as f:
        dados = json.load(f)
    
    cota = dados.get("cota_cm", 0)
    timestamp = datetime.now().isoformat()
    
    # Criar a linha
    linha = {
        "timestamp_execucao": timestamp,
        "cota_atual_cm": cota,
        "cota_1h_cm": None,
        "delta_1h_cm": None,
        "cota_3h_cm": None,
        "delta_3h_cm": None,
        "cota_6h_cm": None,
        "delta_6h_cm": None,
    }
    
    # Salvar no CSV (append)
    df_novo = pd.DataFrame([linha])
    if HISTORICO.exists():
        df_novo.to_csv(HISTORICO, mode='a', header=False, index=False)
    else:
        df_novo.to_csv(HISTORICO, index=False)
    print(f"✅ Cota salva no histórico: {cota:.0f} cm")

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
