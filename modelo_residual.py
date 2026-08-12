# ============================================================
# ARCTURUS CLIMATIK — MODELO RESIDUAL v2.1
# ============================================================
# Prevê o residual ΔT = T_t - T_{t-1}
# Avalia skill vs persistência
# ============================================================

import argparse
import os
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

warnings.filterwarnings("ignore")


def load_data(csv_path: str) -> pd.DataFrame:
    """Carrega e ordena o dataset."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Arquivo não encontrado: {csv_path}\n"
            "Ajuste o caminho com --data ou coloque o CSV no local esperado."
        )

    df = pd.read_csv(csv_path)
    df["data_hora"] = pd.to_datetime(df["data_hora"])
    df = df.sort_values(["id_estacao_final", "data_hora"]).reset_index(drop=True)
    print(f"✅ Dataset carregado: {len(df):,} registros")
    return df


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Cria lags, residual e features temporais."""
    print("🔧 Criando features...")

    # Lags por estação
    df["temp_lag_1"] = df.groupby("id_estacao_final")["temperatura"].shift(1)
    df["temp_lag_3"] = df.groupby("id_estacao_final")["temperatura"].shift(3)
    df["temp_lag_6"] = df.groupby("id_estacao_final")["temperatura"].shift(6)
    df["temp_lag_12"] = df.groupby("id_estacao_final")["temperatura"].shift(12)

    # Alvo: residual
    df["residual"] = df["temperatura"] - df["temp_lag_1"]

    # Features temporais cíclicas
    df["hora"] = df["data_hora"].dt.hour
    df["mes"] = df["data_hora"].dt.month
    df["dia_semana"] = df["data_hora"].dt.dayofweek

    df["hora_sin"] = np.sin(2 * np.pi * df["hora"] / 24)
    df["hora_cos"] = np.cos(2 * np.pi * df["hora"] / 24)
    df["mes_sin"] = np.sin(2 * np.pi * df["mes"] / 12)
    df["mes_cos"] = np.cos(2 * np.pi * df["mes"] / 12)

    # Umidade (imputação simples + flag)
    if "umidade" in df.columns:
        df["umidade_imputada"] = df.groupby("id_estacao_final")["umidade"].transform(
            lambda x: x.fillna(x.mean())
        )
        df["umidade_flag"] = df["umidade"].isna().astype(int)
    else:
        df["umidade_imputada"] = 0.0
        df["umidade_flag"] = 0

    # Remove linhas sem residual válido
    df = df.dropna(subset=["temperatura", "temp_lag_1", "residual"]).copy()
    print(f"✅ Após limpeza: {len(df):,} registros")
    return df


def get_feature_columns() -> list:
    """
    Features usadas no modelo.
    Importante: temp_lag_1 NÃO entra aqui.
    Ele só é usado para reconstruir a temperatura final.
    """
    return [
        "hora_sin",
        "hora_cos",
        "mes_sin",
        "mes_cos",
        "dia_semana",
        "temp_lag_3",
        "temp_lag_6",
        "temp_lag_12",
        "umidade_imputada",
        "umidade_flag",
    ]


def evaluate(y_true, y_pred, y_pers):
    """Calcula métricas e skill score."""
    rmse_model = np.sqrt(mean_squared_error(y_true, y_pred))
    mae_model = mean_absolute_error(y_true, y_pred)
    rmse_pers = np.sqrt(mean_squared_error(y_true, y_pers))
    mae_pers = mean_absolute_error(y_true, y_pers)

    skill_rmse = 1 - (rmse_model / rmse_pers)
    skill_mae = 1 - (mae_model / mae_pers)

    return {
        "rmse_model": rmse_model,
        "mae_model": mae_model,
        "rmse_pers": rmse_pers,
        "mae_pers": mae_pers,
        "skill_rmse": skill_rmse,
        "skill_mae": skill_mae,
    }


def main(args):
    print("🚀 ARCTURUS CLIMATIK — MODELO RESIDUAL v2.1")
    print("=" * 60)

    # 1. Dados
    df = load_data(args.data)
    df = create_features(df)

    feature_cols = get_feature_columns()

    # 2. Split temporal simples (treino < 2026, teste >= 2026)
    train = df[df["data_hora"] < "2026-01-01"]
    test = df[df["data_hora"] >= "2026-01-01"]

    print(f"\n📊 Split temporal:")
    print(f"  Treino: {len(train):,} registros")
    print(f"  Teste : {len(test):,} registros")

    X_train = train[feature_cols].fillna(0)
    y_train = train["residual"]
    X_test = test[feature_cols].fillna(0)

    # 3. Modelo
    print("\n🧠 Treinando Random Forest...")
    model = RandomForestRegressor(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # 4. Predição
    residual_pred = model.predict(X_test)
    temp_pred = test["temp_lag_1"].values + residual_pred
    y_true = test["temperatura"].values
    y_pers = test["temp_lag_1"].values

    # 5. Métricas
    metrics = evaluate(y_true, temp_pred, y_pers)

    print("\n📊 RESULTADOS (conjunto de teste 2026):")
    print(f"  RMSE Modelo      : {metrics["rmse_model"]:.3f} °C")
    print(f"  RMSE Persistência: {metrics["rmse_pers"]:.3f} °C")
    print(f"  MAE  Modelo      : {metrics["mae_model"]:.3f} °C")
    print(f"  MAE  Persistência: {metrics["mae_pers"]:.3f} °C")
    print(f"  Skill RMSE       : {metrics["skill_rmse"]:.3f}")
    print(f"  Skill MAE        : {metrics["skill_mae"]:.3f}")

    # 6. Salvar modelo
    if args.save_model:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        model_path = output_dir / "modelo_residual.joblib"
        joblib.dump(model, model_path)
        print(f"\n💾 Modelo salvo em: {model_path}")

    print("\n" + "=" * 60)
    print("✅ MODELO RESIDUAL CONCLUÍDO")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARCTURUS CLIMATIK - Modelo Residual")
    parser.add_argument(
        "--data",
        type=str,
        default="arcturus_climatik_final_limpo.csv",
        help="Caminho para o CSV consolidado",
    )
    parser.add_argument(
        "--n_estimators",
        type=int,
        default=200,
        help="Número de árvores",
    )
    parser.add_argument(
        "--max_depth",
        type=int,
        default=12,
        help="Profundidade máxima das árvores",
    )
    parser.add_argument(
        "--save_model",
        action="store_true",
        help="Salva o modelo treinado em .joblib",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="models",
        help="Pasta para salvar o modelo",
    )

    args = parser.parse_args()
    main(args)
