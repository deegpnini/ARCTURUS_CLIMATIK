from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
f = ROOT / "src/relatorios/insight_parte2.py"
s = f.read_text(encoding="utf-8")

# Corrigir mensagem: usar total de features reais (sem timestamp)
velho = 'print(f"    Features disponiveis: {res[\'features_usadas\']}/27")'
novo = 'print(f"    Features disponiveis: {res[\'features_usadas\']}/{res[\'features_total\']}")'
if velho in s:
    s = s.replace(velho, novo)

# features_usadas = valores nao nulos EXCLUINDO timestamp
# features_total = total de features do modelo (26)
velho2 = '"features_usadas": len(feats_dict),'
novo2 = '"features_usadas": sum(1 for k, v in feats_dict.items() if k != "timestamp" and v is not None),\n        "features_total": len(feats_dict) - 1,  # -1 para excluir timestamp'
if velho2 in s:
    s = s.replace(velho2, novo2)

f.write_text(s, encoding="utf-8")
print("patch aplicado")
