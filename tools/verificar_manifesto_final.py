import json

m = json.load(open("modelos/manifesto_producao.json", encoding="utf-8"))
for h, info in m["horizontes"].items():
    feats = info["features"]
    print(f"{h}: {len(feats)} features")
    print(f"  Primeiras 5: {feats[:5]}")
    print(f"  'vazao' presente: {'vazao' in feats}")
    print()
