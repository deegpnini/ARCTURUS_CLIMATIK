from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
f = ROOT / "src/modelo/delta_evento_446.py"
s = f.read_text(encoding="utf-8")
velho = "'3h': ('2026-09-22 03:00:00', 413.0),"
assert s.count(velho) == 1, "linha do alvo 3h nao encontrada"
s = s.replace(velho, "'3h': ('2026-09-22 03:00:00', 398.0),  # corrigido: 413 era a leitura de 01:45")
f.write_text(s, encoding="utf-8")
print("ok: alvo 3h corrigido")
