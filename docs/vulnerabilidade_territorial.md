# Banco Espacial de Vulnerabilidade — Tubarão/SC (Etapa 4)

- **Arquivo consolidado:** `data/pontos_alagamento_tubarao.json`
- **Módulo de avaliação:** `src/hidrologia/vulnerabilidade.py`
- **Total de pontos catalogados:** `8` (`4 URBANO` + `4 FLUVIAL`)

| ID | Bairro / Ponto | Classificação | Subtipo Físico | Criticidade | Zona | Gatilho Principal | Coordenadas |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `DEHON` | Dehon | **URBANO** | `drenagem_urbana` | ALTA | Bacia Urbana Central | `drenagem` | `-28.4812, -49.0205` |
| `VILA_MOEMA` | Vila Moema | **URBANO** | `drenagem_urbana` | ALTA | Bacia Urbana Central | `drenagem` | `-28.4775, -49.0085` |
| `CENTRO` | Centro | **URBANO** | `drenagem_urbana` | MEDIA | Bacia Urbana Central | `drenagem_e_comportas` | `-28.4718, -49.0069` |
| `OFICINAS` | Oficinas | **URBANO** | `drenagem_urbana` | ALTA | Bacia Urbana Central | `drenagem` | `-28.4865, -48.9995` |
| `PASSAGEM` | Passagem | **FLUVIAL** | `cheia_fluvial` | ALTA | Margem Esquerda / Calha Principal | `onda_fluvial_e_drenagem` | `-28.4622, -48.996` |
| `SAO_MARTINHO` | São Martinho | **FLUVIAL** | `cheia_fluvial` | ALTA | Margem Esquerda / Baixada | `onda_fluvial` | `-28.4485, -49.0185` |
| `GUARDA` | Guarda (Margem Esquerda/Direita) | **FLUVIAL** | `confluencia_e_montante` | ALTA | Corredor Rural Oeste / Montante ERAB | `onda_fluvial` | `-28.4455, -49.0645` |
| `CONGONHAS` | Congonhas | **FLUVIAL** | `planicie_e_remanso` | ALTA | Planície Sul / Tributário Congonhas | `remanso_e_tributario` | `-28.5145, -49.015` |
