import json
import math
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _ler_jsonl(caminho: Path) -> List[Dict[str, Any]]:
    if not caminho.exists():
        return []
    registros = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            registros.append(json.loads(linha))
        except Exception:
            continue
    return registros


def _parse_ts(valor: Any) -> Optional[datetime]:
    if not valor or not isinstance(valor, str):
        return None
    texto = valor.strip().replace("Z", "")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ):
        try:
            return datetime.strptime(texto[:26], fmt)
        except ValueError:
            continue
    return None


def _carregar_cota_postgres(
    ts_ini: datetime, ts_fim: datetime
) -> List[Tuple[datetime, float]]:
    sql = (
        "SELECT to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS'), cota_cm "
        "FROM leituras "
        f"WHERE qc = 'VALIDO' AND timestamp >= '{ts_ini.strftime('%Y-%m-%d %H:%M:%S')}' "
        f"AND timestamp <= '{ts_fim.strftime('%Y-%m-%d %H:%M:%S')}' "
        "ORDER BY timestamp ASC;"
    )
    proc = subprocess.run(
        ["psql", "-d", "arcturus", "-At", "-F", "\t", "-c", sql],
        capture_output=True,
        text=True,
        check=False,
    )
    serie: List[Tuple[datetime, float]] = []
    for linha in proc.stdout.splitlines():
        partes = linha.strip().split("\t")
        if len(partes) != 2:
            continue
        ts = _parse_ts(partes[0])
        try:
            cota = float(partes[1])
        except ValueError:
            continue
        if ts is not None and math.isfinite(cota):
            serie.append((ts, cota))
    return serie


def _buscar_cota_observada(
    serie_obs: List[Tuple[datetime, float]],
    alvo_ts: datetime,
    tolerancia_min: int = 25,
) -> Optional[float]:
    melhor_diff = None
    melhor_cota = None
    for ts, cota in serie_obs:
        diff = abs((ts - alvo_ts).total_seconds()) / 60.0
        if diff <= tolerancia_min and (melhor_diff is None or diff < melhor_diff):
            melhor_diff = diff
            melhor_cota = cota
    return melhor_cota


def _extrair_previsoes_v8_logs(base_dir: Path) -> Dict[datetime, Dict[str, float]]:
    """Extrai projeções do v8 a partir dos logs operacionais do ciclo ou arquivo dedicado."""
    mapa: Dict[datetime, Dict[str, float]] = {}
    for arq in [
        base_dir / "logs" / "predicoes_v8.jsonl",
        base_dir / "logs" / "sombra_v11c.jsonl",
    ]:
        for reg in _ler_jsonl(arq):
            ts = _parse_ts(reg.get("timestamp") or reg.get("ts"))
            if ts is None:
                continue
            item = mapa.setdefault(ts, {})
            base_cota = reg.get("cota_atual_cm") or reg.get("cota_cm")
            for h in ("1h", "3h", "6h"):
                v_abs = reg.get(f"v8_{h}_cm")
                v_del = reg.get(f"v8_delta_{h}")
                if v_abs is not None:
                    item[h] = float(v_abs)
                elif v_del is not None and base_cota is not None:
                    item[h] = float(base_cota) + float(v_del)
    return mapa


def gerar_relatorio_pos_evento(evento_id: Optional[str] = None) -> Path:
    base_dir = Path(__file__).resolve().parents[2]
    eventos = _ler_jsonl(base_dir / "data" / "lag_eventos.jsonl")
    if not eventos:
        raise RuntimeError("Nenhum evento encontrado em data/lag_eventos.jsonl")

    if evento_id:
        selecionados = [
            e for e in eventos if (e.get("evento_id") or e.get("evento")) == evento_id
        ]
        if not selecionados:
            raise RuntimeError(f"Evento {evento_id} nao encontrado em lag_eventos.jsonl")
        evento = selecionados[-1]
    else:
        evento = eventos[-1]

    ev_id = (
        evento.get("evento_id")
        or evento.get("evento")
        or datetime.now().strftime("%Y%m%d_%H%M")
    )
    ts_ini = _parse_ts(
        evento.get("ts_base_repique")
        or evento.get("inicio_evento")
        or evento.get("ts_inicio_evento")
    )
    ts_fim = _parse_ts(evento.get("ultima_atualizacao") or evento.get("ts_ultima_atualizacao")) or datetime.now()
    if ts_ini is None:
        ts_ini = ts_fim - timedelta(hours=24)

    # 1. Série real da régua ERAB diretamente do PostgreSQL
    serie_pg = _carregar_cota_postgres(ts_ini - timedelta(hours=6), ts_fim + timedelta(hours=6))
    if serie_pg:
        ts_min_pg, cota_min_pg = min(serie_pg, key=lambda x: x[1])
        ts_max_pg, cota_max_pg = max(serie_pg, key=lambda x: x[1])
    else:
        cota_min_pg = float(evento.get("cota_pre_evento") or 0.0)
        cota_max_pg = float(evento.get("cota_pico") or evento.get("cota_atual") or 0.0)
        ts_min_pg = ts_ini
        ts_max_pg = _parse_ts(evento.get("ts_pico")) or ts_fim

    cota_pre = float(evento.get("cota_pre_evento") or cota_min_pg)
    cota_base_rep = float(evento.get("cota_base_repique") or cota_min_pg)
    cota_pico = max(cota_max_pg, float(evento.get("cota_pico") or 0.0))
    delta_total = cota_pico - cota_pre
    delta_repique = cota_pico - cota_base_rep

    # Lag real medido entre base da subida e pico máximo observado no PostgreSQL
    ts_ref_subida = _parse_ts(evento.get("ts_base_repique")) or ts_min_pg
    lag_pico_h = round(max(0.0, (ts_max_pg - ts_ref_subida).total_seconds() / 3600.0), 2)
    if lag_pico_h == 0.0 and evento.get("horas_ate_pico") is not None:
        lag_pico_h = float(evento["horas_ate_pico"])

    chuva_media = float(evento.get("chuva_media_bacia") or 0.0)
    chuva_cab = float(evento.get("chuva_cabeceira") or 0.0)
    chuva_med = float(evento.get("chuva_medio_curso") or 0.0)
    ganho_cm_mm = (delta_total / chuva_media) if chuva_media > 0 else 0.0

    # 2. Enquadramento na Base Científica (docs/base_cientifica_bacia_tubarao.md)
    if 5.0 <= lag_pico_h <= 8.0:
        enquadramento_lag = (
            f"**`{lag_pico_h:.2f} h`** — dentro da janela documentada para o **Rio Braço do Norte / São Ludgero** (`5–8 h`, CPRM/SGB)."
        )
    elif 8.0 < lag_pico_h <= 12.0:
        enquadramento_lag = (
            f"**`{lag_pico_h:.2f} h`** — dentro da janela documentada para o **Alto Rio Tubarão / Orleans** (`8–12 h`, CPRM/SGB)."
        )
    elif lag_pico_h > 12.0:
        enquadramento_lag = (
            f"**`{lag_pico_h:.2f} h`** — onda composta / multi-pulso (superposição cabeceira + médio curso + remanso)."
        )
    else:
        enquadramento_lag = f"**`{lag_pico_h:.2f} h`** — pulso rápido de calha / médio curso."

    if cota_pico >= 550:
        patamar_cprm = "🔴 **Cota de Inundação (`≥ 550 cm` — CPRM/SGB)**"
    elif cota_pico >= 470:
        patamar_cprm = "🟠 **Início de Alarme Oficial PLAMCON 2025 (`≥ 470 cm` na 84580500)**"
    elif cota_pico >= 450:
        patamar_cprm = "🟠 **Cota de Alerta (`≥ 450 cm` — CPRM/SGB; refluxo na microdrenagem)**"
    elif cota_pico >= 350:
        patamar_cprm = "🟡 **Cota de Atenção (`≥ 350 cm` — CPRM/SGB; mobilização preventiva)**"
    else:
        patamar_cprm = "🟢 **Calha Principal / Nível Normal (`< 350 cm`)**"

    # 3. Auditoria pareada v8 vs v11c contra a série real do PostgreSQL
    sombra = _ler_jsonl(base_dir / "logs" / "sombra_v11c.jsonl")
    preds_v8_extra = _extrair_previsoes_v8_logs(base_dir)
    erros: Dict[str, Dict[str, List[float]]] = {
        "v8": {"1h": [], "3h": [], "6h": []},
        "v11c": {"1h": [], "3h": [], "6h": []},
    }

    for reg in sombra:
        ts_prev = _parse_ts(reg.get("timestamp") or reg.get("ts"))
        if ts_prev is None:
            continue
        if not (ts_ini - timedelta(hours=6) <= ts_prev <= ts_fim + timedelta(hours=2)):
            continue

        cota_base = reg.get("cota_atual_cm") or reg.get("cota_cm")
        for h_horas, h_chave in ((1, "1h"), (3, "3h"), (6, "6h")):
            cota_real = _buscar_cota_observada(serie_pg, ts_prev + timedelta(hours=h_horas))
            if cota_real is None:
                continue

            # v8
            p_v8 = reg.get(f"v8_{h_chave}_cm")
            if p_v8 is None and cota_base is not None and reg.get(f"v8_delta_{h_chave}") is not None:
                p_v8 = float(cota_base) + float(reg[f"v8_delta_{h_chave}"])
            if p_v8 is None and ts_prev in preds_v8_extra:
                p_v8 = preds_v8_extra[ts_prev].get(h_chave)
            if p_v8 is not None:
                erros["v8"][h_chave].append(float(p_v8) - cota_real)

            # v11c
            p_v11 = reg.get(f"v11c_{h_chave}_cm")
            if p_v11 is None and cota_base is not None and reg.get(f"v11c_delta_{h_chave}") is not None:
                p_v11 = float(cota_base) + float(reg[f"v11c_delta_{h_chave}"])
            if p_v11 is None and h_chave == "6h" and reg.get("cota_prevista_24h_cm") is not None:
                p_v11 = float(reg["cota_prevista_24h_cm"])
            if p_v11 is not None:
                erros["v11c"][h_chave].append(float(p_v11) - cota_real)

    def _resumo_metricas(lista: List[float]) -> Tuple[Optional[float], str]:
        if not lista:
            return None, "N/D (0 pares)"
        mae = sum(abs(x) for x in lista) / len(lista)
        rmse = math.sqrt(sum(x * x for x in lista) / len(lista))
        vies = sum(lista) / len(lista)
        return mae, f"MAE: **{mae:.2f} cm** | RMSE: {rmse:.2f} cm | Viés: {vies:+.2f} cm (`n={len(lista)}`)"

    linhas_auditoria = []
    for h_label, h_chave in (("+1 hora", "1h"), ("+3 horas", "3h"), ("+6 horas", "6h")):
        mae_v8, txt_v8 = _resumo_metricas(erros["v8"][h_chave])
        mae_v11, txt_v11 = _resumo_metricas(erros["v11c"][h_chave])
        if mae_v8 is not None and mae_v11 is not None:
            vencedor = "✅ **`v8` venceu**" if mae_v8 <= mae_v11 else "⚠️ `v11c` menor MAE"
        else:
            vencedor = "Aguardando pareamento completo"
        linhas_auditoria.append(f"| **{h_label}** | {txt_v8} | {txt_v11} | {vencedor} |")

    # Detalhamento das estações do evento
    est_24h = evento.get("chuvas_estacoes_24h") or {}
    linhas_estacoes = []
    for nome_est, val_24h in sorted(est_24h.items(), key=lambda x: float(x[1] or 0), reverse=True):
        val_6h = (evento.get("chuvas_estacoes_6h") or {}).get(nome_est, 0.0)
        linhas_estacoes.append(f"| {nome_est} | **{float(val_24h or 0):.1f} mm** | {float(val_6h or 0):.1f} mm |")

    linhas_md = [
        f"# Relatório Pós-Evento Hidrológico — `{ev_id}`",
        "",
        f"* **Gerado em:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"* **Série Real PostgreSQL (`leituras`):** `{len(serie_pg)}` registros válidos analisados",
        f"* **Janela do Evento:** `{ts_min_pg.strftime('%d/%m %H:%M')}` (mínima) → `{ts_max_pg.strftime('%d/%m %H:%M')}` (pico)",
        "",
        "---",
        "",
        "## 1. Assinatura Física e Hidrológica do Evento",
        "",
        "| Indicador Hidrológico | Valor Observado | Interpretação Física |",
        "| :--- | :---: | :--- |",
        f"| **Cota Mínima / Pré-Evento (ERAB)** | `{cota_min_pg:.1f} cm` (`{ts_min_pg.strftime('%d/%m %H:%M')}`) | Patamar antecedente na calha em Tubarão |",
        f"| **Cota Máxima Atingida (Pico ERAB)** | **`{cota_pico:.1f} cm`** (`{ts_max_pg.strftime('%d/%m %H:%M')}`) | {patamar_cprm} |",
        f"| **Amplitude Total (`ΔZ_total`)** | **`+{delta_total:.1f} cm`** | Elevação total da lâmina d'água no evento |",
        f"| **Amplitude do Repique (`ΔZ_repique`)** | **`+{delta_repique:.1f} cm`** | Pulso a partir da base do repique (`{cota_base_rep:.1f} cm`) |",
        f"| **Chuva Cabeceira (Serra)** | `{chuva_cab:.2f} mm` | Média Lauro Müller, Orleans e Grão-Pará |",
        f"| **Chuva Médio Curso** | `{chuva_med:.2f} mm` | São Ludgero (Sub-bacia Rio Braço do Norte) |",
        f"| **Chuva Média Espacial da Bacia** | `{chuva_media:.2f} mm` | Precipitação integrada da bacia |",
        f"| **Ganho Empírico (`ΔZ_total / P_bacia`)** | **`{ganho_cm_mm:.2f} cm/mm`** | Sensibilidade da resposta da régua ERAB neste estado de umidade |",
        f"| **Dominante 24h vs. Dominante 6h** | `{evento.get('dominante_24h', 'N/D')}` / `{evento.get('dominante_6h', 'N/D')}` | Acumulado do evento vs. núcleo convectivo mais recente |",
        "",
        "### Distribuição Pluviométrica por Estação Monitorada (Defesa Civil SC)",
        "",
        "| Estação / Setor da Bacia | Acumulado 24h | Recente 6h |",
        "| :--- | :---: | :---: |",
        *(linhas_estacoes or ["| Sem detalhamento por estação | — | — |"]),
        "",
        "---",
        "",
        "## 2. Confronto com a Base Científica (`docs/base_cientifica_bacia_tubarao.md`)",
        "",
        f"* **Tempo até a subida inicial (`horas_ate_subida`):** `{evento.get('horas_ate_subida', 'N/D')} h`",
        f"* **Lag observado até o pico (`horas_ate_pico`):** {enquadramento_lag}",
        (
            f"* **Enquadramento Operacional:** O pico de **`{cota_pico:.1f} cm`** superou a **Cota de Atenção oficial (`350 cm` — CPRM/SGB)**."
            if cota_pico >= 350
            else f"* **Enquadramento Operacional:** O pico de **`{cota_pico:.1f} cm`** permaneceu **abaixo** da **Cota de Atenção oficial (`350 cm` — CPRM/SGB)** e do **Início de Alarme PLAMCON 2025 (`470 cm` na estação 84580500)**."
        ),
        "",
        "---",
        "",
        "## 3. Auditoria Comparativa: Motor `v8` (Produção) vs. `v11c` (Modo Sombra)",
        "",
        "| Horizonte | Motor `v8` (Produção) | Motor `v11c` (Modo Sombra) | Veredito |",
        "| :---: | :--- | :--- | :---: |",
        *linhas_auditoria,
        "",
        "> **Decisão de Governança:** O **`v8`** permanece como motor oficial em produção. O **`v11c`** segue em modo sombra para acúmulo de pares reais de cheia até comprovar ganho estatístico consistente (`IC 95% > 0`).",
        "",
    ]

    arq_saida = base_dir / "relatorios" / f"pos_evento_{ev_id}.md"
    arq_saida.write_text("\n".join(linhas_md), encoding="utf-8")
    return arq_saida


if __name__ == "__main__":
    saida = gerar_relatorio_pos_evento()
    print(f"[OK] Relatorio pos-evento unificado gerado em: {saida}")
    print("-" * 65)
    print(saida.read_text(encoding="utf-8"))
