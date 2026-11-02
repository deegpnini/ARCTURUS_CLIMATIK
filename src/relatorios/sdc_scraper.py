from playwright.sync_api import sync_playwright
import json

def raspar_sdc():
    with sync_playwright() as p:
        # Usar um navegador real (não headless) para o WebGL funcionar
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Interceptar respostas JSON
        captured_data = []
        def on_response(response):
            if "json" in response.headers.get("content-type", ""):
                try:
                    data = response.json()
                    captured_data.append(data)
                except:
                    pass
        
        page.on("response", on_response)
        
        print("Abrindo SDC...")
        page.goto("https://monitoramento.defesacivil.sc.gov.br/mapa", timeout=60000)
        
        # Esperar o mapa carregar (tempo para o WebGL renderizar)
        print("Aguardando renderização do mapa...")
        page.wait_for_timeout(15000) # 15 segundos
        
        # Tentar clicar na estação Tubarão Guarda (se aparecer)
        # O seletor exato depende do HTML da SDC (precisa inspecionar)
        # Por enquanto, apenas capturamos os JSONs
        
        print(f"JSONs capturados: {len(captured_data)}")
        if captured_data:
            # Salvar para análise
            with open("sdc_json_capturado.json", "w") as f:
                json.dump(captured_data, f, indent=2)
            print("Salvo em sdc_json_capturado.json")
            # Procurar por "Tubarão" ou "cota"
            for item in captured_data:
                if "Tubarão" in str(item) or "cota" in str(item).lower():
                    print("Possível dado encontrado!")
                    print(str(item)[:500])
        
        browser.close()

if __name__ == "__main__":
    raspar_sdc()
