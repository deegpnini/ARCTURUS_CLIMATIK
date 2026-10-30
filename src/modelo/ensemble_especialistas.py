"""Treina especialistas hidrológicos validados por evento (LOEO).

Este ensemble é experimental: especialistas só são ativados se superarem o
fallback Vz/Az em validação LOEO, e não alteram o sistema operacional de alerta.
"""
import json
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error


ROOT = Path(__file__).resolve().parents[2]
ANA_FILE = ROOT / "data" / "ana_longa84580000.csv"
DATASET_FILE = ROOT / "data" / "dataset_1h.csv"
SPLIT_FILE = ROOT / "data" / "split_v3.json"
RESULT_FILE = ROOT / "resultados" / "ensemble_especialistas.json"
MODEL_DIR = ROOT / "modelos" / "especialistas"
MIN_TREINO_ROWS = 100
MIN_VALID_FOLDS = 4
MIN_VALID_EVENTS = 4

EXPERTS = ("relampago", "gradual", "inverno", "verao")
PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "learning_rate": 0.03,
    "num_leaves": 7,
    "max_depth": 4,
    "min_data_in_leaf": 15,
    "feature_fraction": 0.9,
    "verbosity": -1,
    "seed": 42,
    "num_threads": 1,
    "deterministic": True,
    "force_col_wise": True,
}


def rotear_especialista(vz_cm_h, mes):
    """Seleciona o especialista a partir do Vz observado e do mês atual."""
    try:
        rate = float(vz_cm_h)
    except (TypeError, ValueError):
        rate = None
    if rate is not None and math.isfinite(rate):
        if rate > 50:
            return "relampago"
        if rate >= 12:
            return "gradual"
    if mes in (6, 7, 8):
        return "inverno"
    if mes in (12, 1, 2, 3):
        return "verao"
    return None


def prever_com_fallback(features, registry, model_dir=MODEL_DIR):
    """Prevê cota em 1h; só usa LightGBM aprovado contra o fallback Vz/Az."""
    cota = float(features["cota"])
    vz = float(features["delta_60m"])
    az = float(features["aceleracao_1h"])
    specialist = rotear_especialista(vz, int(features["mes"]))
    fallback = cota + vz + 0.5 * az

    if specialist is None or registry.get(specialist, {}).get("status") != "ACTIVE":
        return {"cota_prevista": fallback, "especialista": None, "metodo": "vz_az"}

    metadata = registry[specialist]
    model_path = Path(model_dir) / metadata["arquivo"]
    model = lgb.Booster(model_file=str(model_path))
    row = pd.DataFrame(
        [{name: features.get(name, np.nan) for name in metadata["features"]}],
        columns=metadata["features"],
    )
    delta = float(model.predict(row)[0])
    return {
        "cota_prevista": cota + delta,
        "especialista": specialist,
        "metodo": "lightgbm",
    }


def prever_cota_1h(features, result_file=RESULT_FILE, model_dir=MODEL_DIR):
    """Carrega o registro validado e encaminha para especialista ou fallback."""
    try:
        result = json.loads(Path(result_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Não foi possível carregar o registro do ensemble.") from error
    return prever_com_fallback(features, result.get("especialistas", {}), model_dir)


def _historico_ana():
    series = pd.read_csv(ANA_FILE)
    date_column = "Data" if "Data" in series else "data"
    level_column = "Cota (m)" if "Cota (m)" in series else "cota"
    series = series[[date_column, level_column]].rename(
        columns={date_column: "data", level_column: "cota_cm"}
    )
    series["data"] = pd.to_datetime(series["data"], errors="coerce")
    series["cota_cm"] = pd.to_numeric(series["cota_cm"], errors="coerce")
    return series.dropna().sort_values("data").drop_duplicates("data")


def _ana_event_summary(series):
    """Declustera cota >=200 cm; daily ANA cannot resolve hourly rise rates."""
    high = series[series["cota_cm"] >= 200].copy()
    high["event"] = high["data"].diff().dt.days.gt(3).cumsum()
    events = high.groupby("event").agg(
        inicio=("data", "min"),
        pico=("cota_cm", "max"),
        n_dias=("data", "size"),
    )
    events["mes_pico"] = [
        int(group.loc[group["cota_cm"].idxmax(), "data"].month)
        for _, group in high.groupby("event")
    ]
    events["estacao"] = events["mes_pico"].map(
        lambda month: (
            "inverno" if month in (6, 7, 8)
            else "verao" if month in (12, 1, 2, 3)
            else "outras"
        )
    )
    return events


def _modern_event_groups(dataset, event_definitions):
    """Measure event Vz with observed 60-minute changes for type assignment."""
    event_groups = {}
    for event_number, event in enumerate(event_definitions, start=1):
        start = pd.Timestamp(event["inicio"])
        end = pd.Timestamp(event["fim"])
        event_rows = dataset.loc[start:end]
        if event_rows.empty:
            continue

        one_hour_rise = (
            event_rows["cota"] - event_rows["cota_lag_60m"]
        ).dropna()
        max_vz = float(one_hour_rise.max()) if not one_hour_rise.empty else None
        labels = set()
        if max_vz is not None and max_vz > 50:
            labels.add("relampago")
        if max_vz is not None and 12 <= max_vz <= 50:
            labels.add("gradual")
        peak_month = event_rows["cota"].idxmax().month
        if peak_month in (6, 7, 8):
            labels.add("inverno")
        if peak_month in (12, 1, 2, 3):
            labels.add("verao")

        event_groups[f"evento_{event_number:02d}"] = {
            "inicio": start,
            "fim": end,
            "pico_cm": float(event.get("pico", event_rows["cota"].max())),
            "vz_max_cm_h": max_vz,
            "labels": labels,
            "rows": event_rows.index,
        }
    return event_groups


def _fallback_prediction(rows):
    vz = rows["delta_60m"].fillna(0.0)
    az = rows["aceleracao_1h"].fillna(0.0)
    return rows["cota"] + vz + 0.5 * az


def avaliar_especialista(dataset, event_groups, features, expert):
    """Executa LOEO em eventos do especialista, sem treinar no evento retido."""
    eligible = [
        (name, event)
        for name, event in event_groups.items()
        if expert in event["labels"]
    ]
    folds = []
    for test_name, test_event in eligible:
        test = dataset.loc[test_event["rows"]].dropna(subset=["target_1h", "cota"])
        training_names = [
            name for name, event in eligible
            if name != test_name
            and (event["fim"] < test_event["inicio"] - pd.Timedelta(days=1)
                 or event["inicio"] > test_event["fim"] + pd.Timedelta(days=1))
        ]
        train_indices = [
            index
            for name in training_names
            for index in event_groups[name]["rows"]
        ]
        train = dataset.loc[train_indices].dropna(subset=["target_1h", "cota"])
        if len(train) < MIN_TREINO_ROWS or len(test) < 10:
            continue

        train_delta = train["target_1h"] - train["cota"]
        test_delta = test["target_1h"] - test["cota"]
        model = lgb.train(
            PARAMS,
            lgb.Dataset(train[features], label=train_delta),
            num_boost_round=120,
        )
        prediction = test["cota"] + model.predict(test[features])
        fallback = _fallback_prediction(test)
        actual = test["target_1h"]
        folds.append({
            "evento": test_name,
            "inicio": test_event["inicio"].isoformat(),
            "vz_max_cm_h": test_event["vz_max_cm_h"],
            "n_treino_eventos": len(training_names),
            "n_teste": len(test),
            "mae_lightgbm_cm": float(mean_absolute_error(actual, prediction)),
            "mae_vz_az_cm": float(mean_absolute_error(actual, fallback)),
        })

    if folds:
        mae_model = float(np.mean([fold["mae_lightgbm_cm"] for fold in folds]))
        mae_fallback = float(np.mean([fold["mae_vz_az_cm"] for fold in folds]))
    else:
        mae_model = mae_fallback = None
    active = (
        len(eligible) >= MIN_VALID_EVENTS
        and len(folds) >= MIN_VALID_FOLDS
        and mae_model is not None
        and mae_model < mae_fallback
    )
    return {
        "eventos_candidatos": len(eligible),
        "folds_validos": len(folds),
        "mae_loeo_lightgbm_cm": mae_model,
        "mae_loeo_vz_az_cm": mae_fallback,
        "status": "ACTIVE" if active else "FALLBACK",
        "folds": folds,
    }


def executar():
    ana = _historico_ana()
    ana_events = _ana_event_summary(ana)

    dataset = pd.read_csv(DATASET_FILE, parse_dates=["timestamp"])
    dataset = dataset.drop_duplicates("timestamp", keep="last").set_index("timestamp").sort_index()
    split = json.loads(SPLIT_FILE.read_text(encoding="utf-8"))
    event_groups = _modern_event_groups(dataset, split["historico"])
    numeric_features = dataset.select_dtypes(include=[np.number]).columns.tolist()
    features = [
        column for column in numeric_features
        if not column.startswith("target_") and column not in ("target_1h",)
    ]
    dataset["mes"] = dataset.index.month
    features.append("mes")

    expert_results = {}
    for expert in EXPERTS:
        expert_results[expert] = avaliar_especialista(
            dataset, event_groups, features, expert
        )

    registry = {}
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for expert, result in expert_results.items():
        if result["status"] != "ACTIVE":
            registry[expert] = result
            continue
        eligible = [
            event for event in event_groups.values()
            if expert in event["labels"]
        ]
        indices = [index for event in eligible for index in event["rows"]]
        train = dataset.loc[indices].dropna(subset=["target_1h", "cota"])
        model = lgb.train(
            PARAMS,
            lgb.Dataset(train[features], label=train["target_1h"] - train["cota"]),
            num_boost_round=120,
        )
        filename = f"{expert}.txt"
        model.save_model(str(MODEL_DIR / filename))
        registry[expert] = {
            **result,
            "arquivo": filename,
            "features": features,
            "n_treino_final": len(train),
        }

    modern_counts = {
        expert: sum(expert in event["labels"] for event in event_groups.values())
        for expert in EXPERTS
    }
    result = {
        "status": "EXPERIMENTAL_SHADOW",
        "nao_e_sistema_de_alerta": True,
        "dados_ana_diarios": {
            "inicio": ana["data"].min().date().isoformat(),
            "fim": ana["data"].max().date().isoformat(),
            "episodios_cota_ge_200cm_gap_gt_3_dias": len(ana_events),
            "inverno_jun_ago": int((ana_events["estacao"] == "inverno").sum()),
            "verao_dez_mar": int((ana_events["estacao"] == "verao").sum()),
            "demais_meses": int((ana_events["estacao"] == "outras").sum()),
            "limite_resolucao": (
                "A série diária não permite determinar Vz horário nem separar "
                "cheias relâmpago e graduais para 1939-2026."
            ),
        },
        "dados_alta_resolucao": {
            "eventos_loeo": len(event_groups),
            "periodo_inicio": (
                min(event["inicio"] for event in event_groups.values()).isoformat()
                if event_groups else None
            ),
            "periodo_fim": (
                max(event["fim"] for event in event_groups.values()).isoformat()
                if event_groups else None
            ),
            "rotulo_relampago": "pico de Vz observado >50 cm/h no evento",
            "rotulo_gradual": "pico de Vz observado entre 12 e 50 cm/h no evento",
            "rotulos_temporais": (
                "inverno: mês inicial junho-agosto; verão: dezembro-março"
            ),
            "contagem_por_especialista": modern_counts,
        },
        "especialistas": registry,
        "criterio_ativacao": (
            "Ativa somente com pelo menos 4 eventos e 4 folds LOEO válidos, "
            "e MAE média LOEO menor que o fallback Vz/Az."
        ),
        "aviso": (
            "Resultados de pesquisa em sombra; não enviar previsões deste "
            "ensemble como alertas públicos."
        ),
    }
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "ana_events": result["dados_ana_diarios"],
        "high_resolution_events": modern_counts,
        "experts": {
            name: {
                "status": item["status"],
                "events": item["eventos_candidatos"],
                "valid_folds": item["folds_validos"],
                "mae_lightgbm_cm": item["mae_loeo_lightgbm_cm"],
                "mae_vz_az_cm": item["mae_loeo_vz_az_cm"],
            }
            for name, item in registry.items()
        },
        "result": str(RESULT_FILE.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    executar()
