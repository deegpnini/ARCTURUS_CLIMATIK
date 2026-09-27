#!/usr/bin/env python3
"""
Mascara de disponibilidade de Cota_Adotada.
Conta amostras reais para 1h, 3h, 6h.
"""
import json, os
from datetime import datetime, timedelta
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
CODIGO = "84580000"

# Carrega todos os anos
dados = {}
for ano in [2024, 2025, 2026]:
    path = f"{CACHE}/telemetria_{CODIGO}_{ano}.json"
    if not os.path.exists(path): continue
    d = json.load(open(path))
    for it in d.get("items", []):
        ts_str = it.get('Data_Hora_Medicao', '')[:19]
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except:
            continue
        # So cota valida (nao None, nao vazio)
        cota = it.get('Cota_Adotada')
        cota_v = None
        if cota is not None and cota != '':
            try:
                cota_v = float(str(cota).replace(',', '.'))
            except:
                pass
        # Deduplica
        if dt not in dados:
            dados[dt] = cota_v

print(f"Total timestamps unicos: {len(dados)}")
print(f"Com cota valida: {sum(1 for v in dados.values() if v is not None)}")
print()

# Ordena
timestamps = sorted(dados.keys())

# Conta amostras reais para cada horizonte
# target_1h: precisa cota(t) e cota(t+1h)
# target_3h: precisa cota(t) e cota(t+3h)
# target_6h: precisa cota(t) e cota(t+6h)

resultados = {
    '1h': {'valido': 0, 'bloqueado': 0},
    '3h': {'valido': 0, 'bloqueado': 0},
    '6h': {'valido': 0, 'bloqueado': 0},
}

# Mapa de timestamp -> cota (para lookup rapido)
lookup = dados

for dt in timestamps:
    cota_t = lookup.get(dt)
    if cota_t is None:
        # Sem cota em t: bloqueia tudo
        for h in ['1h', '3h', '6h']:
            resultados[h]['bloqueado'] += 1
        continue

    # Verifica cada horizonte
    for h, delta in [('1h', timedelta(hours=1)), ('3h', timedelta(hours=3)), ('6h', timedelta(hours=6))]:
        t_alvo = dt + delta
        cota_alvo = lookup.get(t_alvo)
        if cota_alvo is not None:
            resultados[h]['valido'] += 1
        else:
            resultados[h]['bloqueado'] += 1

print("="*70)
print("AMOSTRAS REAIS POR HORIZONTE")
print("="*70)
print(f"{'Horizonte':12s} | {'Validos':10s} | {'Bloqueados':11s} | {'% Valido':10s}")
print("-"*70)
for h in ['1h', '3h', '6h']:
    v = resultados[h]['valido']
    b = resultados[h]['bloqueado']
    total = v + b
    pct = v / total * 100 if total else 0
    print(f"{h:12s} | {v:10d} | {b:11d} | {pct:9.1f}%")

# Distribuicao de blocos continuos
print()
print("="*70)
print("BLOCOS CONTINUOS DE COTA (minimo 24h = 96 leituras)")
print("="*70)

blocos = []
bloco_atual = []
for dt in timestamps:
    if lookup.get(dt) is not None:
        # Continua? Se gap > 30min: quebra
        if bloco_atual:
            gap = (dt - bloco_atual[-1]).total_seconds() / 60
            if gap > 30:
                if len(bloco_atual) >= 96:
                    blocos.append(bloco_atual)
                bloco_atual = []
        bloco_atual.append(dt)
    else:
        if len(bloco_atual) >= 96:
            blocos.append(bloco_atual)
        bloco_atual = []

if len(bloco_atual) >= 96:
    blocos.append(bloco_atual)

print(f"Total de blocos continuos >= 96 leituras (24h): {len(blocos)}")
print()
print("Maiores 10 blocos:")
for b in sorted(blocos, key=lambda x: -len(x))[:10]:
    duracao_h = len(b) * 0.25
    print(f"  {b[0]} -> {b[-1]}  ({len(b)} leituras, {duracao_h:.1f}h)")

# Total de leituras em blocos >= 24h
total_blocos = sum(len(b) for b in blocos)
print()
print(f"Total de leituras em blocos >= 24h: {total_blocos}")
print(f"% do total: {total_blocos/len(timestamps)*100:.1f}%")
