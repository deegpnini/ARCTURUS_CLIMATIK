#!/usr/bin/env python3
"""
ARCTURUS ML — Gradient Boosting em Python puro.
Sem pandas, sem numpy, sem xgboost, sem sklearn.
v2 - corrigido bug de indexacao.
"""
import csv, json, os, math, random
from datetime import datetime
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

def carregar(horizonte):
    path = f"{CACHE}/dataset_{horizonte}.csv"
    with open(path) as f:
        rows = list(csv.DictReader(f))
    return rows

def preparar(rows, horizonte):
    cols_remover = {'timestamp', f'target_{horizonte}'}
    cols = [c for c in rows[0].keys() if c not in cols_remover]
    X = []
    y = []
    ts = []
    for r in rows:
        t = r.get(f'target_{horizonte}', '')
        if not t: continue
        try: yv = float(t)
        except: continue
        xv = []
        for c in cols:
            v = r.get(c, '')
            if v == '':
                xv.append(None)
            else:
                try: xv.append(float(v))
                except: xv.append(None)
        X.append(xv)
        y.append(yv)
        ts.append(r['timestamp'])
    return X, y, ts, cols

def split_temporal(ts):
    idx_tr = [i for i, t in enumerate(ts) if t < '2025-11-08']
    idx_va = [i for i, t in enumerate(ts) if '2025-11-08' <= t < '2026-07-14']
    idx_te = [i for i, t in enumerate(ts) if '2026-07-22' <= t < '2026-09-15']
    idx_op = [i for i, t in enumerate(ts) if t >= '2026-09-15']
    return idx_tr, idx_va, idx_te, idx_op

# ============================================================
# ARVORE DE DECISAO SIMPLES (CART)
# ============================================================
class Arvore:
    def __init__(self, max_depth=4, min_samples=20):
        self.max_depth = max_depth
        self.min_samples = min_samples
        self.arvore = None

    def fit(self, X, y, indices):
        self.arvore = self._construir(X, y, indices, 0)

    def _construir(self, X, y, indices, depth):
        if depth >= self.max_depth or len(indices) < self.min_samples:
            return {'folha': True, 'valor': sum(y[i] for i in indices) / len(indices)}

        n_features = len(X[0])
        melhor_feature = None
        melhor_threshold = None
        melhor_erro = float('inf')

        features_testar = list(range(n_features))
        if n_features > 8:
            features_testar = random.sample(features_testar, 8)

        for feat in features_testar:
            valores = [X[i][feat] for i in indices if X[i][feat] is not None]
            if len(valores) < 10:
                continue
            valores.sort()
            thresholds = [valores[int(len(valores)*p)] for p in [0.25, 0.5, 0.75]]

            for thr in thresholds:
                esq = [i for i in indices if X[i][feat] is not None and X[i][feat] <= thr]
                dir_ = [i for i in indices if X[i][feat] is not None and X[i][feat] > thr]
                if len(esq) < 5 or len(dir_) < 5:
                    continue
                erro = self._erro(y, esq) + self._erro(y, dir_)
                if erro < melhor_erro:
                    melhor_erro = erro
                    melhor_feature = feat
                    melhor_threshold = thr

        if melhor_feature is None:
            return {'folha': True, 'valor': sum(y[i] for i in indices) / len(indices)}

        esq = [i for i in indices if X[i][melhor_feature] is not None and X[i][melhor_feature] <= melhor_threshold]
        dir_ = [i for i in indices if X[i][melhor_feature] is not None and X[i][melhor_feature] > melhor_threshold]

        return {
            'folha': False,
            'feature': melhor_feature,
            'threshold': melhor_threshold,
            'esq': self._construir(X, y, esq, depth+1),
            'dir': self._construir(X, y, dir_, depth+1),
        }

    def _erro(self, y, indices):
        if not indices: return 0
        media = sum(y[i] for i in indices) / len(indices)
        return sum((y[i] - media)**2 for i in indices)

    def predict(self, x):
        no = self.arvore
        while not no['folha']:
            v = x[no['feature']]
            if v is None:
                no = no['esq'] if no['esq']['folha'] else no['dir']
                continue
            if v <= no['threshold']:
                no = no['esq']
            else:
                no = no['dir']
        return no['valor']

# ============================================================
# GRADIENT BOOSTING SIMPLIFICADO
# ============================================================
class GradientBoosting:
    def __init__(self, n_estimators=30, learning_rate=0.1, max_depth=4):
        self.n_estimators = n_estimators
        self.lr = learning_rate
        self.max_depth = max_depth
        self.arvores = []
        self.base = 0

    def fit(self, X, y, indices):
        self.base = sum(y[i] for i in indices) / len(indices)
        pred = [self.base] * len(X)
        for it in range(self.n_estimators):
            y_res = [y[i] - pred[i] for i in range(len(y))]
            arv = Arvore(max_depth=self.max_depth, min_samples=20)
            arv.fit(X, y_res, indices)
            self.arvores.append(arv)
            for i in indices:
                pred[i] += self.lr * arv.predict(X[i])
            mae_t = sum(abs(y[i] - pred[i]) for i in indices) / len(indices)
            print(f"  it {it+1:3d}: MAE_treino = {mae_t:.2f}")
        return pred

    def predict(self, x):
        p = self.base
        for arv in self.arvores:
            p += self.lr * arv.predict(x)
        return p

# ============================================================
# METRICAS (agora recebem lista completa)
# ============================================================
def mae_full(y, pred):
    """y e pred sao listas completas, comparadas 1-a-1."""
    n = len(y)
    s = 0
    c = 0
    for i in range(n):
        if y[i] is None or pred[i] is None: continue
        s += abs(y[i] - pred[i])
        c += 1
    return s / c if c else 0

def mae_subset(y, pred, indices):
    """Avalia so nos indices passados."""
    s = 0
    c = 0
    for i in indices:
        if y[i] is None or pred[i] is None: continue
        s += abs(y[i] - pred[i])
        c += 1
    return s / c if c else 0

def rmse_subset(y, pred, indices):
    s = 0
    c = 0
    for i in indices:
        if y[i] is None or pred[i] is None: continue
        s += (y[i] - pred[i])**2
        c += 1
    return math.sqrt(s / c) if c else 0

# ============================================================
# MAIN
# ============================================================
def main():
    for h in ['1h']:
        print("="*70)
        print(f"HORIZONTE {h}")
        print("="*70)

        rows = carregar(h)
        X, y, ts, cols = preparar(rows, h)
        print(f"Exemplos: {len(X)}")

        idx_tr, idx_va, idx_te, idx_op = split_temporal(ts)
        print(f"Treino: {len(idx_tr)} | Val: {len(idx_va)} | Teste: {len(idx_te)} | Oper: {len(idx_op)}")
        print()

        # Baseline persistencia: pred[i] = cota_atual[i]
        idx_cota = cols.index('cota')
        persist_pred = []
        for i in range(len(X)):
            v = X[i][idx_cota]
            persist_pred.append(v if v is not None else 0)

        print("=== BASELINE PERSISTENCIA ===")
        print(f"MAE treino: {mae_subset(y, persist_pred, idx_tr):.2f}")
        print(f"MAE val:    {mae_subset(y, persist_pred, idx_va):.2f}")
        print(f"MAE teste:  {mae_subset(y, persist_pred, idx_te):.2f}")
        print()

        print("=== TREINANDO GRADIENT BOOSTING (30 estimadores) ===")
        gb = GradientBoosting(n_estimators=30, learning_rate=0.1, max_depth=4)
        gb.fit(X, y, idx_tr)
        print()

        # Predicoes para todas as linhas
        gb_pred = [gb.predict(X[i]) for i in range(len(X))]

        print("=== AVALIACAO GBM ===")
        print(f"MAE treino: {mae_subset(y, gb_pred, idx_tr):.2f}")
        print(f"MAE val:    {mae_subset(y, gb_pred, idx_va):.2f}")
        print(f"MAE teste:  {mae_subset(y, gb_pred, idx_te):.2f}")
        print(f"RMSE teste: {rmse_subset(y, gb_pred, idx_te):.2f}")
        print()

        # Comparacao no teste
        pers_test = mae_subset(y, persist_pred, idx_te)
        gb_test = mae_subset(y, gb_pred, idx_te)
        ganho = (1 - gb_test / pers_test) * 100 if pers_test else 0
        print("=== COMPARACAO (teste) ===")
        print(f"Baseline persistencia: {pers_test:.2f} cm")
        print(f"GBM:                   {gb_test:.2f} cm")
        print(f"GANHO: {ganho:+.1f}%")

if __name__ == "__main__":
    main()
