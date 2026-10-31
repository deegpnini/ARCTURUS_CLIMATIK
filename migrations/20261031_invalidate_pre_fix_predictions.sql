BEGIN;

ALTER TABLE predicoes_shadow
    ADD COLUMN IF NOT EXISTS valido boolean NOT NULL DEFAULT true;

UPDATE predicoes_shadow
SET valido = false
WHERE timestamp < TIMESTAMP '2026-10-31 14:30:00'
  AND valido IS DISTINCT FROM false;

COMMIT;
