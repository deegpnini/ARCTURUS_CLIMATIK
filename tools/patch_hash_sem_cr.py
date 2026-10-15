import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FUNC = ("def sha256_lf(path):\n"
        "    # sha256 do conteudo sem o caractere CR (o Windows grava CR extra no fim; as arvores sao as mesmas)\n"
        "    with open(path, 'rb') as f:\n"
        "        return hashlib.sha256(f.read().replace(b'\\r', b'')).hexdigest()\n\n\n")
def ler(p):
    s = p.read_bytes().decode("utf-8")
    return s, ("\r\n" if "\r\n" in s else "\n")
def grava(p, s): p.write_bytes(s.encode("utf-8"))

# 1. treinar_producao.py
p = ROOT / "tools/treinar_producao.py"; s, eol = ler(p)
if "sha256_lf" not in s:
    assert s.count("def sha256(path):") == 1
    s = s.replace("def sha256(path):", FUNC.replace("\n", eol) + "def sha256(path):")
    pat = re.compile(r'(?m)^([ \t]*)"sha256_modelo": model_hash,(\r?\n)')
    assert len(pat.findall(s)) == 1
    s = pat.sub(lambda m: m.group(0) + m.group(1) + '"sha256_modelo_sem_CR": sha256_lf(model_path),' + m.group(2), s)
    grava(p, s); print("ok treinar_producao.py")

# 2. testar_reprodutibilidade.py
p = ROOT / "tools/testar_reprodutibilidade.py"; s, eol = ler(p)
if "sha256_lf" not in s:
    assert s.count("def sha256(path):") == 1
    s = s.replace("def sha256(path):", FUNC.replace("\n", eol) + "def sha256(path):")
    pat = re.compile(r'(?m)^([ \t]*)hash_esperado = info\["sha256_modelo"\](\r?\n)')
    assert len(pat.findall(s)) == 1
    def rep(m):
        i, e = m.group(1), m.group(2)
        linhas = ['hash_esperado = info["sha256_modelo"]',
                  'hash_esperado_lf = info.get("sha256_modelo_sem_CR")',
                  'if hash_atual != hash_esperado and hash_esperado_lf and sha256_lf(model_path) == hash_esperado_lf:',
                  '    print("  [i] arquivo difere do manifesto so no caractere CR (mesmas arvores)")',
                  '    hash_atual, hash_esperado = hash_esperado_lf, hash_esperado_lf']
        return "".join(i + l + e for l in linhas)
    s = pat.sub(rep, s); grava(p, s); print("ok testar_reprodutibilidade.py")

# 3. manifesto (so acrescenta o campo; hashes antigos intactos)
p = ROOT / "modelos/manifesto_producao.json"; s, eol = ler(p)
if "sha256_modelo_sem_CR" not in s:
    man = json.loads(s); lf = json.load(open(ROOT / "modelos/hashes_lf.json", encoding="utf-8"))["sha256_sem_CR"]
    for h in ("1h", "3h", "6h"):
        a = man["horizontes"][h]["sha256_modelo"]
        pat = re.compile(r'(?m)^([ \t]*)"sha256_modelo": "' + a + r'",(\r?\n)')
        assert len(pat.findall(s)) == 1, h
        s = pat.sub(lambda m: m.group(0) + m.group(1) + '"sha256_modelo_sem_CR": "' + lf[h] + '",' + m.group(2), s)
    json.loads(s); grava(p, s); print("ok manifesto_producao.json")
