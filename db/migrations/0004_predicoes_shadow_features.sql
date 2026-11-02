-- Migração 0004: Adiciona coluna features (JSONB) na predicoes_shadow
-- Data: 02/11/2026
-- Motivo: O features_hash guarda só o hash; para auditoria, é preciso guardar os valores das features.

ALTER TABLE predicoes_shadow ADD COLUMN IF NOT EXISTS features jsonb;
COMMENT ON COLUMN predicoes_shadow.features IS 'JSON com os valores das features usadas na predição (para auditoria).';
