from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
f = ROOT / "tools/treinar_producao.py"
s = f.read_text(encoding="utf-8")
velho = 'feats = [c for c in df.columns if c not in ("timestamp", target_abs)]'
assert s.count(velho) == 1, f"linha nao encontrada ({s.count(velho)} ocorrencias)"
s = s.replace(velho, 'feats = [c for c in df.columns if c not in ("timestamp", target_abs, "vazao")]')
f.write_text(s, encoding="utf-8")
print("ok: treinar_producao.py sem vazao")
