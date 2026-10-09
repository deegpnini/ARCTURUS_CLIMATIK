# Verificar previsões do shadow mode
import json
from datetime import datetime

with open("/content/drive/MyDrive/ARCTURUS_ML/shadow_log.jsonl") as f:
    logs = [json.loads(l) for l in f.readlines()]

print(f"Total de previsoes no log: {len(logs)}")
for log in logs[-3:]:
    print(json.dumps(log, indent=2, default=str))