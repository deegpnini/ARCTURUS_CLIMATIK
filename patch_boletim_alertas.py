#!/usr/bin/env python3
"""Patch: unidade dupla, alertas INMET e nota de contexto no boletim."""
from pathlib import Path
import shutil

arquivo = Path("boletim_telegram.py")
backup = Path("boletim_telegram.py.bak_alertas")

if backup.exists():
    shutil.copy2(backup, arquivo)
else:
    shutil.copy2(arquivo, backup)
    print(f"[OK] Backup criado: {backup}")

texto = arquivo.read_text(encoding="utf-8")

# 1. Adicionar função de alertas INMET (se não existir)
if "def buscar_alertas_inmet" not in texto:
    ancora = "def gerar_boletim"  # ou a função principal
    pos = texto.find(ancora)
    if pos == -1:
        print("[AVISO] Função principal não encontrada. Adicionando no início do arquivo.")
        pos = 0
    nova_funcao = '''
def buscar_alertas_inmet():
    """Busca alertas oficiais do INMET para a região da bacia."""
    import requests
    # API pública do INMET (simplificada)
    try:
        url = "https://apiprevmet3.inmet.gov.br/avisos"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            dados = r.json()
            # Filtrar por SC
            alertas = [a for a in dados if "SC" in a.get("estados", "") or "Santa Catarina" in a.get("estados", "")]
            if alertas:
                return alertas[0].get("titulo", "Alerta ativo")
        return "Sem alertas ativos no momento"
    except Exception:
        return "Sem alertas ativos no momento"

'''
    texto = texto[:pos] + nova_funcao + texto[pos:]
    print("[OK] Função buscar_alertas_inmet() adicionada")

# 2. Adicionar unidade dupla (cm + m) e alertas no texto do boletim
# Procurar onde a cota é formatada
if "cm ({" not in texto and "Cota atual" in texto:
    # Substituir a formatação da cota
    import re
    # Padrão: "{cota_atual:.0f} cm" → "{cota_atual:.0f} cm ({cota_atual/100:.2f} m)"
    texto = re.sub(
        r'\{cota_atual:\.0f\} cm',
        '{cota_atual:.0f} cm ({cota_atual/100:.2f} m)',
        texto
    )
    print("[OK] Unidade dupla (cm + m) aplicada")

# 3. Adicionar bloco de alertas oficiais no topo do boletim
if "ALERTAS OFICIAIS" not in texto:
    # Procurar onde o boletim começa (ex: "🌊 ARCTURUS")
    ancora_boletim = '"🌊 ARCTURUS'
    pos = texto.find(ancora_boletim)
    if pos != -1:
        # Inserir o bloco antes
        bloco_alertas = '''
    # Bloco de alertas oficiais
    alerta_inmet = buscar_alertas_inmet()
    msg += f"\\n⚠️ *ALERTAS OFICIAIS (INMET / DEFESA CIVIL)*\\n"
    msg += f"• INMET: {alerta_inmet}\\n"
    msg += f"• Defesa Civil: {nivel_risco_defesa_civil}\\n\\n"
'''
        # Encontrar o final da string do boletim (onde msg é montada)
        # Inserir antes do envio para o Telegram
        pos_envio = texto.find("requests.post")
        if pos_envio != -1:
            texto = texto[:pos_envio] + bloco_alertas + texto[pos_envio:]
            print("[OK] Bloco de alertas oficiais adicionado")

# 4. Adicionar nota de contexto na projeção do modo sombra
if "consequência da chuva prevista" not in texto:
    ancora_sombra = "Projeção experimental · modo sombra"
    pos = texto.find(ancora_sombra)
    if pos != -1:
        nota = " (elevação consequência da chuva prevista na cabeceira/médio curso)"
        texto = texto[:pos + len(ancora_sombra)] + nota + texto[pos + len(ancora_sombra):]
        print("[OK] Nota de contexto adicionada")

arquivo.write_text(texto, encoding="utf-8")
print("[OK] Patch aplicado ao boletim_telegram.py")
