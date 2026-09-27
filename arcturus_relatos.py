# -*- coding: utf-8 -*-
"""
ARCTURUS CLIMATIK — Modulo de Relatos da Comunidade
====================================================
Coleta relatos de moradores sobre nivel de rios, como complemento
ao dado oficial (Defesa Civil / Epagri / ANA) em locais onde nao
existe estacao de monitoramento.

Principio ARCTURUS: um relato de morador NUNCA e tratado como dado
oficial. Fica marcado como "confiavel: false" e "fonte: comunidade"
no cache, e o painel exibe isso separado.

Modulo puro: nao importa nada de telegram.
Toda interacao de interface fica em bot_v7.py.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

# ============================================================
# Configuracao
# ============================================================
BASE = Path.home() / "ARCTURUS_CLIMATIK"
RELATOS_PATH = BASE / "cache" / "arcturus_relatos.json"

CIDADES_FIXAS = [
    "Blumenau",
    "Rio do Sul",
    "Itajai",
    "Tubarao",
    "Criciuma",
]

NIVEIS = {
    "normal":          "🟢 Normal",
    "cheio":           "🟡 Cheio, sem transbordar",
    "transbordando":   "🔴 Transbordando",
    "seco":            "⚪ Seco / baixo",
}

COOLDOWN_SEGUNDOS = 3600        # 1 hora
MAX_RELATOS_POR_CIDADE = 20
MAX_DESCRICAO_CHARS = 280


# ============================================================
# Persistencia
# ============================================================
def carregar_relatos():
    """
    Le o cache de relatos. Se nao existe ou esta corrompido,
    retorna estrutura vazia em vez de tentar adivinhar conteudo.
    """
    if not RELATOS_PATH.exists():
        return {"atualizado_em": None, "por_cidade": {}}
    try:
        with open(RELATOS_PATH, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if not isinstance(dados, dict) or "por_cidade" not in dados:
            return {"atualizado_em": None, "por_cidade": {}}
        return dados
    except (json.JSONDecodeError, OSError):
        # Nunca inventa: cache corrompido = cache vazio
        return {"atualizado_em": None, "por_cidade": {}}


def salvar_relatos(dados):
    """Escrita atomica: grava em .tmp e move por cima."""
    RELATOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    dados["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    tmp = str(RELATOS_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RELATOS_PATH)


# ============================================================
# Regras de negocio
# ============================================================
def pode_reportar(user_id, cidade):
    """
    Verifica cooldown. Retorna (pode: bool, segundos_restantes: int).
    Cooldown por usuario + por cidade.
    """
    dados = carregar_relatos()
    entradas = dados["por_cidade"].get(cidade, [])
    agora = time.time()
    for r in entradas:
        if r.get("user_id") == user_id:
            delta = agora - r.get("timestamp_unix", 0)
            if delta < COOLDOWN_SEGUNDOS:
                return False, int(COOLDOWN_SEGUNDOS - delta)
    return True, 0


def adicionar_relato(user_id, username, cidade, nivel, descricao=""):
    """
    Adiciona relato apos validar cooldown e nivel.
    Retorna (ok: bool, mensagem: str).
    """
    if nivel not in NIVEIS:
        return False, "Nivel invalido."
    if not cidade or not isinstance(cidade, str):
        return False, "Cidade invalida."
    if not isinstance(user_id, int) or user_id <= 0:
        return False, "Usuario invalido."

    cidade = cidade.strip()
    if not (2 <= len(cidade) <= 80):
        return False, "Nome de cidade invalido."

    descricao = (descricao or "").strip()[:MAX_DESCRICAO_CHARS]

    pode, restante = pode_reportar(user_id, cidade)
    if not pode:
        minutos = max(1, restante // 60)
        return False, f"Voce ja reportou {cidade} recentemente. Tente em ~{minutos} min."

    dados = carregar_relatos()
    entrada = {
        "cidade": cidade,
        "nivel": nivel,
        "descricao": descricao,
        "fonte": "comunidade",
        "confiavel": False,
        "user_id": user_id,
        "username": username or "",
        "timestamp_unix": time.time(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    lista = dados["por_cidade"].setdefault(cidade, [])
    lista.insert(0, entrada)
    dados["por_cidade"][cidade] = lista[:MAX_RELATOS_POR_CIDADE]

    salvar_relatos(dados)
    return True, "Relato registrado."


# ============================================================
# Consultas (para o painel e para o bot)
# ============================================================
def listar_cidades_com_relato():
    """Retorna lista de cidades (com contagem), ordenada por volume."""
    dados = carregar_relatos()
    por_cidade = dados.get("por_cidade", {})
    itens = [(cidade, len(entradas)) for cidade, entradas in por_cidade.items() if entradas]
    itens.sort(key=lambda x: x[1], reverse=True)
    return itens


def listar_relatos_cidade(cidade):
    """Retorna relatos de uma cidade, mais recentes primeiro."""
    dados = carregar_relatos()
    return dados["por_cidade"].get(cidade, [])


def contar_relatos_por_nivel(cidade):
    """Contagem por nivel para uma cidade."""
    contagem = {n: 0 for n in NIVEIS}
    for r in listar_relatos_cidade(cidade):
        n = r.get("nivel")
        if n in contagem:
            contagem[n] += 1
    return contagem


def resumo_ultimo_relato(cidade):
    """
    Retorna (nivel_human, timestamp, descricao) do ultimo relato,
    ou None se nao houver.
    """
    relatos = listar_relatos_cidade(cidade)
    if not relatos:
        return None
    r = relatos[0]
    return {
        "nivel": r.get("nivel"),
        "nivel_human": NIVEIS.get(r.get("nivel"), "?"),
        "timestamp": r.get("timestamp"),
        "descricao": r.get("descricao", ""),
    }
