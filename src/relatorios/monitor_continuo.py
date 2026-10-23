import time
import subprocess
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[2]
INTERVALO_MIN = 30

def rodar_ciclo():
    print(f"\n{'='*50}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Novo ciclo...")
    
    # 1. Coletar a cota da Tubarão Saneamento
    print("1. Coletando cota da Tubarão Saneamento...")
    subprocess.run(["python", str(BASE / "src" / "relatorios" / "coletar_tubarao_saneamento.py")], cwd=str(BASE))
    
    # 2. Rodar o modelo operacional
    print("2. Rodando o modelo operacional...")
    subprocess.run(["python", str(BASE / "src" / "relatorios" / "insight_operacional.py")], cwd=str(BASE))

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
