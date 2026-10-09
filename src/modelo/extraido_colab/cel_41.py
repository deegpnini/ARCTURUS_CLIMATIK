import pickle, os

modelos = [
    '/content/drive/MyDrive/ARCTURUS_CLIMATIK/modelos/modelo_TUBARAO.pkl',
    '/content/drive/MyDrive/ARCTURUS_CLIMATIK/modelos/modelo_RIO_FORTUNA.pkl',
]

for m in modelos:
    if os.path.exists(m):
        print(f"\n=== {os.path.basename(m)} ===")
        with open(m, 'rb') as f:
            obj = pickle.load(f)
        print("Tipo:", type(obj))
        if hasattr(obj, 'feature_names_in_'):
            print("Features:", list(obj.feature_names_in_))
        elif hasattr(obj, 'n_features_in_'):
            print("N features:", obj.n_features_in_)
        if hasattr(obj, 'classes_'):
            print("Classes:", obj.classes_)
        print("Atributos:", [a for a in dir(obj) if not a.startswith('_')][:15])