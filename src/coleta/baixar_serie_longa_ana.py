import hidroana
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

print("Baixando série histórica longa da ANA (84580000)...")
# O hidroana baixa séries convencionais (diárias) de cota
hidroana.get_conv_data_list(
    list_est=['84580000'],
    d_i='1939-01-01',
    d_f='2026-10-24',
    tipo='1',  # 1 = cota
    caminho=str(BASE / "data" / "ana_longa"),
    cons=1,
    disp=False
)
print("Concluído. Verifique a pasta data/ana_longa/")
