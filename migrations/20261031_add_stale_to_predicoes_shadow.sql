ALTER TABLE predicoes_shadow
    ADD COLUMN IF NOT EXISTS stale boolean NOT NULL DEFAULT false;
