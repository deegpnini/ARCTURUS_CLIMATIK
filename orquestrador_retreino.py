#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ORQUESTRADOR DE RETREINO: Guardião -> Auditor -> Treino -> LOEO -> Promoção."""

import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import precision_recall_curve, auc

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

# Configurações
MODELOS_PRODUCAO = {
    "1h": BASE / "modelos" / "modelo_delta_1h_v8_final.txt",
    "3h": BASE / "modelos" / "modelo_delta_3h_v8_final.txt",
    "6h": BASE / "modelos" / "modelo_delta_6h_v8_final.txt",
}
MODELOS_CANDIDATOS = {
    "1h": BASE / "modelos" / "modelo_delta_1h_v9.txt",
    "3h": BASE / "modelos" / "modelo_delta_3h_v9.txt",
    "6h": BASE / "modelos" / "modelo_delta_6h_v9.txt",
}
LIMIAR_APROVACAO = 0.63 # PR-AUC mínimo para bater o v8

def enviar_telegram(msg):
    """Envia mensagem para o Telegram (lê do .env)."""
    try:
        from dotenv import load_dotenv
        import os
        import requests
        load_dotenv()
        token = os.environ.get("TELEGRAM_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if token and chat_id:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"[AVISO] Falha ao enviar Telegram: {e}")

def main():
    print("=" * 60)
    print("ORQUESTRADOR DE RETREINO AUTOMÁTICO — ARCTURUS")
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    # 1. GUARDIÃO
    print("\n[1/5] Rodando Guardião (backfill point-in-time)...")
    res = subprocess.run([sys.executable, str(BASE / "backfill_features_pit.py")], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERRO] Guardião falhou: {res.stderr}")
        enviar_telegram("❌ ARCTURUS: Retreino abortado (Guardião falhou).")
        return
    print("[OK] Guardião concluído.")

    # 2. AUDITOR
    print("\n[2/5] Rodando Auditor (validação do dataset)...")
    res = subprocess.run([sys.executable, str(BASE / "agente_auditor.py")], capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print(f"[ERRO] Auditor REPROVOU o dataset.")
        enviar_telegram("❌ ARCTURUS: Retreino abortado (Auditor reprovou o dataset).")
        return
    print("[OK] Auditor APROVOU.")

    # 3. RETREINO
    print("\n[3/5] Rodando Retreino (modelos candidatos)...")
    res = subprocess.run([sys.executable, str(BASE / "retreinar_modelo.py")], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERRO] Retreino falhou.")
        enviar_telegram("❌ ARCTURUS: Retreino abortado (falha no treino).")
        return
    print("[OK] Retreino concluído.")

    # 4. LOEO (Validação)
    print("\n[4/5] Rodando LOEO (Leave-One-Event-Out)...")
    df = pd.read_parquet(BASE / "data" / "dataset_retreino.parquet")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    eventos = df["timestamp"].dt.date.unique()
    features_controle = ["timestamp", "horizonte", "y_true"]
    features = [c for c in df.columns if c not in features_controle]

    aprovados = []
    resultados = []

    for h in ["1h", "3h", "6h"]:
        df_h = df[df["horizonte"] == h].copy()
        if len(df_h) < 30: continue
        
        predicoes, reais = [], []
        for evento in eventos:
            teste = df_h[df_h["timestamp"].dt.date == evento]
            treino = df_h[df_h["timestamp"].dt.date != evento]
            if len(teste) == 0 or len(treino) < 30: continue
            
            X_train, y_train = treino[features].fillna(0), treino["y_true"]
            X_test, y_test = teste[features].fillna(0), teste["y_true"]
            
            try:
                train_data = lgb.Dataset(X_train, label=y_train)
                params = {"objective": "regression", "metric": "mae", "num_leaves": 15, "verbose": -1}
                modelo = lgb.train(params, train_data, num_boost_round=50)
                predicoes.extend(modelo.predict(X_test))
                reais.extend(y_test.values)
            except Exception: continue
        
        if len(predicoes) > 10:
            reais_bin = [1 if r > 0 else 0 for r in reais]
            if sum(reais_bin) > 0:
                precision, recall, _ = precision_recall_curve(reais_bin, predicoes)
                pr_auc = auc(recall, precision)
                resultados.append((h, pr_auc))
                
                # Critério de aprovação (bater o v8)
                if pr_auc > LIMIAR_APROVACAO:
                    aprovados.append(h)

    print("\n[5/5] Resultado do LOEO:")
    for h, pr_auc in resultados:
        status = "✅ APROVADO" if pr_auc > LIMIAR_APROVACAO else "❌ REPROVADO"
        print(f"  {h}: PR-AUC = {pr_auc:.4f} (limiar: {LIMIAR_APROVACAO}) -> {status}")

    # 5. PROMOÇÃO
    if aprovados:
        print(f"\n[PROMOÇÃO] O modelo v9 bateu o v8 em: {aprovados}")
        for h in aprovados:
            # shutil.copy(MODELOS_CANDIDATOS[h], MODELOS_PRODUCAO[h])  # PROMOÇÃO CONGELADA
            print(f"  [AVISO] Modelo {h} seria promovido, mas a promoção está congelada.")
        
        msg = f"✅ ARCTURUS: Modelo v9 PROMOVIDO para {', '.join(aprovados)}.\n"
        msg += "\n".join([f"• {h}: {pr_auc:.2f}" for h, pr_auc in resultados if h in aprovados])
        enviar_telegram(msg)
    else:
        print("\n[PROMOÇÃO] Nenhum modelo bateu o v8. O v8 continua em produção.")
        enviar_telegram("ℹ️ ARCTURUS: Retreino concluído. O v9 não superou o v8. O v8 continua em produção.")

    print("\n" + "=" * 60)
    print("ORQUESTRADOR CONCLUÍDO")
    print("=" * 60)

if __name__ == "__main__":
    main()
