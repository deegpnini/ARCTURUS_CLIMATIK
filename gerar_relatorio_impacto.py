import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ROAD_CSV = ROOT / "resultados" / "dano_inundacao_tubarao_2019_road_stats.csv"
BUILDING_CSV = ROOT / "resultados" / "dano_inundacao_tubarao_2019_building_stats.csv"
REPORT_PATH = ROOT / "docs" / "RELATORIO_IMPACTO_2019.md"


def read_csv_rows(path):
    if not path.is_file():
        raise FileNotFoundError(f"CSV nao encontrado: {path}")
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        return list(csv.DictReader(csv_file))


def main():
    road_rows = read_csv_rows(ROAD_CSV)
    building_rows = read_csv_rows(BUILDING_CSV)

    required_road_columns = {"Total Length (km)", "Flooded Length (km)"}
    if not road_rows or not required_road_columns.issubset(road_rows[0]):
        raise ValueError(
            f"CSV de estradas deve conter as colunas: "
            f"{', '.join(sorted(required_road_columns))}"
        )
    if not building_rows:
        raise ValueError("CSV de predios nao contem estatisticas.")

    road_total_km = sum(float(row["Total Length (km)"]) for row in road_rows)
    road_affected_km = sum(float(row["Flooded Length (km)"]) for row in road_rows)
    road_percent = road_affected_km / road_total_km * 100 if road_total_km else 0

    building_stats = building_rows[0]
    required_building_columns = {"Total Buildings", "Flooded Buildings", "Flooded %"}
    if not required_building_columns.issubset(building_stats):
        raise ValueError(
            f"CSV de predios deve conter as colunas: "
            f"{', '.join(sorted(required_building_columns))}"
        )

    buildings_total = int(float(building_stats["Total Buildings"]))
    buildings_affected = int(float(building_stats["Flooded Buildings"]))
    buildings_percent = float(building_stats["Flooded %"])

    report = f"""# Relatório de Impacto da Inundação de 2019

**Data do evento:** Maio de 2019 — Rio Tubarão

## Impacto em infraestrutura

- **Estradas afetadas:** {road_affected_km:.2f} km ({road_percent:.2f}% do total de {road_total_km:.2f} km analisados).
- **Prédios afetados:** {buildings_affected} de {buildings_total} ({buildings_percent:.2f}%).

## Conclusão

O evento de 2019 afetou **{road_affected_km:.2f} km de vias** e **{buildings_affected} edificações** na área analisada.
"""

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"Relatorio salvo em: {REPORT_PATH}")


if __name__ == "__main__":
    main()
