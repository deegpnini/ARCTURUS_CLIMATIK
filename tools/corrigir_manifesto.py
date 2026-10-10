import json
from pathlib import Path

p = Path("resultados/manifesto_loeo_v2.json")
m = json.loads(p.read_text(encoding="utf-8-sig"))

# Corrigir texto
m["n_boost_round_regra"] = "mediana dos best_iteration dos 26 folds validos (evento 13 descartado por ter <50 leituras de teste)"
m["n_folds_total_planejado"] = 27
m["n_folds_valido"] = 26
m["folds_descartados"] = [{
    "evento_idx": 13,
    "motivo": "n_teste < 50 leituras"
}]

# Corrigir mediana 1h (float no manifesto, mas arredondado como int pra uso)
# Nao altera o valor — so registra o calculo exato
m["resultado_por_horizonte"]["1h"]["best_iteration_mediana_exata"] = 156.5
m["resultado_por_horizonte"]["1h"]["best_iteration_mediana"] = 156  # arredondado pra baixo

out = p
with open(out, "w", encoding="utf-8") as f:
    json.dump(m, f, indent=2, ensure_ascii=False)

print(f"[OK] Manifesto corrigido: {out}")
print(f"  n_boost_round_regra: {m['n_boost_round_regra']}")
print(f"  Folds validos: {m['n_folds_valido']}")
print(f"  Folds descartados: {m['folds_descartados']}")
print()
print("Medianas finais:")
for h, d in m["resultado_por_horizonte"].items():
    print(f"  {h}: {d['best_iteration_mediana']} rounds")
