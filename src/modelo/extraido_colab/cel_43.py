Uimport pickle
import numpy as np

# Carregar modelo
with open('/content/drive/MyDrive/ARCTURUS_CLIMATIK/modelos/modelo_TUBARAO.pkl', 'rb') as f:
    modelo = pickle.load(f)

print("=== MODELO TUBARAO ===")
print("Features:", list(modelo.feature_names_in_))
print("N features:", modelo.n_features_in_)
print("N estimadores:", modelo.n_estimators)
print("Profundidade max:", modelo.max_depth)
print()
print("=== IMPORTANCE DAS FEATURES ===")
for feat, imp in sorted(zip(modelo.feature_names_in_, modelo.feature_importances_), key=lambda x: -x[1]):
    print(f"  {feat:15s} {imp:.4f}")
print()
print("=== EXEMPLO DE PREDICAO ===")
# Testar com features genericas
X_test = np.array([[12, 15, 6, 0, 0.5, 0.87, 0.5, 0.87]])  # hora=12, dia=15, mes=6, seg=0...
try:
    pred = modelo.predict(X_test)
    print(f"Predicao para input ficticio: {pred}")
    print("(isso mostra a escala do que ele preve)")
except Exception as e:
    print("Erro:", e)