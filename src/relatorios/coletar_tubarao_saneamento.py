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
        try:
            page.goto("https://tubaraosaneamento.com.br/nivelriotubarao_termometro/get_historico", timeout=60000)
            page.wait_for_timeout(5000)
        except Exception as e:
            print(f"⚠️ Erro ao carregar a página: {e}")
            browser.close()
            return

        # Pega TODOS os elementos com a classe do gráfico
        elementos = page.query_selector_all(".chartjs-value")
        
        cota_metros = None
        
        if elementos:
            # Tenta ler todos os valores e escolher o mais plausível (0.1 a 6.0 metros)
            valores = []
            for el in elementos:
                try:
                    texto = el.inner_text().strip().replace(",", ".")
                    v = float(texto)
                    if 0.1 <= v <= 6.0: # Rio Tubarão não passa de 6 metros
                        valores.append(v)
                except (ValueError, TypeError):
                    continue
            
            if valores:
                # Pega o menor valor (o nível do rio, não o topo da régua)
                cota_metros = valores[-1]  # Pega o último valor (o mais recente)
                
                resultado = {
                    "fonte": "Tubarão Saneamento (ERAB)",
                    "cota_metros": cota_metros,
                    "cota_cm": cota_metros * 100,
                    "data_extracao": datetime.now().isoformat(),
                    "qc": "VALIDO",
                }
                
                # Chama o monitor para checar a regra de salto (SUSPEITO)
                qc = salvar_no_historico(resultado)
                resultado["qc"] = qc
                
                with open("tubarao_saneamento_dados.json", "w", encoding="utf-8") as f:
                    json.dump(resultado, f, indent=2)
                    
                print(f"✅ Cota extraída: {cota_metros:.2f} metros ({cota_metros*100:.0f} cm; QC={qc})")
            else:
                print("⚠️ Nenhum valor numérico plausível encontrado na página.")
                resultado = {"fonte": "ERAB", "cota_metros": None, "cota_cm": None, "data_extracao": datetime.now().isoformat(), "qc": "CORROMPIDO"}
                salvar_no_historico(resultado)
        else:
            print("⚠️ Elemento .chartjs-value não encontrado. O site pode ter mudado.")

        browser.close()

if __name__ == "__main__":
    coletar_cota()
