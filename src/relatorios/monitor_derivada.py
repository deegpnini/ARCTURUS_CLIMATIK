import json
import math
import statistics
from datetime import datetime
from itertools import combinations
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parents[2]
HISTORICO = BASE / "resultados" / "historico_previsoes.csv"
REGIME_FILE = BASE / "data" / "regime_atual.json"
ENSEMBLE_FILE = BASE / "data" / "chuva_ensemble_consolidada.json"

# Limiares calibrados
LIMIAR_ATENCAO = 20.0   # P95
LIMIAR_EXTREMO = 52.0   # P99
LIMIAR_CHEIA_RELAMPAGO = 100.0
MIN_CICLOS_CONFIRMACAO = 2
INTERVALO_MIN_AZ_H = 0.5


def vz_robusto(t_h, cota, n=4, janela_min_h=0.5):
    """Estima a tendência em cm/h pela mediana das inclinações Theil-Sen."""
    observacoes = {}
    for tempo, nivel in zip(t_h, cota):
        try:
            tempo = float(tempo)
            nivel = float(nivel)
        except (TypeError, ValueError):
            continue
        if math.isfinite(tempo) and math.isfinite(nivel):
            # Keep the last reading for duplicate timestamps; never form a
            # zero-duration slope from duplicate observations.
            observacoes[tempo] = nivel

    limite = max(3, int(n))
    pontos = sorted(observacoes.items())[-limite:]
    if len(pontos) < 3 or pontos[-1][0] - pontos[0][0] < janela_min_h:
        return None

    inclinacoes = [
        (nivel_b - nivel_a) / (tempo_b - tempo_a)
        for (tempo_a, nivel_a), (tempo_b, nivel_b) in combinations(pontos, 2)
    ]
    return statistics.median(inclinacoes) if inclinacoes else None


def az_robusto(t_h, cota, n=4, janela_min_h=0.5):
    """Estima a aceleração usando duas tendências Theil-Sen separadas no tempo."""
    observacoes = {}
    for tempo, nivel in zip(t_h, cota):
        try:
            tempo = float(tempo)
            nivel = float(nivel)
        except (TypeError, ValueError):
            continue
        if math.isfinite(tempo) and math.isfinite(nivel):
            observacoes[tempo] = nivel

    pontos = sorted(observacoes.items())
    if not pontos:
        return None

    tempos, cotas = zip(*pontos)
    vz_atual = vz_robusto(tempos, cotas, n=n, janela_min_h=janela_min_h)
    if vz_atual is None:
        return None

    tempo_atual = tempos[-1]
    tempo_limite = tempo_atual - janela_min_h
    anteriores = [(tempo, nivel) for tempo, nivel in pontos if tempo <= tempo_limite]
    if not anteriores:
        return None

    tempos_anteriores, cotas_anteriores = zip(*anteriores)
    vz_anterior = vz_robusto(
        tempos_anteriores,
        cotas_anteriores,
        n=n,
        janela_min_h=janela_min_h,
    )
    intervalo_h = tempo_atual - tempos_anteriores[-1]
    if vz_anterior is None or intervalo_h < janela_min_h:
        return None
    return (vz_atual - vz_anterior) / intervalo_h


def atualizar_confirmacao(
    regime_atual,
    candidato_anterior,
    contador_anterior,
    timestamp_anterior,
    candidato,
    timestamp_atual,
):
    """Advance the candidate only when a strictly newer observation arrives."""
    if timestamp_anterior is not None:
        anterior = pd.to_datetime(timestamp_anterior, errors="coerce")
        atual = pd.to_datetime(timestamp_atual, errors="coerce")
        if pd.notna(anterior) and pd.notna(atual) and atual <= anterior:
            return regime_atual, candidato_anterior, contador_anterior

    contador = contador_anterior + 1 if candidato == candidato_anterior else 1
    contador = min(contador, MIN_CICLOS_CONFIRMACAO)
    confirmado = candidato if contador >= MIN_CICLOS_CONFIRMACAO else regime_atual
    return confirmado, candidato, contador


def calcular_derivada():
    if not HISTORICO.exists():
        print("❌ Histórico não encontrado.")
        return

    df = pd.read_csv(HISTORICO)
    colunas_necessarias = {"timestamp_execucao", "cota_atual_cm"}
    if not colunas_necessarias.issubset(df.columns):
        raise ValueError(
            "Histórico precisa conter timestamp_execucao e cota_atual_cm."
        )

    df["timestamp_execucao"] = pd.to_datetime(
        df["timestamp_execucao"], format="mixed", errors="coerce"
    )
    df["cota_atual_cm"] = pd.to_numeric(df["cota_atual_cm"], errors="coerce")
    df = (
        df.dropna(subset=["timestamp_execucao", "cota_atual_cm"])
        .sort_values("timestamp_execucao", kind="stable")
        .drop_duplicates("timestamp_execucao", keep="last")
    )
    if df.empty:
        print("⚠️ Histórico sem observações válidas.")
        return

    ultima = df.iloc[-1]
    timestamp_atual = ultima["timestamp_execucao"]
    cota_atual = float(ultima["cota_atual_cm"])
    horas = (
        df["timestamp_execucao"] - df["timestamp_execucao"].iloc[0]
    ).dt.total_seconds() / 3600
    cotas = df["cota_atual_cm"].astype(float)

    vz = vz_robusto(horas, cotas)
    az = az_robusto(horas, cotas, janela_min_h=INTERVALO_MIN_AZ_H)

    estado = {}
    if REGIME_FILE.exists():
        with REGIME_FILE.open(encoding="utf-8") as arquivo:
            estado = json.load(arquivo)
    regime_atual = estado.get("regime", "INDEFINIDO")
    candidato_anterior = estado.get("regime_candidato")
    contador_anterior = int(estado.get("contador_candidato", 0))
    timestamp_anterior = estado.get("timestamp_ultima_observacao")

    motivo = "Vz robusto indisponível: histórico precisa cobrir pelo menos 30 min."
    regime_candidato = None
    if vz is not None:
        incerteza_alta = False
        if ENSEMBLE_FILE.exists():
            with ENSEMBLE_FILE.open(encoding="utf-8") as arquivo:
                ensemble = json.load(arquivo)
            incerteza_alta = ensemble.get("incerteza_alta", False)

        limiar_atencao = 12.0 if incerteza_alta else LIMIAR_ATENCAO
        if vz > LIMIAR_CHEIA_RELAMPAGO:
            regime_candidato = "EXTREMO"
            motivo_candidato = f"Vz robusto = {vz:+.1f} cm/h (cheia relâmpago)"
        elif vz > LIMIAR_EXTREMO:
            regime_candidato = "EXTREMO"
            motivo_candidato = f"Vz robusto = {vz:+.1f} cm/h (evento extremo)"
        elif vz > limiar_atencao:
            regime_candidato = "ATENCAO"
            motivo_candidato = f"Vz robusto = {vz:+.1f} cm/h (subida anormal)"
        else:
            regime_candidato = "NORMAL"
            motivo_candidato = f"Vz robusto = {vz:+.1f} cm/h"

        regime_atual, candidato_anterior, contador_anterior = atualizar_confirmacao(
            regime_atual,
            candidato_anterior,
            contador_anterior,
            timestamp_anterior,
            regime_candidato,
            timestamp_atual,
        )
        if contador_anterior < MIN_CICLOS_CONFIRMACAO:
            motivo = (
                f"{motivo_candidato}; aguardando confirmação "
                f"({contador_anterior}/{MIN_CICLOS_CONFIRMACAO} ciclos)"
            )
        else:
            motivo = motivo_candidato
    else:
        candidato_anterior = None
        contador_anterior = 0

    tempo_200 = None
    tempo_300 = None
    if vz is not None and vz > 0:
        if cota_atual < 200:
            tempo_200 = (200 - cota_atual) / vz
        if cota_atual < 300:
            tempo_300 = (300 - cota_atual) / vz

    atualizado = datetime.now().isoformat()
    estado_atualizado = {
        **estado,
        "regime": regime_atual,
        "regime_candidato": candidato_anterior,
        "contador_candidato": contador_anterior,
        "timestamp_ultima_observacao": timestamp_atual.isoformat(),
        "delta_60m": round(vz, 2) if vz is not None else None,
        "vz_robusto": round(vz, 2) if vz is not None else None,
        "aceleracao_az": round(az, 2) if az is not None else None,
        "az_robusto": round(az, 2) if az is not None else None,
        "tempo_para_200h": round(tempo_200, 1) if tempo_200 is not None else None,
        "tempo_para_300h": round(tempo_300, 1) if tempo_300 is not None else None,
        "motivo": motivo,
        "atualizado": atualizado,
    }

    REGIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REGIME_FILE.open("w", encoding="utf-8") as arquivo:
        json.dump(estado_atualizado, arquivo, indent=2, ensure_ascii=False)

    print("=== MONITOR DE DERIVADA (Vz robusto) ===")
    print(f"Cota atual: {cota_atual:.1f} cm")
    print(f"Vz robusto: {vz:+.1f} cm/h" if vz is not None else "Vz robusto: indisponível")
    print(f"Az robusto: {az:+.2f} cm/h²" if az is not None else "Az robusto: indisponível")
    print(f"Regime: {regime_atual} (candidato: {regime_candidato or 'indisponível'})")
    print(motivo)
    print(f"✅ Regime salvo em: {REGIME_FILE}")


if __name__ == "__main__":
    calcular_derivada()
