#!/usr/bin/env python3
"""
ARCTURUS_CLIMATIK — Treino Recalibrado do Modelo v11c (LightGBM + Noise-Augmented Training)
Blindagem contra ruído meteorológico:
  1. Treino base com dataset_treino_ana_preparado.parquet + climatologia 1939-2026.
  2. Data Augmentation 3x no treino com ruído realista (30% base, variando 15% a 45%).
  3. Feature explícita de incerteza/divergência entre modelos (div_modelos_mm).
  4. Validação temporal limpa (sem augmentation) e agregação out-of-time (72h).
"""

import json
import pickle
from datetime import datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models" / "v11c"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

SEED = 42


def carregar_estatisticas_historicas_ana() -> dict:
    """Extrai percentis históricos (1939-2026) de ana_longa84580000.csv para normalização de regime."""
    arq_longa = DATA_DIR / "ana_longa84580000.csv"
    if not arq_longa.exists():
        return {"p50": 58.0, "p90": 145.0, "p99": 306.0, "max": 746.0}

    df_longa = pd.read_csv(arq_longa)
    col_cota = [c for c in df_longa.columns if "cota" in c.lower()][0]
    cotas = pd.to_numeric(df_longa[col_cota], errors="coerce").dropna()
    return {
        "p50": float(np.percentile(cotas, 50)),
        "p90": float(np.percentile(cotas, 90)),
        "p99": float(np.percentile(cotas, 99)),
        "max": float(cotas.max()),
        "n_dias": int(len(cotas)),
    }


def _injetar_previsao_ruidosa(
    df_base: pd.DataFrame,
    rng: np.random.Generator,
    fator_incerteza: float = 0.30,
) -> pd.DataFrame:
    """Gera uma realização ruidosa das features de chuva futura e divergência explícita."""
    out = df_base.copy()

    chuva_t1 = out["_raw_chuva_t1"]
    chuva_t2 = out["_raw_chuva_t2"]
    chuva_t3 = out["_raw_chuva_t3"]
    chuva_max_t1 = out["_raw_chuva_max_t1"]

    def simular(serie: pd.Series, scale: float) -> tuple[pd.Series, np.ndarray]:
        ruido_mult = rng.normal(loc=1.0, scale=scale, size=len(serie))
        ruido_adit = rng.normal(loc=0.0, scale=2.5 * scale, size=len(serie))
        sim = np.where(serie > 0.2, serie * ruido_mult + ruido_adit, np.maximum(0.0, ruido_adit * 0.4))
        sim_clip = np.clip(sim, 0.0, None)
        erro_abs = np.abs(sim_clip - serie.values)
        return pd.Series(sim_clip, index=serie.index), erro_abs

    prev_24h, err_24h = simular(chuva_t1, fator_incerteza)
    prev_d2, _ = simular(chuva_t2, fator_incerteza * 1.25)
    prev_d3, _ = simular(chuva_t3, fator_incerteza * 1.50)
    prev_pior, err_pior = simular(chuva_max_t1, fator_incerteza * 1.15)

    out["prev_chuva_24h_media_mm"] = prev_24h
    out["prev_chuva_48h_acum_mm"] = prev_24h + prev_d2
    out["prev_chuva_72h_acum_mm"] = prev_24h + prev_d2 + prev_d3
    out["prev_chuva_24h_pior_caso_mm"] = prev_pior

    # Feature explícita de incerteza/divergência entre modelos (equivalente a div_horaria no CSV triplo)
    # Combina a amplitude do erro simulado com o spread entre pior caso e média
    spread_modelos = np.abs(prev_pior.values - prev_24h.values)
    out["div_modelos_mm"] = np.round(0.5 * (err_24h + err_pior) + 0.5 * spread_modelos, 3)

    return out


def preparar_dataset_treino(stats_ana: dict) -> tuple[pd.DataFrame, list[str]]:
    """Carrega o parquet da ANA e prepara o dataset base com ruído padrão de 30%."""
    rng = np.random.default_rng(SEED)
    arq_parquet = DATA_DIR / "dataset_treino_ana_preparado.parquet"
    df = pd.read_parquet(arq_parquet).sort_index()

    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)

    cols_chuva_base = [
        c for c in df.columns
        if c.startswith("openmeteo_chuva_") and c.endswith("_mm") and "_lag" not in c
    ]
    if not cols_chuva_base:
        cols_chuva_base = [c for c in df.columns if "chuva" in c.lower() and "lag" not in c.lower()]

    df["bacia_chuva_media_mm"] = df[cols_chuva_base].mean(axis=1)
    df["bacia_chuva_max_mm"] = df[cols_chuva_base].max(axis=1)

    # Colunas auxiliares brutas para permitir data augmentation multi-ruído sem data leakage
    df["_raw_chuva_t1"] = df["bacia_chuva_media_mm"].shift(-1)
    df["_raw_chuva_t2"] = df["bacia_chuva_media_mm"].shift(-2)
    df["_raw_chuva_t3"] = df["bacia_chuva_media_mm"].shift(-3)
    df["_raw_chuva_max_t1"] = df["bacia_chuva_max_mm"].shift(-1)

    # Climatologia de 87 anos da ANA
    df["cota_norm_p90"] = df["ana_cota_m"] / max(stats_ana["p90"], 0.1)
    df["mes_sin"] = np.sin(2 * np.pi * df.index.month / 12.0)
    df["mes_cos"] = np.cos(2 * np.pi * df.index.month / 12.0)

    # Alvo (t+1): variação de cota no dia seguinte
    df["target_cota_t1"] = df["ana_cota_m"].shift(-1)
    df["target_delta_cota_1d"] = df["target_cota_t1"] - df["ana_cota_m"]

    df_limpo = df.dropna(subset=["target_delta_cota_1d", "_raw_chuva_t3"]).copy()
    df_limpo = _injetar_previsao_ruidosa(df_limpo, rng=rng, fator_incerteza=0.30)

    cols_excluir = {
        "target_cota_t1",
        "target_delta_cota_1d",
        "_raw_chuva_t1",
        "_raw_chuva_t2",
        "_raw_chuva_t3",
        "_raw_chuva_max_t1",
    }
    features = [
        c for c in df_limpo.columns
        if c not in cols_excluir and pd.api.types.is_numeric_dtype(df_limpo[c])
    ]

    return df_limpo, features


def gerar_treino_aumentado_3x(train_df: pd.DataFrame) -> pd.DataFrame:
    """Cria 3 realizações de ruído (15%, 30% e 45%) exclusivamente no split de treino."""
    rng_aug = np.random.default_rng(SEED + 100)
    if "_raw_chuva_t1" not in train_df.columns:
        return train_df

    partes = [
        _injetar_previsao_ruidosa(train_df, rng=rng_aug, fator_incerteza=0.15),
        _injetar_previsao_ruidosa(train_df, rng=rng_aug, fator_incerteza=0.30),
        _injetar_previsao_ruidosa(train_df, rng=rng_aug, fator_incerteza=0.45),
    ]
    return pd.concat(partes, axis=0)


def treinar_modelo(df: pd.DataFrame, features: list[str]) -> tuple[lgb.LGBMRegressor, dict]:
    """Treina o LightGBM v11c com Data Augmentation 3x no treino e validação temporal limpa."""
    n_total = len(df)
    idx_corte = int(n_total * 0.80)

    train_base = df.iloc[:idx_corte]
    val_df = df.iloc[idx_corte:]  # 1 realização limpa (30% ruído), sem duplicatas

    train_aug = gerar_treino_aumentado_3x(train_base)

    X_train, y_train = train_aug[features], train_aug["target_delta_cota_1d"]
    X_val, y_val = val_df[features], val_df["target_delta_cota_1d"]

    modelo = lgb.LGBMRegressor(
        n_estimators=700,
        learning_rate=0.025,
        num_leaves=23,             # Regularização extra para evitar overfitting em picos de ruído
        min_child_samples=25,
        subsample_for_bin=500,
        colsample_bytree=0.75,
        subsample=0.80,
        subsample_freq=1,
        reg_alpha=1.0,
        reg_lambda=2.0,
        random_state=SEED,
        verbose=-1,
    )

    modelo.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=60, verbose=False)],
    )

    pred_delta_val = modelo.predict(X_val)
    pred_cota_val = val_df["ana_cota_m"].values + pred_delta_val
    real_cota_val = val_df["target_cota_t1"].values

    rmse_cota = float(np.sqrt(mean_squared_error(real_cota_val, pred_cota_val)))
    mae_cota = float(mean_absolute_error(real_cota_val, pred_cota_val))

    rmse_persist = float(np.sqrt(mean_squared_error(real_cota_val, val_df["ana_cota_m"].values)))
    mae_persist = float(mean_absolute_error(real_cota_val, val_df["ana_cota_m"].values))

    metricas = {
        "n_treino_base": int(len(train_base)),
        "n_treino_aumentado_3x": int(len(train_aug)),
        "n_val_interna": int(len(val_df)),
        "periodo_treino": f"{train_base.index.min().date()} a {train_base.index.max().date()}",
        "periodo_val": f"{val_df.index.min().date()} a {val_df.index.max().date()}",
        "rmse_cota_m": round(rmse_cota, 4),
        "mae_cota_m": round(mae_cota, 4),
        "rmse_persistencia_m": round(rmse_persist, 4),
        "mae_persistencia_m": round(mae_persist, 4),
        "ganho_rmse_pct": round((1 - rmse_cota / max(rmse_persist, 1e-6)) * 100, 2),
    }

    return modelo, metricas


def preparar_validacao_out_of_time() -> pd.DataFrame:
    """Agrega previsao_chuva_tripla.csv (72h horárias) incluindo div_modelos_mm."""
    arq_prev = DATA_DIR / "previsao_chuva_tripla.csv"
    df_prev = pd.read_csv(arq_prev)
    df_prev["timestamp"] = pd.to_datetime(df_prev["timestamp"])
    df_prev = df_prev.sort_values("timestamp").set_index("timestamp")

    diario = df_prev.resample("1D").agg(
        prev_chuva_24h_media_mm=("chuva_media_mm", "sum"),
        prev_chuva_24h_pior_caso_mm=("chuva_pior_caso_mm", "sum"),
        ecmwf_24h_mm=("chuva_ecmwf_ifs025_mm", "sum"),
        gfs_24h_mm=("chuva_gfs_global_mm", "sum"),
        ukmo_24h_mm=("chuva_ukmo_global_deterministic_10km_mm", "sum"),
        div_modelos_mm=("div_horaria", "sum"),
    )

    diario["prev_chuva_48h_acum_mm"] = diario["prev_chuva_24h_media_mm"].rolling(2, min_periods=1).sum()
    diario["prev_chuva_72h_acum_mm"] = diario["prev_chuva_24h_media_mm"].rolling(3, min_periods=1).sum()

    saida_oot = MODEL_DIR / "validacao_oot_72h_agregada.csv"
    diario.to_csv(saida_oot)
    return diario


def main():
    print("=" * 68)
    print(" ARCTURUS — RETREINO v11c (NOISE-AUGMENTED 3X + INCERTEZA EXPLÍCITA)")
    print("=" * 68)

    stats_ana = carregar_estatisticas_historicas_ana()
    print(f"[1/4] Climatologia ANA (1939-2026): {stats_ana}")

    df_treino, features = preparar_dataset_treino(stats_ana)
    print(f"[2/4] Dataset base: {df_treino.shape[0]} amostras | {len(features)} features (inclui div_modelos_mm)")

    modelo, metricas = treinar_modelo(df_treino, features)
    print("[3/4] Métricas Validação Temporal Interna (com ruído 30%):")
    for k, v in metricas.items():
        print(f"      - {k}: {v}")

    arq_modelo = MODEL_DIR / "modelo_v11c_lgbm.pkl"
    with open(arq_modelo, "wb") as f:
        pickle.dump(modelo, f)

    importancias = sorted(
        zip(features, modelo.feature_importances_),
        key=lambda x: x[1],
        reverse=True,
    )[:10]

    manifesto = {
        "versao": "v11c_noise_augmented_3x",
        "treinado_em": datetime.now().isoformat(),
        "features": features,
        "n_features": len(features),
        "climatologia_ana": stats_ana,
        "metricas_validacao": metricas,
        "top_10_features": [{"feature": f, "importancia": int(imp)} for f, imp in importancias],
    }
    (MODEL_DIR / "manifesto_v11c.json").write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    df_oot = preparar_validacao_out_of_time()
    print("[4/4] Janela Out-of-Time (13/11 a 15/11) agregada com div_modelos_mm:")
    print(df_oot[["prev_chuva_24h_media_mm", "prev_chuva_24h_pior_caso_mm", "div_modelos_mm", "prev_chuva_72h_acum_mm"]])
    print("=" * 68)
    print(f"[OK] Artefatos recalibrados salvos em: {MODEL_DIR}")


if __name__ == "__main__":
    main()
