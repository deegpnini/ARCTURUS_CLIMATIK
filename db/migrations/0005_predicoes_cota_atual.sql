-- Migração 0005: Adiciona cota_atual na predicoes_shadow
-- Data: 02/11/2026
-- Motivo: A cota usada na predição deve ser auditável (além do JSONB)

ALTER TABLE predicoes_shadow ADD COLUMN IF NOT EXISTS cota_atual double precision;
COMMENT ON COLUMN predicoes_shadow.cota_atual IS 'Cota em cm usada como ponto de partida para o delta previsto.';
