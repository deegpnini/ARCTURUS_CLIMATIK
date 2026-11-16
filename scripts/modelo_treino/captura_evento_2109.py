#!/usr/bin/env python3
"""
Captura e alinha o evento de 21/09/2026 (ao vivo).
Chuva Orleans + cota/vazao Rio do Pouso, hora a hora.
"""
import json
from datetime import datetime, timedelta

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

# Carrega historico (ja temos)
pouso_hist = json.load(open(f"{CACHE}/ana_historico_84580000.json"))['items']
orleans_hist = json.load(open(f"{CACHE}/ana_historico_84249998.json"))['items']

# Filtra so 21/09
def filtra_dia(items, dia):
    return [it for it in items if it.get('Data_Hora_Medicao', '').startswith(dia)]

pouso_2109 = filtra_dia(pouso_hist, '2026-09-21')
orleans_2109 = filtra_dia(orleans_hist, '2026-09-21')

print("="*100)
print("EVENTO 21/09/2026 — RIO DO POUSO + ORLEANS")
print("="*100)
print(f"Leituras Pouso: {len(pouso_2109)}")
print(f"Leituras Orleans: {len(orleans_2109)}")
print()

# Alinha por hora
def por_hora(items):
    """Agrupa por hora (pega leitura da hora cheia ou mais proxima)."""
    buckets = {}
    for it in items:
        dt_str = it.get('Data_Hora_Medicao', '')
        if not dt_str: continue
        try:
            dt = datetime.strptime(dt_str[:19], "%Y-%m-%d %H:%M:%S")
        except: continue
        h = dt.replace(minute=0, second=0, microsecond=0)
        # Pega ultima leitura da hora
        if h not in buckets or dt > buckets[h][0]:
            buckets[h] = (dt, it)
    return {h: it for h, (_, it) in buckets.items()}

pouso_hora = por_hora(pouso_2109)
orleans_hora = por_hora(orleans_2109)

# Todas as horas comuns
todas_horas = sorted(set(pouso_hora.keys()) | set(orleans_hora.keys()))

print(f"{'Hora':20s} | {'Chuva Orl':10s} | {'Cota Pou':10s} | {'Vazao Pou':10s}")
print("-" * 70)

for h in todas_horas:
    pou = pouso_hora.get(h, {})
    orl = orleans_hora.get(h, {})
    
    chuva = orl.get('Chuva_Adotada', '-')
    cota = pou.get('Cota_Adotada', '-')
    vazao = pou.get('Vazao_Adotada', '-')
    
    hora_str = h.strftime("%Y-%m-%d %H:%M")
    print(f"{hora_str:20s} | {str(chuva):10s} | {str(cota):10s} | {str(vazao):10s}")

# Estatisticas do dia
print()
print("="*100)
print("ESTATISTICAS DE 21/09")
print("="*100)

cotas = [float(str(it['Cota_Adotada']).replace(',','.')) 
         for it in pouso_2109 if it.get('Cota_Adotada') and it['Cota_Adotada'] not in ('', '0.00')]
vazoes = [float(str(it['Vazao_Adotada']).replace(',','.')) 
          for it in pouso_2109 if it.get('Vazao_Adotada') and it['Vazao_Adotada'] not in ('', '0.00')]
chuvas = [float(str(it['Chuva_Adotada']).replace(',','.')) 
          for it in orleans_2109 if it.get('Chuva_Adotada') and it['Chuva_Adotada'] not in ('', '0.00')]

if cotas:
    print(f"\nPOUSO:")
    print(f"  Cota min: {min(cotas):.2f}")
    print(f"  Cota max: {max(cotas):.2f}")
    print(f"  Cota media: {sum(cotas)/len(cotas):.2f}")

if vazoes:
    print(f"\n  Vazao min: {min(vazoes):.2f}")
    print(f"  Vazao max: {max(vazoes):.2f}")
    print(f"  Vazao media: {sum(vazoes)/len(vazoes):.2f}")

if chuvas:
    print(f"\nORLEANS (chuva):")
    print(f"  Chuva total: {sum(chuvas):.2f} mm")
    print(f"  Chuva max por hora: {max(chuvas):.2f} mm")

# Comparacao com limiares estatisticos
if cotas:
    media_geral = 45.40
    sigma_geral = 51.57
    limiar_2s = media_geral + 2 * sigma_geral
    limiar_3s = media_geral + 3 * sigma_geral
    
    print()
    print("=== COMPARACAO COM LIMIARES ===")
    print(f"Media geral (abr-ago): {media_geral}")
    print(f"Desvio geral: {sigma_geral}")
    print(f"Limiar 2 sigma: {limiar_2s:.2f}")
    print(f"Limiar 3 sigma: {limiar_3s:.2f}")
    print()
    print(f"Cota max hoje: {max(cotas):.2f}")
    if max(cotas) > limiar_3s:
        print("-> ACIMA DE 3 SIGMA (evento severo)")
    elif max(cotas) > limiar_2s:
        print("-> ACIMA DE 2 SIGMA (evento moderado)")
    else:
        print("-> abaixo de 2 sigma (evento leve)")
