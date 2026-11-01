-- Migração 0003: fases do experimento e motivo de invalidação em predicoes_shadow
-- Data: 01/11/2026. Idempotente.
-- Critério por REGRA (data de corte), nunca por desempenho: o pipeline ainda não tinha
-- versão fixa, havia lags com leituras SUSPEITO, chuva defasada e backfill com bug.

ALTER TABLE predicoes_shadow ADD COLUMN IF NOT EXISTS fase text;
ALTER TABLE predicoes_shadow ADD COLUMN IF NOT EXISTS motivo_invalidacao text;

UPDATE predicoes_shadow SET fase = 'PILOTO' WHERE fase IS NULL AND timestamp < '2026-11-01 14:00';
-- até a tag pipeline-congelado-v1, nada é PROSPECTIVO:
UPDATE predicoes_shadow SET fase = 'PILOTO_II' WHERE fase IS NULL OR fase = 'PROSPECTIVO';
UPDATE predicoes_shadow SET motivo_invalidacao = 'pipeline_pre_congelamento' WHERE fase = 'PILOTO';

ALTER TABLE predicoes_shadow ALTER COLUMN fase SET DEFAULT 'PILOTO_II';
