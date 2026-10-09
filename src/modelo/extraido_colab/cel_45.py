from google.colab import files
import json
import numpy as np
import pandas as pd
import lightgbm as lgb

print("Faça upload dos 4 arquivos:")
print("  - dataset_1h.csv")
print("  - dataset_3h.csv")
print("  - dataset_6h.csv")
print("  - split_v3.json")
uploaded = files.upload()
print(f"\n{len(uploaded)} arquivos recebidos:")
for name in uploaded:
    print(f"  - {name}")