#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1
TS="$(date +%Y%m%d_%H%M%S)"
LOG="resultados/refatoracao_raiz_${TS}.log"
mkdir -p resultados tools/auditoria tools/ops tools/coleta src/coleta src/atlas src/apps src/ops historico/experimentos
echo "=== ARCTURUS — Refatoração da raiz ===" | tee "$LOG"
echo "Root: $ROOT" | tee -a "$LOG"
echo "Modo: $([ $APPLY -eq 1 ] && echo APPLY || echo DRY-RUN)" | tee -a "$LOG"
KEEP=(README.md LICENSE AGENTS.md .gitignore .gitattributes .env.example requirements.txt requirements.lock INVENTARIO.sh)
is_keep() { local f="$1"; for k in "${KEEP[@]}"; do [[ "$f" == "$k" ]] && return 0; done; return 1; }
declare -A MAP=(
  [ana_auth.py]="src/coleta/ana_auth.py"
  [puxar_historico_ana.py]="src/coleta/puxar_historico_ana.py"
  [coleta_incremental.py]="src/coleta/coleta_incremental.py"
  [coletar_telemetria.py]="src/coleta/coletar_telemetria.py"
  [coletor_historico.py]="src/coleta/coletor_historico.py"
  [baixar_chuva_bacia.py]="src/coleta/baixar_chuva_bacia.py"
  [baixar_open_buildings.py]="src/coleta/baixar_open_buildings.py"
  [recuperar_gaps.py]="src/coleta/recuperar_gaps.py"
  [consolidar_recuperados.py]="src/coleta/consolidar_recuperados.py"
  [consolidar_v2.py]="src/coleta/consolidar_v2.py"
  [reconsolidar.py]="src/coleta/reconsolidar.py"
  [build_dataset.py]="src/coleta/build_dataset.py"
  [normalizador.py]="src/coleta/normalizador.py"
  [normalizar_cotas.py]="src/coleta/normalizar_cotas.py"
  [mask_disponibilidade.py]="src/coleta/mask_disponibilidade.py"
  [ml_baseline.py]="src/modelo/ml_baseline.py"
  [benchmark_oficial.py]="src/modelo/benchmark_oficial.py"
  [detectar_eventos.py]="src/modelo/detectar_eventos.py"
  [detector_eventos_v2.py]="src/modelo/detector_eventos_v2.py"
  [listar_28_eventos.py]="src/modelo/listar_28_eventos.py"
  [check_split.py]="src/modelo/check_split.py"
  [retomar_validacao.py]="src/modelo/retomar_validacao.py"
  [persistir_shadow.py]="src/modelo/persistir_shadow.py"
  [previsao_log.py]="src/modelo/previsao_log.py"
  [selecionar_candidatas.py]="src/modelo/selecionar_candidatas.py"
  [captura_evento_2109.py]="src/modelo/captura_evento_2109.py"
  [exportar_mancha_kml.py]="src/atlas/exportar_mancha_kml.py"
  [gerar_relatorio_impacto.py]="src/atlas/gerar_relatorio_impacto.py"
  [avaliar_dano_inundacao_v6.py]="src/atlas/avaliar_dano_inundacao_v6.py"
  [avaliar_dano_manual.py]="src/atlas/avaliar_dano_manual.py"
  [mapear_risco_gee.py]="src/atlas/mapear_risco_gee.py"
  [mancha_inundacao.geojson]="data/geo/mancha_inundacao.geojson"
  [mancha_inundacao.kml]="data/geo/mancha_inundacao.kml"
  [app_dash.py]="src/apps/app_dash.py"
  [painel_controle.py]="src/apps/painel_controle.py"
  [arcturus.py]="src/apps/arcturus.py"
  [arcturus_hidro.py]="src/apps/arcturus_hidro.py"
  [arcturus_relatos.py]="src/apps/arcturus_relatos.py"
  [arcturus_sar.py]="src/apps/arcturus_sar.py"
  [arcturus_sar_local.py]="src/apps/arcturus_sar_local.py"
  [arcturus_sismico.py]="src/apps/arcturus_sismico.py"
  [relatorio_risco.py]="src/apps/relatorio_risco.py"
  [email_tubarao.html]="src/apps/email_tubarao.html"
  [bot_telegram.py]="src/ops/bot_telegram.py"
  [bot_v6.py]="src/ops/bot_v6.py"
  [bot_v7.py]="src/ops/bot_v7.py"
  [monitor_agora.py]="src/ops/monitor_agora.py"
  [monitor_critico.py]="src/ops/monitor_critico.py"
  [auditar_datasets.py]="tools/auditoria/auditar_datasets.py"
  [auditar_itajai_ararangua.py]="tools/auditoria/auditar_itajai_ararangua.py"
  [auditar_picos.py]="tools/auditoria/auditar_picos.py"
  [auditar_split_v3.py]="tools/auditoria/auditar_split_v3.py"
  [auditoria_ancoras.py]="tools/auditoria/auditoria_ancoras.py"
  [auditoria_fina.py]="tools/auditoria/auditoria_fina.py"
  [auditoria_pre_treino.py]="tools/auditoria/auditoria_pre_treino.py"
  [auditoria_v3.py]="tools/auditoria/auditoria_v3.py"
  [analisa_ana.py]="tools/auditoria/analisa_ana.py"
  [analisa_lag_diferenciado.py]="tools/auditoria/analisa_lag_diferenciado.py"
  [descobrir_itajai_ararangua.py]="tools/auditoria/descobrir_itajai_ararangua.py"
  [cron_motor.sh]="tools/ops/cron_motor.sh"
  [deploy_dashboard.sh]="tools/ops/deploy_dashboard.sh"
  [backup_diario.sh]="tools/ops/backup_diario.sh"
  [gerar_backup_completo.sh]="tools/ops/gerar_backup_completo.sh"
  [health_check.sh]="tools/ops/health_check.sh"
)
MOVED=0; SKIPPED=0; MISSING=0
move_one() {
  local src="$1" dst="$2"
  if [[ ! -e "$src" ]]; then echo "  [skip] não existe: $src" | tee -a "$LOG"; MISSING=$((MISSING+1)); return; fi
  if is_keep "$src"; then echo "  [keep] $src" | tee -a "$LOG"; SKIPPED=$((SKIPPED+1)); return; fi
  mkdir -p "$(dirname "$dst")"
  if [[ $APPLY -eq 0 ]]; then echo "  [dry] $src -> $dst" | tee -a "$LOG"; MOVED=$((MOVED+1)); return; fi
  if git ls-files --error-unmatch "$src" >/dev/null 2>&1; then git mv -f "$src" "$dst"; echo "  [git mv] $src -> $dst" | tee -a "$LOG"; else mv -f "$src" "$dst"; echo "  [mv] $src -> $dst" | tee -a "$LOG"; fi
  MOVED=$((MOVED+1))
}
echo "--- Movimentações planejadas ---" | tee -a "$LOG"
for src in "${!MAP[@]}"; do move_one "$src" "${MAP[$src]}"; done
echo "" | tee -a "$LOG"
echo "--- Catch-all: .py restantes na raiz ---" | tee -a "$LOG"
shopt -s nullglob
for f in *.py; do
  is_keep "$f" && continue
  [[ -n "${MAP[$f]+x}" ]] && continue
  move_one "$f" "historico/experimentos/$f"
done
for f in *.sh; do
  [[ "$f" == "INVENTARIO.sh" ]] && continue
  [[ -n "${MAP[$f]+x}" ]] && continue
  move_one "$f" "tools/ops/$f"
done
echo "" | tee -a "$LOG"
echo "=== Resumo ===" | tee -a "$LOG"
echo "Movidos (ou planejados): $MOVED" | tee -a "$LOG"
echo "Mantidos/skip: $SKIPPED" | tee -a "$LOG"
echo "Não encontrados: $MISSING" | tee -a "$LOG"
echo "Log: $LOG" | tee -a "$LOG"
