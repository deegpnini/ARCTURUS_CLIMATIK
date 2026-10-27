# Contexto de Retomada — ARCTURUS CLIMATIK (28/10/2026)

## Estado Atual
- **Regime:** NORMAL (72 cm, Vz 0.0 cm/h).
- **Commit mais recente:** `09c7931` (docs: relatório executivo, plano de prioridades e QC log).
- **Cron:** rodando a cada 15 min (WSL/Windows sem sleep).
- **XERJ:** integrado ao VS Code (MCP), indexado com `src/` (ax) e `tools/` (tools).

## Prioridades de Hoje (28/10)
1. **P1 — `vz_robusto`:** implementar a função Theil-Sen (janela ≥30 min, confirmação em 2 ciclos) no `monitor_derivada.py`.
2. **P2 — `qc_flag`:** marcar o pico de 127 cm como `SUSPEITO` no CSV/JSON (não apagar).
3. **P3 — E-mail à Tubarão Saneamento:** pedir autorização da câmera + calibração ERAB.

## Decisões Metodológicas (Mestra)
- Não apagar dados suspeitos (marcar `qc_flag`).
- Não publicar números não validados (2 prédios afetados é inconclusivo).
- Vz com 2 pontos é ruído; usar `vz_robusto`.

## Arquivos-Chave
- `docs/RELATORIO_EXECUTIVO_27OUT2026.md`
- `docs/PLANO_PRIORIDADES_SEMANA.md`
- `docs/QC_LOG.md`
- `src/relatorios/vz_robusto.py` (criado, mas não integrado)
- `data/regime_atual.json` (estado atual)
