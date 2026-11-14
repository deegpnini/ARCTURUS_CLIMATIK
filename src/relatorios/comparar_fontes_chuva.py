#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confronto de fontes de chuva (lê o JSON consolidado do baixar_previsao_tripla.py)."""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
DATA = BASE / "data"
JSON_ENSEMBLE = DATA / "chuva_ensemble_consolidada.json"

print("=== ARCTURUS CLIMATIK: CONFRONTO E ENSEMBLE DE PREVISÃO DE CHUVA (3 FONTES) ===")

if not JSON_ENSEMBLE.exists():
    print("[ERRO] JSON consolidado não encontrado. Rode baixar_previsao_tripla.py primeiro.")
    exit(1)

with open(JSON_ENSEMBLE, "r") as f:
    dados = json.load(f)

ecmwf = dados.get("ecmwf_72h_mm", 0)
gfs = dados.get("gfs_72h_mm", 0)
ukmo = dados.get("ukmo_72h_mm", 0)
media = dados.get("media_72h_mm", 0)
pior = dados.get("pior_caso_72h_mm", 0)
div_total = dados.get("divergencia_total_mm", 0)
div_horaria = dados.get("divergencia_horaria_max_mm", 0)
confianca = dados.get("confianca", "DESCONHECIDA")

print(f"[OK] ECMWF: {ecmwf:.1f} mm (72h)")
print(f"[OK] GFS:   {gfs:.1f} mm (72h)")
print(f"[OK] UKMO:  {ukmo:.1f} mm (72h)")
print(f"📊 Índice de Confiança: {confianca} (Δ total = {div_total:.1f} mm | Δ horária máx = {div_horaria:.1f} mm)")

print("\n" + "="*60)
print("📊 RESUMO DO CONFRONTO DE PREVISÃO (72 HORAS)")
print("="*60)
print(f"• Fonte A (ECMWF):  {ecmwf:6.1f} mm")
print(f"• Fonte B (GFS):    {gfs:6.1f} mm")
print(f"• Fonte C (UKMO):   {ukmo:6.1f} mm")
print(f"• Média das Fontes: {media:6.1f} mm")
print(f"• Pior Caso:        {pior:6.1f} mm  <-- Valor recomendado para o Alerta")
print(f"• Divergência total: {div_total:6.1f} mm")
print(f"• Divergência horária máx: {div_horaria:6.1f} mm")

if confianca == "BAIXA":
    print("\n🚨 ALERTA DE ALTA INCERTEZA METEOROLÓGICA!")
    print(f"   A divergência entre os modelos ({div_total:.1f} mm) é ALTA.")
    print("   Recomendação: Adotar a premissa do Pior Caso (Conservador) na matriz de decisão do ARCTURUS.")
elif confianca == "MÉDIA":
    print("\n⚠️  CONFIANÇA MÉDIA: Os modelos divergem moderadamente. Usar a média com cautela.")
else:
    print("\n✅ COERÊNCIA MODELAR: Os modelos apresentam convergência dentro da margem aceitável.")

print(f"\n[OK] Resultado consolidado (JSON): {JSON_ENSEMBLE}")
