#!/usr/bin/env python3
"""
Normaliza serie ANA HidroSerieCotas.
Regra: 1 item por mes, preferindo nc=2 (revisado).
Se nao tiver nc=2: usar nc=1 de 00:00 (consolidacao do dia).
"""
import json
import sys, os
sys.path.insert(0, '/data/data/com.termux/files/home/ARCTURUS_CLIMATIK')
from normalizador import numero

def normalizar_arquivo(path_in, path_out):
    d = json.load(open(path_in))
    items = d.get("items", [])

    por_mes = {}
    for it in items:
        data_full = it.get('Data_Hora_Dado', '')  # '2020-01-01 17:00:00.0'
        if len(data_full) < 7:
            continue
        mes = data_full[:7]  # '2020-01'
        hora = data_full[11:13] if len(data_full) >= 13 else '00'

        # IMPORTANTE: nc vem como STRING ('1', '2')
        nc = str(it.get('nivelconsistencia', '0'))

        # Prioridade: nc=2 > nc=1 hora 00 > nc=1 hora 07 > nc=1 hora 17
        if nc == '2':
            score = 100
        elif nc == '1' and hora == '00':
            score = 50
        elif nc == '1' and hora == '07':
            score = 30
        elif nc == '1' and hora == '17':
            score = 20
        else:
            score = 0

        if mes not in por_mes or score > por_mes[mes]['score']:
            por_mes[mes] = {'item': it, 'score': score, 'nc': nc, 'hora': hora}

    # Debug: mostra qual item foi escolhido por mes
    print("=== ITEM ESCOLHIDO POR MES ===")
    for mes in sorted(por_mes.keys()):
        info = por_mes[mes]
        print(f"  {mes}: nc={info['nc']} hora={info['hora']} score={info['score']}")
    print()

    # Gera CSV
    from datetime import datetime
    linhas = ["data,cota,cota_status,fonte_estacao,nc,ult_atualizacao"]
    total = 0

    for mes in sorted(por_mes.keys()):
        it = por_mes[mes]['item']
        nc = por_mes[mes]['nc']
        ano, m = mes.split('-')

        for dia in range(1, 32):
            cota_key = f'Cota_{dia:02d}'
            cota_status_key = f'Cota_{dia:02d}_Status'

            cota = numero(it.get(cota_key))
            status = it.get(cota_status_key)

            if cota is None:
                continue

            try:
                data = f"{ano}-{m}-{dia:02d}"
                datetime.strptime(data, "%Y-%m-%d")
            except ValueError:
                continue

            linhas.append(f"{data},{cota:.2f},{status or ''},84580000,{nc},{it.get('Data_Ultima_Alteracao', '')[:10]}")
            total += 1

    with open(path_out, 'w') as f:
        f.write('\n'.join(linhas))

    print(f"Saida:   {path_out}")
    print(f"Meses:   {len(por_mes)}")
    print(f"Cotas:   {total}")

if __name__ == "__main__":
    normalizar_arquivo(
        "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache/cotas_84580000_2020.json",
        "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache/cotas_84580000_2020.csv"
    )
