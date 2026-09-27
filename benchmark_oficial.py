#!/usr/bin/env python3
"""
ARCTURUS BENCHMARK OFICIAL
Roda 1h/3h/6h com:
- baseline persistencia
- GBM caseiro
- MAE global + MAE em extremos (P95, P99) + MAE na subida
"""
import csv, json, os, math, random
from datetime import datetime

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

def carregar(horizonte):
    path = f"{CACHE}/dataset_{horizonte}.csv"
    with open(path) as f:
        return list(csv.DictReader(f))

def preparar(rows, horizonte):
    cols_remover = {'timestamp', f'target_{horizonte}'}
    cols = [c for c in rows[0].keys() if c not in cols_remover]
    X, y, ts = [], [], []
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
    return idx_tr, idx_va, idx_te

# ============================================================
# ARVORE DE DECISAO
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
            if len(valores) < 10: continue
            valores.sort()
            thresholds = [valores[int(len(valores)*p)] for p in [0.25, 0.5, 0.75]]

            for thr in thresholds:
                esq = [i for i in indices if X[i][feat] is not None and X[i][feat] <= thr]
                dir_ = [i for i in indices if X[i][feat] is not None and X[i][feat] > thr]
                if len(esq) < 5 or len(dir_) < 5: continue
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
            no = no['esq'] if v <= no['threshold'] else no['dir']
        return no['valor']

class GradientBoosting:
    def __init__(self, n_estimators=20, learning_rate=0.1, max_depth=4):
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

    def predict(self, x):
        p = self.base
        for arv in self.arvores:
            p += self.lr * arv.predict(x)
        return p

# ============================================================
# METRICAS
# ============================================================
def mae_idx(y, pred, idx):
    if not idx: return 0
    return sum(abs(y[i] - pred[i]) for i in idx) / len(idx)

def mae_extremos(y, pred, idx, limiar):
    subset = [i for i in idx if y[i] > limiar]
    if not subset: return None, 0
    return sum(abs(y[i] - pred[i]) for i in subset) / len(subset), len(subset)

def mae_subida(y, pred, idx, cols, X, limiar_delta=5.0):
    """MAE so nos exemplos onde a cota subiu muito em 1h."""
    try:
        idx_delta = cols.index('delta_60m')
    except:
        return None, 0
    subset = [i for i in idx if X[i][idx_delta] is not None and X[i][idx_delta] > limiar_delta]
    if not subset: return None, 0
    return sum(abs(y[i] - pred[i]) for i in subset) / len(subset), len(subset)

# ============================================================
# MAIN
# ============================================================
def main():
    resultados = {}

    for h in ['1h', '3h', '6h']:
        print("="*70)
        print(f"HORIZONTE {h}")
        print("="*70)

        rows = carregar(h)
        X, y, ts, cols = preparar(rows, h)
        idx_tr, idx_va, idx_te = split_temporal(ts)

        # P95 e P99 do target
        y_sorted = sorted(y)
        p95 = y_sorted[int(len(y_sorted)*0.95)]
        p99 = y_sorted[int(len(y_sorted)*0.99)]

        print(f"Exemplos: {len(X)} | Treino: {len(idx_tr)} | Val: {len(idx_va)} | Teste: {len(idx_te)}")
        print(f"P95: {p95:.1f} | P99: {p99:.1f}")
        print()

        # Baseline
        idx_cota = cols.index('cota')
        persist = [X[i][idx_cota] if X[i][idx_cota] is not None else 0 for i in range(len(X))]

        # GBM
        print(f"  treinando GBM ({h})...")
        gb = GradientBoosting(n_estimators=20, learning_rate=0.1, max_depth=4)
        gb.fit(X, y, idx_tr)
        gb_pred = [gb.predict(X[i]) for i in range(len(X))]
        print(f"  pronto.")

        # Metricas
        print()
        print(f"  {'Metrica':30s} | {'Persist':10s} | {'GBM':10s}")
        print(f"  {'-'*30} | {'-'*10} | {'-'*10}")

        mae_pers_te = mae_idx(y, persist, idx_te)
        mae_gb_te = mae_idx(y, gb_pred, idx_te)
        print(f"  {'MAE global (teste)':30s} | {mae_pers_te:10.2f} | {mae_gb_te:10.2f}")

        mae_pers_p95, n95 = mae_extremos(y, persist, idx_te, p95)
        mae_gb_p95, _ = mae_extremos(y, gb_pred, idx_te, p95)
        if mae_pers_p95 is not None:
            print(f"  {f'MAE > P95 (n={n95})':30s} | {mae_pers_p95:10.2f} | {mae_gb_p95:10.2f}")

        mae_pers_p99, n99 = mae_extremos(y, persist, idx_te, p99)
        mae_gb_p99, _ = mae_extremos(y, gb_pred, idx_te, p99)
        if mae_pers_p99 is not None:
            print(f"  {f'MAE > P99 (n={n99})':30s} | {mae_pers_p99:10.2f} | {mae_gb_p99:10.2f}")

        mae_pers_sub, n_sub = mae_subida(y, persist, idx_te, cols, X)
        mae_gb_sub, _ = mae_subida(y, gb_pred, idx_te, cols, X)
        if mae_pers_sub is not None:
            print(f"  {f'MAE na subida (n={n_sub})':30s} | {mae_pers_sub:10.2f} | {mae_gb_sub:10.2f}")

        print()

        resultados[h] = {
            'mae_persist_teste': mae_pers_te,
            'mae_gbm_teste': mae_gb_te,
            'mae_persist_p95': mae_pers_p95,
            'mae_gbm_p95': mae_gb_p95,
            'mae_persist_p99': mae_pers_p99,
            'mae_gbm_p99': mae_gb_p99,
        }

    # ============================================================
    # TABELA FINAL
    # ============================================================
    print()
    print("="*70)
    print("BENCHMARK OFICIAL ARCTURUS — RESUMO")
    print("="*70)
    print(f"{'Horizonte':10s} | {'Baseline':12s} | {'GBM':12s} | {'Ganho':10s}")
    print("-"*70)
    for h in ['1h', '3h', '6h']:
        r = resultados[h]
        ganho = (1 - r['mae_gbm_teste']/r['mae_persist_teste']) * 100
        print(f"{h:10s} | {r['mae_persist_teste']:9.2f} cm | {r['mae_gbm_teste']:9.2f} cm | {ganho:+7.1f}%")

    # Salva
    with open(f"{CACHE}/benchmark_oficial.json", 'w') as f:
        json.dump(resultados, f, indent=2, default=str)
    print(f"\nSalvo: {CACHE}/benchmark_oficial.json")

if __name__ == "__main__":
    main()
