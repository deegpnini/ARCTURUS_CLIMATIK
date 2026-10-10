import json

with open("data/split_v3.json", encoding="utf-8") as f:
    split = json.load(f)

print("=== CHAVES DO SPLIT ===")
for k in split.keys():
    v = split[k]
    if isinstance(v, list):
        print(f"  {k}: lista com {len(v)} itens")
    else:
        print(f"  {k}: {type(v).__name__}")

print()
print("=== HISTORICO (27 eventos) ===")
for i, ev in enumerate(split["historico"]):
    print(f"[{i:2d}] inicio={ev.get('inicio')} fim={ev.get('fim')} pico={ev.get('pico')}")

print()
print("=== OPERACIONAL ===")
op = split.get("operacional")
if op:
    print(f"  {op}")

print()
print("=== INDEXACAO DO BENCHMARK ===")
print(f"  treino_fim  = historico[17]['fim']  = {split['historico'][17]['fim']}")
print(f"  val_ini     = historico[18]['inicio']= {split['historico'][18]['inicio']}")
print(f"  val_fim     = historico[21]['fim']   = {split['historico'][21]['fim']}")
print(f"  teste_ini   = historico[22]['inicio']= {split['historico'][22]['inicio']}")
print(f"  teste_fim   = historico[26]['fim']   = {split['historico'][26]['fim']}")
