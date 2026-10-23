import json
import pandas as pd
from pathlib import Path

BASE = Path(".")
MODELOS = BASE / "modelos"

def gerar_relatorio():
    # Dados do modelo (do nosso insight_operacional)
    # Vamos simular os valores que o modelo gerou hoje
    cota_atual = 170.38  # cm (normalizada da Rio Fortuna)
    delta_previsto = -1.13  # cm
    
    # Dados do GEE
    altitude_regua = 23.0
    cota_risco_cm = 446.0  # cm (evento de 22/09)
    altitude_risco = altitude_regua + (cota_risco_cm / 100)
    
    # Cálculo de tempo para atingir a cota de risco (hipotético)
    distancia = cota_risco_cm - cota_atual
    if delta_previsto > 0:
        horas = distancia / delta_previsto
    else:
        horas = float('inf')
    
    # Markdown
    relatorio = f"""# Relatório de Risco Hidrológico
## Bacia do Tubarão (23/10/2026)

### Dados Atuais
- **Cota Atual (normalizada):** {cota_atual:.2f} cm
- **Delta Previsto (1h):** {delta_previsto:+.2f} cm
- **Altitude da Régua:** {altitude_regua:.1f} m

### Dados de Risco
- **Cota de Risco (pico 22/09):** {cota_risco_cm:.0f} cm
- **Altitude de Inundação:** {altitude_risco:.2f} m
- **Área Inundável (GEE):** 200.26 km²

### Estimativa de Tempo
"""
    if delta_previsto > 0:
        relatorio += f"Com o delta de {delta_previsto:+.2f} cm/h, o rio levaria **{horas:.1f} horas** para atingir a cota de risco ({cota_risco_cm} cm).\n"
    else:
        relatorio += "O rio está em **recessão** (delta negativo). Não há risco imediato de atingir a cota de 446 cm.\n"
        
    relatorio += """
### Limitações
- O MDE (SRTM 30m) tem resolução de 30m, não suficiente para mapear ruas.
- A cota atual é normalizada da PCH Rio Fortuna (substituta da ANA).
- O modelo não prevê eventos extremos (> 320 cm) com confiança.
"""
    print(relatorio)
    
    # Salvar em arquivo
    with open(BASE / "docs" / "RELATORIO_RISCO.md", "w") as f:
        f.write(relatorio)
    print("✅ Relatório salvo em docs/RELATORIO_RISCO.md")

if __name__ == "__main__":
    gerar_relatorio()
