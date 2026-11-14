#!/usr/bin/env python3
"""
ARCTURUS_CLIMATIK — Auditoria Rigorosa do Modelo v11c
Executa os 4 testes de estresse antes da promoção para Modo Sombra:
  1. Vazamento Temporal (Target Leakage & Correlação Espúria)
  2. Ablação de Chuva Futura (Proxy/Oracle Leakage)
  3. Estabilidade Temporal / Viés Sazonal (3 Folds Temporais)
  4. Desempenho em Regime de Cheia (Picos > p90 = 145 cm)
"""

import json
import pickle
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR / "src" / "modelo"))

from treinar_v11c import (
    SEED,
    carregar_estatisticas_historicas_ana,
    gerar_treino_aumentado_3x,
    preparar_dataset_treino,
)

MODEL_DIR = BASE_DIR / "models" / "v11c"


def avalia_metricas(y_cota_atual: np.ndarray, y_cota_real: np.ndarray, delta_pred: np.ndarray) -> dict:
    cota_pred = y_cota_atual + delta_pred
    rmse = float(np.sqrt(mean_squared_error(y_cota_real, cota_pred)))
    mae = float(mean_absolute_error(y_cota_real, cota_pred))
    rmse_pers = float(np.sqrt(mean_squared_error(y_cota_real, y_cota_atual)))
    mae_pers = float(mean_absolute_error(y_cota_real, y_cota_atual))
    ganho = (1.0 - rmse / max(rmse_pers, 1e-6)) * 100.0
    return {
        "rmse": round(rmse, 2),
        "mae": round(mae, 2),
        "rmse_pers": round(rmse_pers, 2),
        "mae_pers": round(mae_pers, 2),
        "ganho_pct": round(ganho, 2),
    }


def treinar_lgb_rapido(X_tr, y_tr, X_va, y_va) -> lgb.LGBMRegressor:
    m = lgb.LGBMRegressor(
        n_estimators=700,
        learning_rate=0.025,
        num_leaves=23,
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
    m.fit(
        X_tr,
        y_tr,
        eval_set=[(X_va, y_va)],
        callbacks=[lgb.early_stopping(stopping_rounds=60, verbose=False)],
    )
    return m


def main():
    print("=" * 72)
    print(" AUDITORIA DE ESTRESSE — MODELO v11c (LIGHTGBM + CHUVA FUTURA)")
    print("=" * 72)

    stats_ana = carregar_estatisticas_historicas_ana()
    df, features = preparar_dataset_treino(stats_ana)

    with open(MODEL_DIR / "modelo_v11c_lgbm.pkl", "rb") as f:
        modelo_salvo = pickle.load(f)

    manifesto = json.loads((MODEL_DIR / "manifesto_v11c.json").read_text(encoding="utf-8"))

    # =========================================================================
    # TESTE 1: VAZAMENTO TEMPORAL (TARGET LEAKAGE)
    # =========================================================================
    print("\n[TESTE 1] VAZAMENTO TEMPORAL (Target Leakage & Correlações > 0.85)")
    print("-" * 72)

    suspeitas_nome = [
        f for f in features
        if any(k in f.lower() for k in ["target", "t1", "futuro", "lead"])
    ]
    print(f"Features com nomes suspeitos de futuro: {suspeitas_nome}")

    corrs = {}
    for f in features:
        c = df[f].corr(df["target_delta_cota_1d"])
        if pd.notna(c):
            corrs[f] = float(c)

    top_corrs = sorted(corrs.items(), key=lambda x: abs(x[1]), reverse=True)[:10]
    print("Top 10 correlações absolutas com o alvo (target_delta_cota_1d):")
    vazamento_t1 = False
    for feat, r in top_corrs:
        flag = " <--- [ALERTA: > 0.90]" if abs(r) > 0.90 else ""
        if abs(r) > 0.95:
            vazamento_t1 = True
        print(f"  - {feat:<38s}: r = {r:+.4f}{flag}")

    # Verifica especificamente se ana_vz_m_d ou ana_az_m_d2 usam cota futura (t+1 - t) vs passada (t - t-1)
    diff_vz = (df["ana_vz_m_d"] - df["target_delta_cota_1d"]).abs().max()
    print(f"Diferença máxima |ana_vz_m_d - target_delta_cota_1d|: {diff_vz:.4f}")
    if diff_vz < 1e-3:
        print("  [CRÍTICO] ana_vz_m_d é idêntica ao alvo t+1! Vazamento confirmado.")
        vazamento_t1 = True
    else:
        print("  [OK] ana_vz_m_d não é cópia direta do alvo t+1.")

    status_t1 = "REPROVADO" if vazamento_t1 else "APROVADO"
    print(f"Veredito Teste 1: {status_t1}")

    # =========================================================================
    # TESTE 2: ABLAÇÃO DE CHUVA FUTURA (PROXY / ORACLE LEAKAGE)
    # =========================================================================
    print("\n[TESTE 2] ABLAÇÃO DE CHUVA FUTURA (Quanto vem da física vs. oráculo?)")
    print("-" * 72)

    idx_corte = int(len(df) * 0.80)
    tr, va = df.iloc[:idx_corte], df.iloc[idx_corte:]

    # 2A. Modelo completo (com prev_chuva_*)
    tr_aug = gerar_treino_aumentado_3x(tr)
    m_full = treinar_lgb_rapido(tr_aug[features], tr_aug["target_delta_cota_1d"], va[features], va["target_delta_cota_1d"])
    res_full = avalia_metricas(va["ana_cota_m"].values, va["target_cota_t1"].values, m_full.predict(va[features]))

    # 2B. Modelo SEM prev_chuva_* (apenas observações até o instante t)
    feats_sem_prev = [f for f in features if not f.startswith("prev_chuva_")]
    m_sem_prev = treinar_lgb_rapido(
        tr[feats_sem_prev], tr["target_delta_cota_1d"], va[feats_sem_prev], va["target_delta_cota_1d"]
    )
    res_sem_prev = avalia_metricas(
        va["ana_cota_m"].values, va["target_cota_t1"].values, m_sem_prev.predict(va[feats_sem_prev])
    )

    # 2C. Teste de degradação com erro realista de previsão (+40% ruído + viés de 25%)
    va_ruido = va.copy()
    rng_aud = np.random.default_rng(999)
    for col_p in [c for c in features if c.startswith("prev_chuva_")]:
        orig = va_ruido[col_p].values.copy()
        va_ruido[col_p] = np.clip(
            orig * rng_aud.normal(0.85, 0.40, size=len(va_ruido)) + rng_aud.normal(0, 3.0, size=len(va_ruido)),
            0.0,
            None,
        )
        if col_p == "prev_chuva_24h_media_mm" and "div_modelos_mm" in va_ruido.columns:
            va_ruido["div_modelos_mm"] = np.abs(va_ruido[col_p].values - orig) + 2.5
    res_ruido_pesado = avalia_metricas(
        va["ana_cota_m"].values, va["target_cota_t1"].values, m_full.predict(va_ruido[features])
    )

    print(f"  - Baseline Persistência : RMSE = {res_full['rmse_pers']} cm | MAE = {res_full['mae_pers']} cm")
    print(f"  - v11c Completo (proxy) : RMSE = {res_full['rmse']} cm | MAE = {res_full['mae']} cm (Ganho: {res_full['ganho_pct']:+.2f}%)")
    print(f"  - v11c SEM chuva futura : RMSE = {res_sem_prev['rmse']} cm | MAE = {res_sem_prev['mae']} cm (Ganho: {res_sem_prev['ganho_pct']:+.2f}%)")
    print(f"  - v11c Previsão Ruidosa : RMSE = {res_ruido_pesado['rmse']} cm | MAE = {res_ruido_pesado['mae']} cm (Ganho: {res_ruido_pesado['ganho_pct']:+.2f}%)")

    print("\n  Top 10 Features mais importantes no modelo salvo:")
    for item in manifesto["top_10_features"]:
        print(f"    * {item['feature']:<38s}: {item['importancia']} splits")

    # =========================================================================
    # TESTE 3: VIÉS SAZONAL / ESTABILIDADE EM 3 FOLDS TEMPORAIS (EXPANDING)
    # =========================================================================
    print("\n[TESTE 3] ESTABILIDADE TEMPORAL (3 Folds Expansivos / Sazonalidade)")
    print("-" * 72)

    n = len(df)
    cortes = [
        ("Fold 1 (Val ~2024-H2)", int(n * 0.35), int(n * 0.55)),
        ("Fold 2 (Val ~2025-H1)", int(n * 0.55), int(n * 0.78)),
        ("Fold 3 (Val ~2025-H2/26)", int(n * 0.78), n),
    ]

    ganhos_folds = []
    for nome_f, ini_v, fim_v in cortes:
        f_tr = df.iloc[:ini_v]
        f_va = df.iloc[ini_v:fim_v]
        f_tr_aug = gerar_treino_aumentado_3x(f_tr)
        mf = treinar_lgb_rapido(f_tr_aug[features], f_tr_aug["target_delta_cota_1d"], f_va[features], f_va["target_delta_cota_1d"])
        rf = avalia_metricas(f_va["ana_cota_m"].values, f_va["target_cota_t1"].values, mf.predict(f_va[features]))
        ganhos_folds.append(rf["ganho_pct"])
        print(
            f"  - {nome_f:<25s} [{f_va.index.min().date()} a {f_va.index.max().date()}] | "
            f"RMSE={rf['rmse']} vs Pers={rf['rmse_pers']} ({rf['ganho_pct']:+.2f}%)"
        )

    status_t3 = "APROVADO" if all(g > 0 for g in ganhos_folds) else "ATENÇÃO (instável entre períodos)"
    print(f"Veredito Teste 3: {status_t3}")

    # =========================================================================
    # TESTE 4: DESEMPENHO EM REGIME DE CHEIA (PICOS > p90 = 145 cm)
    # =========================================================================
    print("\n[TESTE 4] DESEMPENHO NOS PICOS / CHEIAS (Cota atual ou t+1 > p90 = 145 cm)")
    print("-" * 72)

    p90 = stats_ana["p90"]
    preds_va = m_full.predict(va[features])
    mask_cheia = (va["ana_cota_m"] > p90) | (va["target_cota_t1"] > p90)
    mask_calmo = ~mask_cheia

    n_cheia = int(mask_cheia.sum())
    n_calmo = int(mask_calmo.sum())

    res_calmo = avalia_metricas(
        va.loc[mask_calmo, "ana_cota_m"].values,
        va.loc[mask_calmo, "target_cota_t1"].values,
        preds_va[mask_calmo],
    )
    print(f"  - Regime Normal (<= {p90} cm, n={n_calmo}): RMSE={res_calmo['rmse']} cm vs Pers={res_calmo['rmse_pers']} cm ({res_calmo['ganho_pct']:+.2f}%)")

    if n_cheia > 0:
        res_cheia = avalia_metricas(
            va.loc[mask_cheia, "ana_cota_m"].values,
            va.loc[mask_cheia, "target_cota_t1"].values,
            preds_va[mask_cheia],
        )
        erros_abs_cheia = np.abs((va.loc[mask_cheia, "ana_cota_m"].values + preds_va[mask_cheia]) - va.loc[mask_cheia, "target_cota_t1"].values)
        erro_max_cheia = float(np.max(erros_abs_cheia))
        print(f"  - Regime Cheia  (>  {p90} cm, n={n_cheia}): RMSE={res_cheia['rmse']} cm vs Pers={res_cheia['rmse_pers']} cm ({res_cheia['ganho_pct']:+.2f}%)")
        print(f"  - Maior erro absoluto em dia de cheia na validação: {erro_max_cheia:.2f} cm")
        status_t4 = "APROVADO" if res_cheia["rmse"] < res_cheia["rmse_pers"] else "REPROVADO (pior que persistência na cheia)"
    else:
        print("  - [AVISO] Nenhum dia > p90 na janela de validação atual.")
        status_t4 = "INCONCLUSIVO (sem cheias na validação)"

    print(f"Veredito Teste 4: {status_t4}")
    print("=" * 72)


if __name__ == "__main__":
    main()
