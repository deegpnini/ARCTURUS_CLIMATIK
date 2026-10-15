import hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LF = ROOT / "modelos/hashes_lf.json"
def sha_lf(p): return hashlib.sha256(Path(p).read_bytes().replace(b"\r", b"")).hexdigest()
hs = {h: sha_lf(ROOT / f"modelos/modelo_delta_{h}.txt") for h in ("1h", "3h", "6h")}
if "--gravar" in sys.argv:
    man = json.load(open(ROOT / "modelos/manifesto_producao.json", encoding="utf-8"))
    out = {"nota": "sha256 do conteudo do modelo SEM o caractere CR. O treino no Linux e o do Windows geram as mesmas arvores; so o fim de linha do arquivo muda (CR extra no Windows).",
           "sha256_sem_CR": hs,
           "sha256_bruto_no_manifesto": {h: man["horizontes"][h]["sha256_modelo"] for h in hs}}
    LF.write_text(json.dumps(out, indent=2), encoding="utf-8", newline="\n")
    print("gravado", LF.name)
ref = json.load(open(LF, encoding="utf-8"))["sha256_sem_CR"]
ok = True
for h in hs:
    igual = hs[h] == ref[h]; ok &= igual
    print(f"{h} {hs[h][:16]} {'OK' if igual else 'DIFERE'}")
print("VEREDITO:", "OK" if ok else "FALHA")
sys.exit(0 if ok else 1)
