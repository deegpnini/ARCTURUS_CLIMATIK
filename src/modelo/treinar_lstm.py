import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
from sklearn.preprocessing import StandardScaler

torch.manual_seed(42)
np.random.seed(42)

BASE = Path(__file__).resolve().parents[2]
raw = pd.read_csv(BASE / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True).sort_index()
raw = raw.loc[:, ~raw.columns.duplicated()]
raw = raw[~raw.index.duplicated(keep="last")]
g = raw.resample("15min").last()
c = g["cota"]

# Features (cota + deltas + chuva da bacia)
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

# Normalizar todas as features
scaler_X = StandardScaler()
X_scaled = scaler_X.fit_transform(X.values)

# Alvo: cota futura (1 passo à frente = 15 min)
scaler_y = StandardScaler()
y_scaled = scaler_y.fit_transform(c.reindex(X.index).values.reshape(-1, 1)).flatten()

# Criar sequências (janela de 48 passos = 12h)
def criar_sequencias(X, y, janela=48):
    Xs, ys = [], []
    for i in range(len(X) - janela):
        Xs.append(X[i:i+janela])
        ys.append(y[i+janela])
    return np.array(Xs), np.array(ys)

Xs, ys = criar_sequencias(X_scaled, y_scaled, janela=48)
print(f"Sequências criadas: {Xs.shape}")

# Split cronológico (80% treino, 20% teste)
split = int(len(Xs) * 0.8)
X_train, X_test = Xs[:split], Xs[split:]
y_train, y_test = ys[:split], ys[split:]

class RiverDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.FloatTensor(X)
        self.y = torch.FloatTensor(y)
    def __len__(self):
        return len(self.X)
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

train_loader = DataLoader(RiverDataset(X_train, y_train), batch_size=64, shuffle=True)

class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_size=64, num_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, 
                            batch_first=True, dropout=dropout)
        self.fc = nn.Linear(hidden_size, 1)
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

modelo = LSTMModel(input_size=Xs.shape[2])
otimizador = torch.optim.Adam(modelo.parameters(), lr=0.0005)
criterio = nn.MSELoss()

print("Treinando LSTM (com gradient clipping)...")
for epoch in range(30):
    modelo.train()
    total_loss = 0
    for X_batch, y_batch in train_loader:
        otimizador.zero_grad()
        pred = modelo(X_batch).squeeze()
        loss = criterio(pred, y_batch)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(modelo.parameters(), max_norm=1.0)  # Gradient clipping
        otimizador.step()
        total_loss += loss.item()
    
    if (epoch + 1) % 5 == 0:
        print(f"  Epoch {epoch+1}/30 | Loss: {total_loss/len(train_loader):.6f}")

# Avaliar
modelo.eval()
with torch.no_grad():
    X_t = torch.FloatTensor(X_test)
    pred_test = modelo(X_t).squeeze().numpy()

# Desnormalizar
pred_real = scaler_y.inverse_transform(pred_test.reshape(-1, 1)).flatten()
y_real = scaler_y.inverse_transform(y_test.reshape(-1, 1)).flatten()

rmse = np.sqrt(np.mean((pred_real - y_real)**2))
mae = np.mean(np.abs(pred_real - y_real))

print(f"\n=== RESULTADO LSTM (1 passo à frente = 15 min) ===")
print(f"RMSE: {rmse:.2f} cm")
print(f"MAE: {mae:.2f} cm")
print(f"Total de amostras de teste: {len(y_real)}")
