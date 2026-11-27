#!/usr/bin/env python3
"""
vulnerabilidade.py — Camada de vulnerabilidade hidrológica auditável da Bacia do Rio Tubarão.
Separa fisicamente o Sistema 1 (RISCO URBANO / drenagem) do Sistema 2 (RISCO FLUVIAL / calha).
"""
import json
from pathlib import Path
from typing import Any, Dict, List

BASE = Path(__file__).resolve().parents[2]
PONTOS_FILE = BASE / "data" / "pontos_alagamento_tubarao.json"

TAXONOMIA_OFICIAL = {
    "drenagem_urbana": "Drenagem Urbana (Sistema 1)",
    "cheia_fluvial": "Cheia Fluvial (Sistema 2)",
    "confluencia_e_montante": "Confluência e Montante (Sistema 2)",
    "planicie_e_remanso": "Planície e Remanso (Sistema 2)",
}


def carregar_pontos_vulnerabilidade() -> List[Dict[str, Any]]:
    if not PONTOS_FILE.exists():
        return []
    try:
        dados = json.loads(PONTOS_FILE.read_text(encoding="utf-8"))
        return dados if isinstance(dados, list) else []
    except Exception:
        return []


def avaliar_contexto_vulnerabilidade(
    chuva_local_1h_mm: float = 0.0,
    chuva_local_3h_mm: float = 0.0,
    cota_erab_cm: float = 0.0,
) -> Dict[str, Any]:
    """
    Avalia os dois sistemas físicos independentes sem disparar alerta automático:
      - Sistema 1 (RISCO URBANO): chuva convectiva local >= 25 mm/1h ou >= 40 mm/3h
      - Sistema 2 (RISCO FLUVIAL): cota ERAB >= 250 cm (atenção) ou >= 350 cm (alerta)
    """
    pontos = carregar_pontos_vulnerabilidade()

    urbano_ativo = chuva_local_1h_mm >= 25.0 or chuva_local_3h_mm >= 40.0
    fluvial_ativo = cota_erab_cm >= 250.0

    locais_urbanos = [
        p["nome"]
        for p in pontos
        if p.get("classificacao") == "URBANO" or p.get("tipo") == "drenagem_urbana"
    ]
    locais_fluviais = [
        p["nome"]
        for p in pontos
        if p.get("classificacao") == "FLUVIAL"
        or p.get("tipo") in ("cheia_fluvial", "confluencia_e_montante", "planicie_e_remanso")
    ]

    return {
        "risco_urbano": {
            "ativo": urbano_ativo,
            "nivel": "ALTO" if (chuva_local_1h_mm >= 40.0 or chuva_local_3h_mm >= 50.0) else ("MODERADO" if urbano_ativo else "BAIXO"),
            "locais_sensiveis": locais_urbanos,
        },
        "risco_fluvial": {
            "ativo": fluvial_ativo,
            "nivel": "ALTO" if cota_erab_cm >= 350.0 else ("MODERADO" if fluvial_ativo else "BAIXO"),
            "locais_sensiveis": locais_fluviais,
        },
        "total_pontos_catalogados": len(pontos),
    }


if __name__ == "__main__":
    print(json.dumps(avaliar_contexto_vulnerabilidade(), indent=2, ensure_ascii=False))
