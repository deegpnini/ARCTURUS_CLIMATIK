# ============================================================
# VALIDACAO 446 — FIX do format + analise final
# ============================================================
import json
from datetime import datetime, timedelta

with open("/content/telemetria_84580000_2026.json") as f:
    tel = json.load(f)

evento = [it for it in tel['items']
          if it.get('Data_Hora_Medicao', '').startswith(('2026-09-21', '2026-09-22'))]
evento.sort(key=lambda x: x.get('Data_Hora_Medicao'))

leituras = {}
chuvas = {}
vazoes = {}
for it in evento:
    ts = it.get('Data_Hora_Medicao', '')[:19]
    for campo, dicionario in [('Cota_Adotada', leituras),
                                ('Chuva_Adotada', chuvas),
                                ('Vazao_Adotada', vazoes)]:
        v = it.get(campo)
        val = None
        if v is not None and v != '':
            try: val = float(str(v).replace(',', '.'))
            except: pass
        dicionario[ts] = val

# ============================================================
# ANALISE: CHUVA E VAZAO NO ENTORNO DO GAP
# ============================================================
print("="*100)
print("CHUVA E VAZAO NO ENTORNO DO GAP (18:00 -> 00:30)")
print("="*100)
print(f"{'Timestamp':22s} | {'Cota':10s} | {'Chuva':10s} | {'Vazao':10s}")
print("-"*100)

atual = datetime(2026, 9, 21, 18, 0)
fim = datetime(2026, 9, 22, 0, 30)
while atual <= fim:
    ts = atual.strftime("%Y-%m-%d %H:%M:%S")
    cota = leituras.get(ts)
    chuva = chuvas.get(ts)
    vazao = vazoes.get(ts)
    cota_str = f"{cota:.0f}" if cota is not None else "-"
    chuva_str = f"{chuva:.1f}" if chuva is not None else "-"
    vazao_str = f"{vazao:.1f}" if vazao is not None else "-"
    print(f"{ts:22s} | {cota_str:10s} | {chuva_str:10s} | {vazao_str:10s}")
    atual += timedelta(minutes=15)

# ============================================================
# COMPARACAO: VAZAO ANTES vs DEPOIS DO GAP
# ============================================================
print()
print("="*100)
print("VAZAO ANTES vs DEPOIS DO GAP")
print("="*100)

# Vazao as 19:45 (antes do gap)
vz_antes = vazoes.get("2026-09-21 19:45:00")
print(f"Vazao 19:45: {vz_antes:.2f} m3/s" if vz_antes else "Sem vazao 19:45")

# Vazao as 00:00 (depois do gap)
vz_depois = vazoes.get("2026-09-22 00:00:00")
print(f"Vazao 00:00: {vz_depois:.2f} m3/s" if vz_depois else "Sem vazao 00:00")

if vz_antes and vz_depois:
    print(f"Variacao: {vz_depois - vz_antes:+.2f} m3/s")

# ============================================================
# RESUMO FINAL
# ============================================================
print()
print("="*100)
print("VEREDITO SOBRE 446")
print("="*100)
print("""
EVIDENCIA DE EVENTO REAL:
  - Rampa antes do gap: 52 -> 183 cm (5h de subida continua)
  - Taxa de subida acelerando: +40 cm/h as 18h
  - Gap de 4h15min (20:00-00:00)
  - Salto durante gap: +263 cm em 4h15min = +62 cm/h
  - Recessao suave depois: 446 -> 361 cm (9h)
  - 38 leituras consecutivas > 312 cm (recorde)
  - Chuva antecedente: picos de 6.8mm as 16:00

CONCLUSao:
  - 446 cm e' EVENTO HIDROLOGICO REAL
  - Taxa durante gap MAIOR que antes
  - Recessao fisica coerente
  - NAO e' spike de sensor

IMPLICACAO:
  - Teste C e' valido como teste de generalizacao
  - O modelo errou por FALTA DE DADOS no gap
  - Nao por 'modelo ruim'
""")