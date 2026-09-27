#!/bin/bash
# ============================================================
# ARCTURUS CLIMATIK — INVENTÁRIO LOCAL
# ============================================================

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🟣 ARCTURUS CLIMATIK — INVENTÁRIO LOCAL                     ║"
echo "║  📅 $(date '+%d/%m/%Y %H:%M')                                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

BASE=~/ARCTURUS_CLIMATIK

echo "══════════════════════════════════════════════════════════════"
echo "📁 ESTRUTURA"
echo "══════════════════════════════════════════════════════════════"
find "$BASE" -maxdepth 2 -type d 2>/dev/null | sed "s|$BASE|.|" | sort
echo ""

echo "══════════════════════════════════════════════════════════════"
echo "📊 MÓDULOS E TAMANHOS"
echo "══════════════════════════════════════════════════════════════"
for pasta in dados/clima dados/climatik modulos/sismico modulos/visual modulos/sentinel modulos/videos modulos/audio core/arcturus; do
    if [ -d "$BASE/$pasta" ]; then
        size=$(du -sh "$BASE/$pasta" 2>/dev/null | awk '{print $1}')
        count=$(find "$BASE/$pasta" -type f 2>/dev/null | wc -l)
        printf "  %-25s %8s  (%d arquivos)\n" "$pasta" "$size" "$count"
    fi
done
echo ""

echo "══════════════════════════════════════════════════════════════"
echo "💾 TOTAL DO ARCTURUS CLIMATIK"
echo "══════════════════════════════════════════════════════════════"
du -sh "$BASE" 2>/dev/null
echo "Total de arquivos: $(find "$BASE" -type f 2>/dev/null | wc -l)"
echo ""

echo "══════════════════════════════════════════════════════════════"
echo "📄 ARQUIVOS-CHAVE POR MÓDULO"
echo "══════════════════════════════════════════════════════════════"

echo "🌦️ CLIMA:"
find "$BASE/dados/clima" -type f -name "*.csv" -o -name "*.json" 2>/dev/null | head -5 | sed "s|$BASE|.|"
echo ""

echo "📊 CLIMATIK (dados históricos):"
find "$BASE/dados/climatik" -type f -name "*.csv" 2>/dev/null | head -5 | sed "s|$BASE|.|"
echo ""

echo "🌍 SÍSMICO (RICHTER):"
find "$BASE/modulos/sismico" -type f 2>/dev/null | head -5 | sed "s|$BASE|.|"
echo ""

echo "🛰️ VISUAL/SENTINEL:"
find "$BASE/modulos/visual" "$BASE/modulos/sentinel" -type f 2>/dev/null | head -5 | sed "s|$BASE|.|"
echo ""

echo "🎬 VÍDEOS/ÁUDIO:"
find "$BASE/modulos/videos" "$BASE/modulos/audio" -type f 2>/dev/null | head -5 | sed "s|$BASE|.|"
echo ""

echo "🔬 CORE (projeto principal):"
find "$BASE/core/arcturus" -maxdepth 1 -type d 2>/dev/null | head -10 | sed "s|$BASE|.|"
echo ""

echo "══════════════════════════════════════════════════════════════"
echo "✅ INVENTÁRIO CONCLUÍDO"
echo "══════════════════════════════════════════════════════════════"
