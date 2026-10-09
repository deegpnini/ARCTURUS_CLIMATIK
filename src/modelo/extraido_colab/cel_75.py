# ============================================================
# VALIDACAO PROSPECTIVA — previsao vs observado
# ============================================================
import json
import pandas as pd
from datetime import datetime, timedelta

# Carrega telemetria
with open("/content/telemetria_84580000_2026.json") as f:
    tel = json.load(f)

# Mapa de cota
leituras = {}
for it in tel['items']:
    ts = it.get('Data_Hora_Medicao', '')[:19]
    c = it.get('Cota_Adotada')
    v = None
    if c is not None and c != '':
        try: v = float(str(c).replace(',', '.'))
        except: pass
    leituras[ts] = v

# Carrega log
with open("/content/drive/MyDrive/ARCTURUS_ML/shadow_log.jsonl") as f:
    logs = [json.loads(l) for l in f.readlines()]

# Pega ultima previsao
ultima = logs[-1]
print(f"=== VALIDACAO DA PREVISAO ===")
print(f"Data medicao: {ultima['data_medicao']}")
print(f"Cota atual: {ultima['cota_atual']}")
print(f"Features: {ultima['features_disponiveis']}/{ultima['features_total']}")
print()

t0 = datetime.strptime(ultima['data_medicao'], "%Y-%m-%d %H:%M:%S")

for h, horas in [('1h', 1), ('3h', 3), ('6h', 6)]:
    t_alvo = t0 + timedelta(hours=horas)
    ts_alvo = t_alvo.strftime("%Y-%m-%d %H:%M:%S")
    real = leituras.get(ts_alvo)
    previsto = ultima['previsoes'][h]['cota']
    delta_prev = ultima['previsoes'][h]['delta']

    if real is not None:
        erro = abs(previsto - real)
        delta_real = real - ultima['cota_atual']
        print(f"{h}:")
        print(f"  Alvo: {ts_alvo}")
        print(f"  Cota atual: {ultima['cota_atual']}")
        print(f"  Previsto: {previsto:.1f} (delta {delta_prev:+.1f})")
        print(f"  Real: {real:.1f} (delta {delta_real:+.1f})")
        print(f"  ERRO: {erro:.1f} cm")
        print()
    else:
        print(f"{h}: alvo {ts_alvo} sem dado ainda")
        print()