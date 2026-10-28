import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.relatorios.monitor_continuo import salvar_no_historico
from playwright.sync_api import sync_playwright
import json
import math
from datetime import datetime

def coletar_cota():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Abrindo Tubarão Saneamento...")
        page.goto("https://tubaraosaneamento.com.br/nivelriotubarao_termometro/get_historico", timeout=60000)
        
        print("Aguardando carregamento do gráfico...")
        page.wait_for_timeout(5000)
        
        # A MÁGICA: Pegar o elemento pela classe exata
        elemento = page.query_selector(".chartjs-value")
        
        if elemento:
            texto = elemento.inner_text().strip()
            try:
                cota_metros = float(texto.replace(",", "."))
                cota_cm = cota_metros * 100
                if not math.isfinite(cota_cm) or cota_cm <= 0:
                    raise ValueError("cota fora do domínio numérico válido")
                resultado = {
                    "fonte": "Tubarão Saneamento (ERAB)",
                    "cota_metros": cota_metros,
                    "cota_cm": cota_cm,
                    "data_extracao": datetime.now().isoformat(),
                    "qc": "VALIDO",
                }
                with open("tubarao_saneamento_dados.json", "w", encoding="utf-8") as f:
                    json.dump(resultado, f, indent=2)

                qc = salvar_no_historico(resultado)
                resultado["qc"] = qc
                with open("tubarao_saneamento_dados.json", "w", encoding="utf-8") as f:
                    json.dump(resultado, f, indent=2)
                print(
                    f"✅ Cota extraída: {cota_metros:.2f} metros "
                    f"({cota_cm:.0f} cm; QC={qc})"
                )
                print("Salvo em tubarao_saneamento_dados.json")
            except (TypeError, ValueError):
                resultado = {
                    "fonte": "Tubarão Saneamento (ERAB)",
                    "cota_metros": None,
                    "cota_cm": None,
                    "data_extracao": datetime.now().isoformat(),
                    "qc": "CORROMPIDO",
                }
                salvar_no_historico(resultado)
                print("⚠️ Valor extraído inválido; leitura registrada como CORROMPIDO.")
        else:
            print("⚠️ Elemento .chartjs-value não encontrado. O site pode ter mudado.")
        
        browser.close()

if __name__ == "__main__":
    coletar_cota()
