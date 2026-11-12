CREATE TABLE IF NOT EXISTS assinatura_hidrologica (
    id SERIAL PRIMARY KEY,
    evento_id TEXT UNIQUE NOT NULL,
    chuva_24h_mm DOUBLE PRECISION,
    chuva_72h_mm DOUBLE PRECISION,
    chuva_7d_mm DOUBLE PRECISION,
    api_7d DOUBLE PRECISION,
    tempo_ate_subida_h DOUBLE PRECISION,
    tempo_ate_pico_h DOUBLE PRECISION,
    cota_max_cm DOUBLE PRECISION,
    vz_max_cm_h DOUBLE PRECISION,
    criado_em TIMESTAMP DEFAULT NOW()
);
