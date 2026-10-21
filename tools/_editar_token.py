#!/usr/bin/env python3
# ============================================================
# Editor de token — substitui hardcode por leitura de .env
# ============================================================
# Uso:
#   python3 _editar_token.py bot_v7.py
#   python3 _editar_token.py bot_telegram.py
#   python3 _editar_token.py arcturus_monitor.py
#   python3 _editar_token.py bot_v6.py
# ============================================================

import sys
import re
import shutil
from pathlib import Path
from datetime import datetime

if len(sys.argv) < 2:
    print("Uso: python3 _editar_token.py <arquivo.py>")
    sys.exit(1)

alvo = sys.argv[1]
BASE = Path.home() / "ARCTURUS_CLIMATIK"
ARQ = BASE / alvo

if not ARQ.exists():
    print(f"❌ nao existe: {ARQ}")
    sys.exit(1)

# Verifica se tem token hardcoded
texto = ARQ.read_text(encoding='utf-8')
padrao_token = re.compile(r'[0-9]{8,12}:[A-Za-z0-9_-]{30,}')
tem_token = bool(padrao_token.search(texto))

if not tem_token:
    print(f"ℹ️  {alvo} NAO tem token hardcoded. Nada a fazer.")
    sys.exit(0)

# Backup
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
bak = ARQ.with_suffix(f'.py.bak_{timestamp}')
shutil.copy(ARQ, bak)
print(f"✅ Backup: {bak.name}")

# Bloco de leitura .env
BLOCO_ENV = '''import os
from pathlib import Path

def _load_env():
    """Carrega .env do diretorio do projeto (procura ate 6 niveis acima)."""
    p = Path(__file__).resolve().parent
    for _ in range(6):
        env_file = p / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
            return
        p = p.parent

_load_env()
'''

linhas = texto.splitlines()
linhas_novas = []
adicionou_bloco = False
trocou_variavel = False

for linha in linhas:
    # Encontra a linha do token
    if padrao_token.search(linha):
        # Se ainda nao adicionou o bloco .env, adiciona antes
        if not adicionou_bloco:
            linhas_novas.append("# --- Leitura segura de credenciais (.env) ---")
            for bl in BLOCO_ENV.splitlines():
                linhas_novas.append(bl)
            linhas_novas.append("# --- Fim do bloco .env ---")
            linhas_novas.append("")
            adicionou_bloco = True

        # Substitui a linha do token pela leitura do .env
        if "TELEGRAM_TOKEN" in linha:
            linhas_novas.append('TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")')
            trocou_variavel = True
        elif "TOKEN_BOT" in linha:
            linhas_novas.append('TOKEN_BOT = os.environ.get("TELEGRAM_TOKEN", "")')
            trocou_variavel = True
        else:
            linhas_novas.append('TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")')
            trocou_variavel = True
        continue

    # Substitui CHAT_ID hardcoded
    if re.search(r'CHAT_ID\s*=\s*"7', linha):
        linhas_novas.append('TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")')
        continue

    linhas_novas.append(linha)

if not trocou_variavel:
    print("⚠️  Nao achei a linha do token — nada mudou")
    # Restaura backup
    shutil.copy(bak, ARQ)
    bak.unlink()
    sys.exit(1)

ARQ.write_text("\n".join(linhas_novas) + "\n", encoding='utf-8')
print(f"✅ {alvo} editado")

# Verifica se token sumiu
texto_novo = ARQ.read_text(encoding='utf-8')
if padrao_token.search(texto_novo):
    print(f"❌ Token ainda aparece em {alvo} — revertendo")
    shutil.copy(bak, ARQ)
    sys.exit(1)

print(f"✅ Token removido do codigo")

# Teste de sintaxe
import py_compile
try:
    py_compile.compile(str(ARQ), doraise=True)
    print(f"✅ Sintaxe OK")
except py_compile.PyCompileError as e:
    print(f"❌ Sintaxe quebrada: {e}")
    print(f"   Revertendo...")
    shutil.copy(bak, ARQ)
    sys.exit(1)

print()
print(f"Para reverter: cp {bak.name} {alvo}")
