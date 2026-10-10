from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
f = ROOT / "src/relatorios/insight_parte2.py"
s = f.read_text(encoding="utf-8")

# Patch 1: remover linha que adiciona vazao ao dict
velho1 = '    # Vazao\n    f["vazao"] = dados.get(dt, {}).get("vazao")\n'
if velho1 in s:
    s = s.replace(velho1, "    # Vazao removida (redundante com cota)\n")

# Patch 2: remover vazao do dicionario de entrada
velho2 = '            "vazao": numero(it.get("Vazao_Adotada")),\n'
if velho2 in s:
    s = s.replace(velho2, "")

f.write_text(s, encoding="utf-8")
print("patch aplicado")
