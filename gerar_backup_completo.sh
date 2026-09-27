#!/data/data/com.termux/files/usr/bin/bash
#
# ARCTURUS — Backup Completo
# Gera um unico arquivo .txt com TODOS os scripts e documentos
# Gera um .tar.gz com dados
#
# Data: $(date)
#

BASE=~/ARCTURUS_CLIMATIK
OUT=$BASE/backup_completo
mkdir -p "$OUT"

echo "================================================================"
echo " ARCTURUS CLIMATIK — GERADOR DE BACKUP COMPLETO"
echo " Data: $(date)"
echo "================================================================"
echo

# ============================================================
# 1. CONCATENAR TODOS OS SCRIPTS PYTHON
# ============================================================
echo "[1/5] Concatenando scripts Python..."

OUT_SCRIPTS="$OUT/TODOS_SCRIPTS_PY.txt"
echo "================================================================" > "$OUT_SCRIPTS"
echo " ARCTURUS CLIMATIK — TODOS OS SCRIPTS PYTHON" >> "$OUT_SCRIPTS"
echo " Data: $(date)" >> "$OUT_SCRIPTS"
echo "================================================================" >> "$OUT_SCRIPTS"
echo "" >> "$OUT_SCRIPTS"

for f in "$BASE"/*.py; do
    if [ -f "$f" ]; then
        echo "================================================================" >> "$OUT_SCRIPTS"
        echo " ARQUIVO: $(basename $f)" >> "$OUT_SCRIPTS"
        echo " Tamanho: $(wc -c < "$f") bytes" >> "$OUT_SCRIPTS"
        echo " Modificado: $(stat -c %y "$f" 2>/dev/null || stat -f %Sm "$f")" >> "$OUT_SCRIPTS"
        echo "================================================================" >> "$OUT_SCRIPTS"
        cat "$f" >> "$OUT_SCRIPTS"
        echo "" >> "$OUT_SCRIPTS"
        echo "" >> "$OUT_SCRIPTS"
    fi
done

echo "  -> $OUT_SCRIPTS"
wc -l "$OUT_SCRIPTS"
echo

# ============================================================
# 2. CONCATENAR DOCUMENTOS MARKDOWN
# ============================================================
echo "[2/5] Concatenando documentos..."

OUT_DOCS="$OUT/TODOS_DOCS_MD.txt"
echo "================================================================" > "$OUT_DOCS"
echo " ARCTURUS CLIMATIK — TODOS OS DOCUMENTOS" >> "$OUT_DOCS"
echo " Data: $(date)" >> "$OUT_DOCS"
echo "================================================================" >> "$OUT_DOCS"
echo "" >> "$OUT_DOCS"

for f in "$BASE"/docs/*.md "$BASE"/*.md; do
    if [ -f "$f" ]; then
        echo "================================================================" >> "$OUT_DOCS"
        echo " ARQUIVO: $(basename $f)" >> "$OUT_DOCS"
        echo "================================================================" >> "$OUT_DOCS"
        cat "$f" >> "$OUT_DOCS"
        echo "" >> "$OUT_DOCS"
    fi
done

echo "  -> $OUT_DOCS"
wc -l "$OUT_DOCS"
echo

# ============================================================
# 3. LISTAR ESTRUTURA DE ARQUIVOS
# ============================================================
echo "[3/5] Gerando inventario de arquivos..."

OUT_INV="$OUT/INVENTARIO.txt"
{
    echo "================================================================"
    echo " ARCTURUS CLIMATIK — INVENTARIO DE ARQUIVOS"
    echo " Data: $(date)"
    echo "================================================================"
    echo ""
    echo "=== TAMANHO DOS DIRETORIOS ==="
    du -sh "$BASE" 2>/dev/null
    du -sh "$BASE"/* 2>/dev/null | sort -h
    echo ""
    echo "=== SCRIPTS PYTHON ==="
    ls -la "$BASE"/*.py 2>/dev/null
    echo ""
    echo "=== DOCUMENTOS ==="
    ls -la "$BASE"/*.md "$BASE"/docs/*.md 2>/dev/null
    echo ""
    echo "=== CACHE (arquivos de dados) ==="
    ls -la "$BASE"/cache/*.json "$BASE"/cache/*.csv 2>/dev/null | head -50
    echo ""
    echo "=== ESTRUTURA COMPLETA ==="
    find "$BASE" -maxdepth 3 -type f 2>/dev/null | head -200
} > "$OUT_INV"

echo "  -> $OUT_INV"
wc -l "$OUT_INV"
echo

# ============================================================
# 4. ESTADO ATUAL DO SISTEMA
# ============================================================
echo "[4/5] Capturando estado do sistema..."

OUT_ESTADO="$OUT/ESTADO_SISTEMA.txt"
{
    echo "================================================================"
    echo " ARCTURUS CLIMATIK — ESTADO DO SISTEMA"
    echo " Data: $(date)"
    echo "================================================================"
    echo ""
    echo "=== PROCESSOS ATIVOS ==="
    ps aux | grep -E "bot_v6|crond|oikosd7|runsvdir|tmux" | grep -v grep
    echo ""
    echo "=== TMUX ==="
    tmux ls 2>/dev/null || echo "sem sessao tmux"
    echo ""
    echo "=== CRON ==="
    crontab -l 2>/dev/null
    echo ""
    echo "=== SERVICOS TERMUX ==="
    ls /data/data/com.termux/files/usr/var/service/ 2>/dev/null
    echo ""
    echo "=== ULTIMA MODIFICACAO DO CACHE ==="
    ls -lat "$BASE"/cache/*.json 2>/dev/null | head -20
    echo ""
    echo "=== CONTEUDO DO .env (sem valores) ==="
    cut -d= -f1 "$BASE"/.env 2>/dev/null
    echo ""
    echo "=== PERMISSOES .env ==="
    ls -la "$BASE"/.env 2>/dev/null
} > "$OUT_ESTADO"

echo "  -> $OUT_ESTADO"
wc -l "$OUT_ESTADO"
echo

# ============================================================
# 5. EMPACOTAR DADOS
# ============================================================
echo "[5/5] Empacotando dados (JSON + CSV + split)..."

cd "$BASE"
tar -czf "$OUT/dados_compactados.tar.gz" \
    cache/*.json \
    cache/*.csv \
    cache/split_v3.json \
    cache/previsoes_log.jsonl \
    2>/dev/null || echo "  (alguns arquivos nao encontrados, ok)"

echo "  -> $OUT/dados_compactados.tar.gz"
ls -lh "$OUT/dados_compactados.tar.gz" 2>/dev/null
echo

# ============================================================
# FINAL
# ============================================================
echo "================================================================"
echo " BACKUP COMPLETO GERADO"
echo "================================================================"
echo
echo "Diretorio: $OUT"
echo
ls -lh "$OUT/"
echo
echo "================================================================"
echo " Tamanho total:"
du -sh "$OUT"
echo "================================================================"
