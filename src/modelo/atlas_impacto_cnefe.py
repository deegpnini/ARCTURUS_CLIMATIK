import pandas as pd
import geopandas as gpd
import json
import requests
import zipfile
import io
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar a mancha de inundação
mancha = gpd.read_file(BASE / "cache" / "mancha_2019.geojson").to_crs("EPSG:4326")
print(f"✅ Mancha carregada: {len(mancha)} polígonos")

# 2. Baixar o CNEFE (Censo 2022) para SC (URL CORRETA)
cnefe_url = "https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/SC.zip"
print("Baixando CNEFE (SC)...")
try:
    r = requests.get(cnefe_url, timeout=300)  # 5 min de timeout (arquivo grande)
    if r.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            # O CNEFE tem um CSV por município
            # Tubarão: código IBGE 4218707
            arquivo_tubarao = [f for f in z.namelist() if "4218707" in f]
            if arquivo_tubarao:
                with z.open(arquivo_tubarao[0]) as f:
                    df_cnefe = pd.read_csv(f, sep=";", encoding="latin1", dtype=str)
                print(f"✅ CNEFE (Tubarão): {len(df_cnefe)} registros")
            else:
                print("⚠️ Arquivo de Tubarão não encontrado no CNEFE.")
                exit(1)
    else:
        print(f"⚠️ Erro ao baixar CNEFE: {r.status_code}")
        exit(1)
except Exception as e:
    print(f"⚠️ Erro no download do CNEFE: {e}")
    exit(1)

# 3. Filtrar escolas (4) e estabelecimentos de saúde (5)
# (As colunas do CNEFE são: COD_ESPECIE, LATITUDE, LONGITUDE, etc.)
df_cnefe["COD_ESPECIE"] = df_cnefe["COD_ESPECIE"].astype(int)
df_cnefe["LATITUDE"] = pd.to_numeric(df_cnefe["LATITUDE"], errors="coerce")
df_cnefe["LONGITUDE"] = pd.to_numeric(df_cnefe["LONGITUDE"], errors="coerce")

escolas = df_cnefe[df_cnefe["COD_ESPECIE"] == 4].dropna(subset=["LATITUDE", "LONGITUDE"])
saude = df_cnefe[df_cnefe["COD_ESPECIE"] == 5].dropna(subset=["LATITUDE", "LONGITUDE"])
print(f"✅ Escolas: {len(escolas)} encontradas")
print(f"✅ Estabelecimentos de saúde: {len(saude)} encontrados")

# 4. Cruzar com a mancha de 2019
def cruzar_com_mancha(df, nome):
    if len(df) == 0:
        return 0
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["LONGITUDE"], df["LATITUDE"]), crs="EPSG:4326")
    afetados = gpd.sjoin(gdf, mancha, how="inner", predicate="within")
    afetados = afetados.drop_duplicates(subset=["LATITUDE", "LONGITUDE"])
    print(f"✅ {nome} afetados: {len(afetados)} de {len(df)}")
    return len(afetados)

escolas_afetadas = cruzar_com_mancha(escolas, "Escolas")
saude_afetadas = cruzar_com_mancha(saude, "Estabelecimentos de saúde")

# 5. Estimar a população afetada
edificacoes_afetadas = 1290
populacao_estimada = edificacoes_afetadas * 3

# 6. Salvar o relatório
relatorio = {
    "evento": "Maio/2019",
    "edificacoes_afetadas": edificacoes_afetadas,
    "escolas_afetadas": escolas_afetadas,
    "saude_afetadas": saude_afetadas,
    "populacao_estimada": populacao_estimada,
}
with open(BASE / "resultados" / "atlas_impacto_2019_cnefe.json", "w") as f:
    json.dump(relatorio, f, indent=2)

print("\n=== A.C. ATLAS (IMPACTO 2019, CNEFE) ===")
print(json.dumps(relatorio, indent=2))
print(f"\n✅ Relatório salvo em: resultados/atlas_impacto_2019_cnefe.json")
