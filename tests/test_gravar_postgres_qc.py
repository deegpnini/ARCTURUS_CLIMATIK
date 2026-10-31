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
        if query.lstrip().startswith("INSERT"):
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
        """Leitura SUSPEITO DEVE ser persistida (para trilha de auditoria)."""
        connection = FakeConnection(cota_anterior=80.0)
        qc = gravar_leitura(
            {"delta_60m": 1.5, "aceleracao_az": 0.2, "regime": "ATENCAO"},
            {"cota_cm": 111.0, "qc": "VALIDO"},
            connection_factory=lambda: connection,
        )

        self.assertEqual(qc, "SUSPEITO")
        # A leitura FOI persistida com o QC SUSPEITO
        self.assertIsNotNone(connection.cursor_instance.inserted_values)
        self.assertEqual(connection.cursor_instance.inserted_values[1], 111.0)
        self.assertEqual(connection.cursor_instance.inserted_values[-1], "SUSPEITO")
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
        self.assertIsNotNone(connection.cursor_instance.inserted_values)
        self.assertIsNone(connection.cursor_instance.inserted_values[1])
        self.assertEqual(connection.cursor_instance.inserted_values[-1], "CORROMPIDO")


if __name__ == "__main__":
    unittest.main()
