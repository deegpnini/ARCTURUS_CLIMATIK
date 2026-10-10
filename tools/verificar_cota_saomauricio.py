import csv
from pathlib import Path

path = Path("data/consolidado/84538500_SAO_MAURICIO_JUSANTE_consolidado.csv")

with path.open(encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

print(f"Total: {len(rows)}")
print()

# Estatisticas da cota
cotas = []
for r in rows:
    c = r.get("Cota_Adotada")
    if c and c != "":
        try:
            cotas.append(float(c))
        except:
            pass

if cotas:
    print(f"Cota (n={len(cotas)}):")
    print(f"  min:  {min(cotas):.2f}")
    print(f"  max:  {max(cotas):.2f}")
    print(f"  media: {sum(cotas)/len(cotas):.2f}")
    print(f"  10 primeiras: {cotas[:10]}")
    print(f"  10 ultimas:   {cotas[-10:]}")

# Mesma coisa pra Rio Fortuna (comparacao)
print()
path2 = Path("data/consolidado/84536000_RIO_FORTUNA_JUSANTE_consolidado.csv")
with path2.open(encoding="utf-8-sig") as f:
    rows2 = list(csv.DictReader(f))

cotas2 = []
for r in rows2:
    c = r.get("Cota_Adotada")
    if c and c != "":
        try:
            cotas2.append(float(c))
        except:
            pass

print(f"RIO FORTUNA — Cota (n={len(cotas2)}):")
print(f"  min:  {min(cotas2):.2f}")
print(f"  max:  {max(cotas2):.2f}")
print(f"  media: {sum(cotas2)/len(cotas2):.2f}")

# E a ancora (Tubarao) — do backup neural, os valores sao ~100-450 cm
print()
print("REFERENCIA — Tubarao (84580000) tinha cota 100-450 cm.")
