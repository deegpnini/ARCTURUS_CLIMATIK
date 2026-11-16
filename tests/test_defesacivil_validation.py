from src.coleta.coletar_defesacivil_sc import _ler_colunas, parse_float_br


def test_leitura_defesa_civil_rejeita_chuva_negativa_e_fora_de_faixa():
    assert parse_float_br("12,5", 300) == 12.5
    assert parse_float_br("-1", 300) is None
    assert parse_float_br("301", 300) is None
    assert parse_float_br("nan", 300) is None


def test_cota_da_estacao_e_rotulada_como_altimetrica():
    colunas = [
        "DCSC-00048",
        "Tubarão",
        "15/11/2026 16:00:00",
        "1,0",
        "2,0",
        "3,0",
        "4,0",
        "5,0",
        "6,0",
        "7,0",
        "4,05",
    ]

    dados = _ler_colunas(colunas)

    assert dados["chuva_24h_mm"] == 4.0
    assert dados["cota_altimetrica_m"] == 4.05
    assert "rio_m" not in dados
