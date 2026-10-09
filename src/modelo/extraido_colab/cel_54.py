# ============================================================
# CORRECAO: marcar IC degenerado (quando bootstrap colapsa)
# ============================================================
def ic95_valido(arr):
    """
    Retorna (lo, hi, n_unicos).
    Se n_unicos == 1: bootstrap colapsou, IC invalido.
    """
    arr = np.array(arr)
    n_unicos = len(np.unique(arr))
    if n_unicos < 5:
        return None, None, n_unicos
    lo = float(np.percentile(arr, 2.5))
    hi = float(np.percentile(arr, 97.5))
    return lo, hi, n_unicos


def interpretar_ic(arr, nome):
    lo, hi, n_unicos = ic95_valido(arr)
    if lo is None:
        print(f"  {nome}: IC INVALIDO ({n_unicos} valores unicos)")
        print(f"    -> bootstrap degenerou (poucos eventos no subset)")
        print(f"    -> resultado inconclusivo, nao usar")
        return None
    media = float(np.mean(arr))
    pct_pos = float((np.array(arr) > 0).mean() * 100)
    cruza_zero = lo <= 0 <= hi
    print(f"  {nome}: media={media:+.2f} IC95%=[{lo:+.2f}, {hi:+.2f}] "
          f"n_unicos={n_unicos} %pos={pct_pos:.1f}%")
    if cruza_zero:
        print(f"    -> INCONCLUSIVO: IC cruza zero")
    elif media > 0:
        print(f"    -> GANHO ROBUSTO")
    else:
        print(f"    -> PERDA ROBUSTA")
    return (media, lo, hi, n_unicos)