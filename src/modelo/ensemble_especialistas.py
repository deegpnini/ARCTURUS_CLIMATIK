"""ANA-only mixture of experts for next-day mean-daily flood levels.

The operational ERAB datasets are deliberately not imported or read here.
"""
import json
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
)


ROOT = Path(__file__).resolve().parents[2]
ANA_FILE = ROOT / "data" / "ana_longa84580000.csv"
RESULT_FILE = ROOT / "resultados" / "ensemble_especialistas.json"
MODEL_DIR = ROOT / "modelos" / "especialistas"
FLOOD_THRESHOLD_CM = 300.0
LEAD_DAYS = 7
MIN_FOLDS = 4
MIN_TRAIN_SAMPLES = 30
EXPERTS = ("relampago", "gradual", "inverno", "verao")
PARAMS = {
    "objective": "binary",
    "metric": "binary_logloss",
    "learning_rate": 0.03,
    "num_leaves": 7,
    "max_depth": 3,
    "min_data_in_leaf": 10,
    "feature_fraction": 0.9,
    "verbosity": -1,
    "seed": 42,
    "num_threads": 1,
    "deterministic": True,
    "force_col_wise": True,
}

FEATURES = (
    "cota_cm",
    "vz_1d_cm",
    "vz_3d_cm",
    "vz_7d_cm",
    "az_1d_cm_dia",
    "max_cota_3d_cm",
    "max_cota_7d_cm",
    "media_cota_3d_cm",
    "sin_dia_ano",
    "cos_dia_ano",
)


def rotear_especialista(vz_cm_dia, mes):
    """Rota por Vz diário; se não há subida rápida, usa a estação."""
    try:
        rate = float(vz_cm_dia)
    except (TypeError, ValueError):
        rate = math.nan

    if math.isfinite(rate):
        if rate > 50:
            return "relampago"
        if 12 <= rate <= 50:
            return "gradual"
    if mes in (6, 7, 8):
        return "inverno"
    if mes in (12, 1, 2, 3):
        return "verao"
    return None


def _read_ana(path=ANA_FILE):
    """Read the daily ANA series in cm; reject non-ANA schema."""
    source = pd.read_csv(path)
    if "Data" not in source.columns or "Cota (m)" not in source.columns:
        raise ValueError("A fonte de treino precisa ser a série diária da ANA.")
    series = source.loc[:, ["Data", "Cota (m)"]].rename(
        columns={"Data": "data", "Cota (m)": "cota_cm"}
    )
    series["data"] = pd.to_datetime(series["data"], errors="coerce")
    series["cota_cm"] = pd.to_numeric(series["cota_cm"], errors="coerce")
    series = series.dropna(subset=["data"]).drop_duplicates("data", keep="last")
    series = series.set_index("data").sort_index().asfreq("D")
    return series


def _build_daily_features(series):
    """Build causal daily features and next-day 300 cm classification target."""
    result = pd.DataFrame(index=series.index)
    cota = series["cota_cm"]
    result["cota_cm"] = cota
    result["vz_1d_cm"] = cota.diff(1)
    result["vz_3d_cm"] = cota.diff(3) / 3.0
    result["vz_7d_cm"] = cota.diff(7) / 7.0
    result["az_1d_cm_dia"] = result["vz_1d_cm"].diff(1)
    result["max_cota_3d_cm"] = cota.shift(1).rolling(3, min_periods=1).max()
    result["max_cota_7d_cm"] = cota.shift(1).rolling(7, min_periods=1).max()
    result["media_cota_3d_cm"] = cota.shift(1).rolling(3, min_periods=1).mean()
    day_of_year = result.index.dayofyear.to_numpy(dtype=float)
    angle = 2 * np.pi * day_of_year / 365.25
    result["sin_dia_ano"] = np.sin(angle)
    result["cos_dia_ano"] = np.cos(angle)

    next_day = cota.shift(-1)
    result["target_cheia_d1"] = (next_day >= FLOOD_THRESHOLD_CM).astype(float)
    result.loc[next_day.isna(), "target_cheia_d1"] = np.nan
    return result


def _identify_events(series):
    """Find contiguous valid daily episodes at or above 300 cm.

    The onset Vz is the cota difference on the first flood day. A missing
    preceding calendar-day measurement leaves the rapid/gradual label unknown.
    Seasonal labels use the date of the episode's peak daily mean.
    """
    series = series.asfreq("D")
    flood = series["cota_cm"].ge(FLOOD_THRESHOLD_CM).fillna(False)
    starts = flood & ~flood.shift(1, fill_value=False)
    event_ids = starts.cumsum().where(flood)
    events = []
    for event_id, days in series.loc[flood].groupby(event_ids.loc[flood]):
        start = days.index.min()
        end = days.index.max()
        peak_date = days["cota_cm"].idxmax()
        previous_date = start - pd.Timedelta(days=1)
        previous_level = series["cota_cm"].get(previous_date, np.nan)
        onset_rate = (
            float(series.at[start, "cota_cm"] - previous_level)
            if pd.notna(previous_level)
            else None
        )
        labels = set()
        if onset_rate is not None:
            if onset_rate > 50:
                labels.add("relampago")
            elif 12 <= onset_rate <= 50:
                labels.add("gradual")
        if peak_date.month in (6, 7, 8):
            labels.add("inverno")
        if peak_date.month in (12, 1, 2, 3):
            labels.add("verao")
        events.append({
            "id": f"evento_{len(events) + 1:03d}",
            "inicio": start,
            "fim": end,
            "pico_data": peak_date,
            "pico_cm": float(days["cota_cm"].max()),
            "vz_inicio_cm_dia": onset_rate,
            "dias_cheia": int(len(days)),
            "labels": labels,
        })
    return events


def _event_window(event):
    return pd.date_range(
        event["inicio"] - pd.Timedelta(days=LEAD_DAYS),
        event["fim"],
        freq="D",
    )


def _fallback_probability(rows):
    """Binary Vz/Az baseline: linear daily extrapolation crosses 300 cm."""
    vz = rows["vz_1d_cm"].fillna(0.0)
    az = rows["az_1d_cm_dia"].fillna(0.0)
    projected = rows["cota_cm"] + vz + 0.5 * az
    return (projected >= FLOOD_THRESHOLD_CM).astype(float).to_numpy()


def _fit_binary(train, features=FEATURES):
    if len(train) < MIN_TRAIN_SAMPLES or train["target_cheia_d1"].nunique() < 2:
        return None
    data = lgb.Dataset(
        train.loc[:, features],
        label=train["target_cheia_d1"].astype(int),
        feature_name=list(features),
        free_raw_data=False,
    )
    return lgb.train(PARAMS, data, num_boost_round=80)


def avaliar_especialista(dataset, events, expert):
    """LOEO on ANA event windows only; each fold holds out one full episode."""
    eligible = [event for event in events if expert in event["labels"]]
    oof = []
    folds = []

    for test_event in eligible:
        test_indexes = _event_window(test_event).intersection(dataset.index)
        test = dataset.loc[test_indexes].dropna(subset=["cota_cm", "target_cheia_d1"])
        if test.empty:
            continue

        test_start = test_event["inicio"] - pd.Timedelta(days=LEAD_DAYS)
        test_end = test_event["fim"]
        train_indexes = set()
        for train_event in eligible:
            if train_event["id"] == test_event["id"]:
                continue
            train_indexes.update(
                _event_window(train_event).intersection(dataset.index)
            )
        train_indexes = [
            day for day in train_indexes
            if day < test_start - pd.Timedelta(days=1)
            or day > test_end + pd.Timedelta(days=1)
        ]
        train = dataset.loc[sorted(train_indexes)].dropna(
            subset=["cota_cm", "target_cheia_d1"]
        )
        model = _fit_binary(train)
        if model is None:
            continue

        actual = test["target_cheia_d1"].astype(int).to_numpy()
        probability = model.predict(test.loc[:, FEATURES])
        fallback = _fallback_probability(test)
        oof.extend({
            "evento": test_event["id"],
            "y": int(y),
            "p_modelo": float(p),
            "p_vz_az": float(b),
        } for y, p, b in zip(actual, probability, fallback))
        predicted = probability >= 0.5
        folds.append({
            "evento": test_event["id"],
            "inicio": test_event["inicio"].date().isoformat(),
            "fim": test_event["fim"].date().isoformat(),
            "pico_cm": test_event["pico_cm"],
            "vz_inicio_cm_dia": test_event["vz_inicio_cm_dia"],
            "dias_teste": int(len(test)),
            "positivos_teste": int(actual.sum()),
            "negativos_teste": int(len(actual) - actual.sum()),
            "recall_modelo": float(recall_score(actual, predicted, zero_division=0)),
            "recall_vz_az": float(
                recall_score(actual, fallback, zero_division=0)
            ),
        })

    if not oof:
        return {
            "eventos_candidatos": len(eligible),
            "folds_validos": 0,
            "status": "INSUFFICIENT_DATA",
            "folds": [],
        }

    y = np.array([row["y"] for row in oof])
    model_scores = np.array([row["p_modelo"] for row in oof])
    fallback_scores = np.array([row["p_vz_az"] for row in oof])
    model_predicted = model_scores >= 0.5
    fallback_predicted = fallback_scores >= 0.5
    model_pr_auc = (
        float(average_precision_score(y, model_scores))
        if y.sum() and y.sum() < len(y) else None
    )
    fallback_pr_auc = (
        float(average_precision_score(y, fallback_scores))
        if y.sum() and y.sum() < len(y) else None
    )
    model_f1 = float(f1_score(y, model_predicted, zero_division=0))
    fallback_f1 = float(f1_score(y, fallback_predicted, zero_division=0))
    active = (
        len(folds) >= MIN_FOLDS
        and model_pr_auc is not None
        and fallback_pr_auc is not None
        and model_pr_auc > fallback_pr_auc
        and model_f1 > fallback_f1
    )
    return {
        "eventos_candidatos": len(eligible),
        "folds_validos": len(folds),
        "amostras_oof": len(oof),
        "positivos_oof": int(y.sum()),
        "negativos_oof": int(len(y) - y.sum()),
        "limiar_classificacao": 0.5,
        "pr_auc_loeo": model_pr_auc,
        "pr_auc_fallback_vz_az": fallback_pr_auc,
        "f1_loeo": model_f1,
        "f1_fallback_vz_az": fallback_f1,
        "precisao_loeo": float(
            precision_score(y, model_predicted, zero_division=0)
        ),
        "recall_loeo": float(recall_score(y, model_predicted, zero_division=0)),
        "status": "ACTIVE" if active else "FALLBACK",
        "folds": folds,
    }


def prever_com_fallback(features, registry, model_dir=MODEL_DIR):
    """Return next-day >=300 cm probability or the Vz/Az binary fallback."""
    specialist = rotear_especialista(
        features.get("vz_1d_cm"), int(features["mes"])
    )
    vz = float(features.get("vz_1d_cm") or 0.0)
    az = float(features.get("az_1d_cm_dia") or 0.0)
    cota = float(features["cota_cm"])
    fallback = float(cota + vz + 0.5 * az >= FLOOD_THRESHOLD_CM)
    if specialist is None or registry.get(specialist, {}).get("status") != "ACTIVE":
        return {
            "probabilidade_cheia_d1": fallback,
            "especialista": None,
            "metodo": "vz_az",
        }

    metadata = registry[specialist]
    model_path = Path(model_dir) / metadata["arquivo"]
    model = lgb.Booster(model_file=str(model_path))
    row = pd.DataFrame(
        [{name: features.get(name, np.nan) for name in metadata["features"]}],
        columns=metadata["features"],
    )
    probability = float(model.predict(row)[0])
    return {
        "probabilidade_cheia_d1": probability,
        "especialista": specialist,
        "metodo": "lightgbm",
    }


def prever_cheia(features, result_file=RESULT_FILE, model_dir=MODEL_DIR):
    """Load ANA-trained registry and select an active expert or Vz/Az."""
    try:
        result = json.loads(Path(result_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Não foi possível carregar o registro do ensemble.") from error
    return prever_com_fallback(
        features,
        result.get("especialistas", {}),
        model_dir=model_dir,
    )


def executar():
    series = _read_ana()
    dataset = _build_daily_features(series)
    events = _identify_events(series)

    specialist_results = {}
    for expert in EXPERTS:
        specialist_results[expert] = avaliar_especialista(
            dataset, events, expert
        )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    registry = {}
    for expert, result in specialist_results.items():
        event_windows = set()
        for event in events:
            if expert in event["labels"]:
                event_windows.update(_event_window(event).intersection(dataset.index))
        train = dataset.loc[sorted(event_windows)].dropna(
            subset=["cota_cm", "target_cheia_d1"]
        )
        final_model = _fit_binary(train)
        if final_model is None:
            registry[expert] = {**result, "arquivo": None, "features": list(FEATURES)}
            continue

        filename = f"{expert}.txt"
        final_model.save_model(str(MODEL_DIR / filename))
        registry[expert] = {
            **result,
            "arquivo": filename,
            "features": list(FEATURES),
            "amostras_treino_final": int(len(train)),
            "positivos_treino_final": int(train["target_cheia_d1"].sum()),
        }

    event_json = [
        {
            "id": event["id"],
            "inicio": event["inicio"].date().isoformat(),
            "fim": event["fim"].date().isoformat(),
            "pico_data": event["pico_data"].date().isoformat(),
            "pico_cm": event["pico_cm"],
            "vz_inicio_cm_dia": event["vz_inicio_cm_dia"],
            "dias_cheia": event["dias_cheia"],
            "especialistas": sorted(event["labels"]),
        }
        for event in events
    ]
    result = {
        "status": "EXPERIMENTAL_SHADOW",
        "nao_e_sistema_de_alerta": True,
        "fonte_treino_unica": "data/ana_longa84580000.csv",
        "unidade_cota": "cm conforme especificação da série; sem conversão",
        "limiar_cheia_media_diaria_cm": FLOOD_THRESHOLD_CM,
        "horizonte_previsao_dias": 1,
        "periodo_ana": {
            "inicio": series.index[series["cota_cm"].notna()].min().date().isoformat(),
            "fim": series.index[series["cota_cm"].notna()].max().date().isoformat(),
            "leituras_validas": int(series["cota_cm"].notna().sum()),
            "dias_sem_leitura": int(series["cota_cm"].isna().sum()),
        },
        "definicoes_eventos": {
            "episodio": (
                "Sequência de dias consecutivos com cota diária >=300 cm; "
                "dias sem leitura encerram a continuidade."
            ),
            "relampago": "Vz no primeiro dia do episódio >50 cm/dia.",
            "gradual": "Vz no primeiro dia do episódio entre 12 e 50 cm/dia, inclusive.",
            "inverno": "Mês da data de pico diária entre junho e agosto.",
            "verao": "Mês da data de pico diária entre dezembro e março.",
            "evento_sem_vz_adjacente": (
                "Não recebe classe relâmpago/gradual se faltar a cota do dia "
                "anterior; ainda pode receber classe sazonal."
            ),
        },
        "contagens_eventos": {
            expert: sum(expert in event["labels"] for event in events)
            for expert in EXPERTS
        },
        "eventos": event_json,
        "especialistas": registry,
        "criterio_ativacao": (
            "Ao menos 4 folds LOEO válidos e PR-AUC e F1 OOF superiores ao "
            "fallback Vz/Az; caso contrário, usa fallback."
        ),
        "limitacoes": [
            "A série diária ANA tem lacunas; não foram interpoladas cotas ausentes.",
            "O Vz diário não representa a resolução horária da estação ERAB.",
            "A validação LOEO mede somente episódios de cheia identificados na ANA.",
            "Resultados experimentais, não conectados ao sistema de alertas.",
        ],
    }
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "fonte_treino": result["fonte_treino_unica"],
        "periodo": result["periodo_ana"],
        "limiar_cm": FLOOD_THRESHOLD_CM,
        "contagens_eventos": result["contagens_eventos"],
        "especialistas": {
            expert: {
                key: registry[expert].get(key)
                for key in (
                    "eventos_candidatos",
                    "folds_validos",
                    "pr_auc_loeo",
                    "pr_auc_fallback_vz_az",
                    "f1_loeo",
                    "f1_fallback_vz_az",
                    "status",
                )
            }
            for expert in EXPERTS
        },
        "result": str(RESULT_FILE.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    executar()
