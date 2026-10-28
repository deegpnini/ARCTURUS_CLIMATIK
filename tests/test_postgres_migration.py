import json
import tempfile
import unittest
from pathlib import Path

from src.relatorios.migrar_postgres import carregar_features_geojson


class GeoJSONMigrationTests(unittest.TestCase):
    def test_reads_polygon_feature_collection(self):
        document = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "flood-2019-1",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
                    },
                    "properties": {},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "flood.geojson"
            path.write_text(json.dumps(document), encoding="utf-8")
            features = carregar_features_geojson(path)

        self.assertEqual(len(features), 1)
        self.assertEqual(features[0][0], "flood-2019-1")
        self.assertEqual(json.loads(features[0][1])["type"], "Polygon")

    def test_rejects_non_polygon_geometry(self):
        document = {
            "type": "Feature",
            "geometry": {"type": "MultiPolygon", "coordinates": []},
            "properties": {},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "flood.geojson"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "não é Polygon"):
                carregar_features_geojson(path)

    def test_rejects_empty_feature_collection(self):
        document = {"type": "FeatureCollection", "features": []}
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "flood.geojson"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "não contém polígonos"):
                carregar_features_geojson(path)


if __name__ == "__main__":
    unittest.main()
