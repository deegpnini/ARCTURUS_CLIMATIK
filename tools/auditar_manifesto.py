import json
import statistics
from pathlib import Path

p = Path("resultados/manifesto_loeo_v2.json")
m = json.loads(p.read_text(encoding="utf-8-sig"))

for horizonte, dados in m["resultado_por_horizonte"].items():
    folds = dados.get("folds", [])
    iteracoes = [f["best_iteration"] for f in folds if f.get("best_iteration") is not None]

    print(f"\n=== Horizonte {horizonte} ===")
    print(f"  Folds registrados:      {len(folds)}")
    print(f"  Iteracoes validas:      {len(iteracoes)}")
    print(f"  Mediana recalculada:    {statistics.median(iteracoes) if iteracoes else 'sem dados'}")
    print(f"  Mediana no manifesto:   {dados.get('best_iteration_mediana')}")
    print(f"  Min:                    {min(iteracoes) if iteracoes else '-'}")
    print(f"  Max:                    {max(iteracoes) if iteracoes else '-'}")
    print(f"  Eventos registrados:    {[f.get('evento_idx') for f in folds]}")
