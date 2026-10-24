import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error
import lightgbm as lgb
import xgboost as xgb
import time

torch.manual_seed(42)
np.random.seed(42)

BASE = Path(__file__).resolve().parents[2]
raw = pd.read_csv(BASE / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True).sort_index()
raw = raw.loc[:, ~raw.columns.duplicated()]
raw = raw[~raw.index.duplicated(keep="last")]
g = raw.resample("15min").last()
c = g["cota"]

X = pd.DataFrame(index=g.index)
X["cota"] = c
X["delta_60m"] = c - c.shift(4)
X["delta_180m"] = c - c.shift(12)
X["aceleracao_1h"] = X["delta_60m"] - (c.shift(4) - c.shift(8))

ch = pd.read_csv(BASE / "data" / "chuva_bacia_openmeteo.csv", index_col=0, parse_dates=True).sort_index()
ch = ch.drop(columns=["braco_norte"], errors="ignore")
media = ch.mean(axis=1)
X["bacia_6h"] = media.rolling(6, min_periods=6).sum().reindex(g.index, method="ffill")
X["bacia_12h"] = media.rolling(12, min_periods=12).sum().reindex(g.index, method="ffill")

X = X.dropna()
y = c.reindex(X.index)

scaler_X = StandardScaler()
scaler_y = StandardScaler()
X_scaled = scaler_X.fit_transform(X.values)
y_scaled = scaler_y.fit_transform(y.values.reshape(-1, 1)).flatten()

def criar_sequencias(X, y, janela=48):
    Xs, ys = [], []
    for i in range(len(X) - janela):
        Xs.append(X[i:i+janela])
        ys.append(y[i+janela])
    return np.array(Xs), np.array(ys)

Xs, ys = criar_sequencias(X_scaled, y_scaled, janela=48)
split = int(len(Xs) * 0.8)
X_train_seq, X_test_seq = Xs[:split], Xs[split:]
y_train_seq, y_test_seq = ys[:split], ys[split:]

X_train_tree = X_scaled[48:48+len(X_train_seq)]
X_test_tree = X_scaled[48+len(X_train_seq):48+len(X_train_seq)+len(X_test_seq)]
y_train_tree = y_scaled[48:48+len(X_train_seq)]
y_test_tree = y_scaled[48+len(X_train_seq):48+len(X_train_seq)+len(X_test_seq)]

print(f"Sequências de treino: {X_train_seq.shape} | Teste: {X_test_seq.shape}")

resultados = {}

class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_size=64, num_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout)
        self.fc = nn.Linear(hidden_size, 1)
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

class GRUModel(nn.Module):
    def __init__(self, input_size, hidden_size=64, num_layers=2, dropout=0.2):
        super().__init__()
        self.gru = nn.GRU(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout)
        self.fc = nn.Linear(hidden_size, 1)
    def forward(self, x):
        out, _ = self.gru(x)
        return self.fc(out[:, -1, :])

class RiverDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.FloatTensor(X)
        self.y = torch.FloatTensor(y)
    def __len__(self): return len(self.X)
    def __getitem__(self, idx): return self.X[idx], self.y[idx]

train_loader = DataLoader(RiverDataset(X_train_seq, y_train_seq), batch_size=64, shuffle=True)
criterio = nn.MSELoss()

# 1. LSTM
print("\n[1/4] Treinando LSTM...")
t0 = time.time()
modelo_lstm = LSTMModel(input_size=Xs.shape[2])
otimizador = torch.optim.Adam(modelo_lstm.parameters(), lr=0.0005)
for epoch in range(15):
    modelo_lstm.train()
    for X_batch, y_batch in train_loader:
        otimizador.zero_grad()
        pred = modelo_lstm(X_batch).squeeze()
        loss = criterio(pred, y_batch)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(modelo_lstm.parameters(), max_norm=1.0)
        otimizador.step()
modelo_lstm.eval()
with torch.no_grad():
    pred_lstm = modelo_lstm(torch.FloatTensor(X_test_seq)).squeeze().numpy()
pred_lstm_real = scaler_y.inverse_transform(pred_lstm.reshape(-1, 1)).flatten()
y_test_real = scaler_y.inverse_transform(y_test_seq.reshape(-1, 1)).flatten()
rmse_lstm = np.sqrt(mean_squared_error(y_test_real, pred_lstm_real))
resultados["LSTM"] = {"RMSE": rmse_lstm, "Tempo": time.time() - t0}

# 2. GRU
print("[2/4] Treinando GRU...")
t0 = time.time()
modelo_gru = GRUModel(input_size=Xs.shape[2])
otimizador_gru = torch.optim.Adam(modelo_gru.parameters(), lr=0.0005)
for epoch in range(15):
    modelo_gru.train()
    for X_batch, y_batch in train_loader:
        otimizador_gru.zero_grad()
        pred = modelo_gru(X_batch).squeeze()
        loss = criterio(pred, y_batch)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(modelo_gru.parameters(), max_norm=1.0)
        otimizador_gru.step()
modelo_gru.eval()
with torch.no_grad():
    pred_gru = modelo_gru(torch.FloatTensor(X_test_seq)).squeeze().numpy()
pred_gru_real = scaler_y.inverse_transform(pred_gru.reshape(-1, 1)).flatten()
rmse_gru = np.sqrt(mean_squared_error(y_test_real, pred_gru_real))
resultados["GRU"] = {"RMSE": rmse_gru, "Tempo": time.time() - t0}

# 3. XGBoost
print("[3/4] Treinando XGBoost...")
t0 = time.time()
modelo_xgb = xgb.XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.05, random_state=42, verbosity=0)
modelo_xgb.fit(X_train_tree, y_train_tree)
pred_xgb = modelo_xgb.predict(X_test_tree)
pred_xgb_real = scaler_y.inverse_transform(pred_xgb.reshape(-1, 1)).flatten()
rmse_xgb = np.sqrt(mean_squared_error(y_test_real, pred_xgb_real))
resultados["XGBoost"] = {"RMSE": rmse_xgb, "Tempo": time.time() - t0}

# 4. LightGBM
print("[4/4] Treinando LightGBM...")
t0 = time.time()
modelo_lgb = lgb.LGBMRegressor(n_estimators=200, max_depth=6, learning_rate=0.05, random_state=42, verbose=-1)
modelo_lgb.fit(X_train_tree, y_train_tree)
pred_lgb = modelo_lgb.predict(X_test_tree)
pred_lgb_real = scaler_y.inverse_transform(pred_lgb.reshape(-1, 1)).flatten()
rmse_lgb = np.sqrt(mean_squared_error(y_test_real, pred_lgb_real))
resultados["LightGBM"] = {"RMSE": rmse_lgb, "Tempo": time.time() - t0}

print("\n" + "="*60)
print("CAMPEONATO DE MODELOS — RMSE (1 passo à frente = 15 min)")
print("="*60)
print(f"{'Modelo':<15} | {'RMSE (cm)':>10} | {'Tempo (s)':>10}")
print("-"*60)
for nome, res in sorted(resultados.items(), key=lambda x: x[1]["RMSE"]):
    print(f"{nome:<15} | {res['RMSE']:>10.2f} | {res['Tempo']:>10.1f}")
print("="*60)
