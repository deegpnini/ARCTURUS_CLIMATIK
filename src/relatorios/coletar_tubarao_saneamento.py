from playwright.sync_api import sync_playwright
import json
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
            # Converter a vírgula para ponto, se necessário
            cota_metros = float(texto.replace(",", "."))
            cota_cm = cota_metros * 100
            
            print(f"✅ Cota extraída: {cota_metros:.2f} metros ({cota_cm:.0f} cm)")
            
            resultado = {
                "fonte": "Tubarão Saneamento (ERAB)",
                "cota_metros": cota_metros,
                "cota_cm": cota_cm,
                "data_extracao": datetime.now().isoformat()
            }
            
            with open("tubarao_saneamento_dados.json", "w") as f:
                json.dump(resultado, f, indent=2)
            print("Salvo em tubarao_saneamento_dados.json")
        else:
            print("⚠️ Elemento .chartjs-value não encontrado. O site pode ter mudado.")
        
        browser.close()

if __name__ == "__main__":
    coletar_cota()
