import unittest
from src.relatorios.gravar_postgres import gravar_leitura

class FakeCursor:
    def __init__(self, cota_anterior):
        self.cota_anterior = cota_anterior
        self.inserted_values = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, values=None):
        # Se for INSERT, guarda os valores. Se for SELECT, guarda os valores (que é o que o fetchone usa)
        if "INSERT" in query.upper():
            self.inserted_values = values

    def fetchone(self):
        return (self.cota_anterior,) if self.cota_anterior is not None else None


class FakeConnection:
    def __init__(self, cota_anterior):
        self.cursor_instance = FakeCursor(cota_anterior)
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class GravarPostgresQCTests(unittest.TestCase):
    def test_suspect_jump_is_persisted_with_qc_flag(self):
        connection = FakeConnection(cota_anterior=80.0)
        qc = gravar_leitura(
            {"delta_60m": 1.5, "aceleracao_az": 0.2, "regime": "ATENCAO"},
            {"cota_cm": 111.0, "qc": "VALIDO", "data_extracao": "2026-10-31T15:15:16"},
            connection_factory=lambda: connection,
        )

        self.assertEqual(qc, "SUSPEITO")
        vals = connection.cursor_instance.inserted_values
        self.assertIsNotNone(vals, "O INSERT nao foi chamado!")
        self.assertEqual(vals[2], 111.0)          # cota_cm
        self.assertEqual(vals[5], "ATENCAO")      # regime
        self.assertEqual(vals[6], "SUSPEITO")     # qc
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_missing_cota_is_preserved_as_null(self):
        connection = FakeConnection(cota_anterior=None)
        qc = gravar_leitura(
            {},
            {},
            connection_factory=lambda: connection,
        )

        self.assertEqual(qc, "CORROMPIDO")
        vals = connection.cursor_instance.inserted_values
        self.assertIsNotNone(vals)
        self.assertIsNone(vals[2])               # cota_cm
        self.assertEqual(vals[6], "CORROMPIDO")  # qc

    def test_empty_regime_defaults_to_desconhecido(self):
        connection = FakeConnection(cota_anterior=80.0)
        gravar_leitura(
            {},
            {"cota_cm": 85.0, "data_extracao": "2026-10-31T15:15:16"},
            connection_factory=lambda: connection,
        )
        vals = connection.cursor_instance.inserted_values
        self.assertEqual(vals[5], "DESCONHECIDO")

    def test_ts_coleta_is_persisted_from_data_extracao(self):
        connection = FakeConnection(cota_anterior=80.0)
        gravar_leitura(
            {"delta_60m": 1.0, "regime": "NORMAL"},
            {"cota_cm": 85.0, "data_extracao": "2026-10-31T15:15:16"},
            connection_factory=lambda: connection,
        )
        vals = connection.cursor_instance.inserted_values
        self.assertEqual(vals[1], "2026-10-31T15:15:16")


if __name__ == "__main__":
    unittest.main()
