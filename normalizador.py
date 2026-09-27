#!/usr/bin/env python3
"""
Normalizador universal para dados ANA.
Nao destroi o RAW. Converte para tipos consistentes.
"""

def numero(v):
    """Converte qualquer valor para float ou None.
    Aceita: None, '', '220.0', 220, '0', '16,20' (virgula).
    Retorna None se nao for numero.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(',', '.')
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def texto(v):
    """Converte para string limpa."""
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def inteiro(v):
    """Converte para inteiro ou None."""
    n = numero(v)
    return int(n) if n is not None else None


if __name__ == "__main__":
    # Testes
    testes = [
        ("220.0", 220.0),
        (220, 220.0),
        ("0", 0.0),
        ("", None),
        (None, None),
        ("16,20", 16.2),
        ("-28.0", -28.0),
        ("abc", None),
    ]
    print("=== TESTES normalizador.numero() ===")
    for entrada, esperado in testes:
        resultado = numero(entrada)
        ok = "OK" if resultado == esperado else "FALHOU"
        print(f"  numero({entrada!r}) = {resultado!r}  [{ok}]")
