# ARCTURUS CLIMATIK

Sistema de previsao de nivel de rio para Santa Catarina.

## O problema

Em setembro de 2026, SC entrou em calamidade publica.
57 municipios com ocorrencias. Rio Tubarao atingiu o maior valor da serie.

## A solucao

Modelo LightGBM com target delta (variacao, nao cota absoluta).
Previsao: cota_atual + delta_previsto.
Horizontes: 1h, 3h, 6h.

## Validacao

Leave-one-event-out em 27 eventos historicos.
Ganho sobre persistencia: 26/27 (1h), 26/27 (3h), 24/27 (6h).

## Limitacoes

- Uma bacia apenas (Tubarao).
- Sem previsao ao vivo (estacao caida).
- Nao e alerta oficial.
- 26 features (vazao removida por redundancia).

## Contato

Helyton Renato Goncalves Ronchi
deegp.nini@gmail.com

---

## Estrutura do repositorio

```
ARCTURUS_CLIMATIK/
|-- README.md
|-- requirements.txt
|-- LICENSE
|-- modelos/                # Modelos de producao + manifesto
|-- src/
|   |-- modelo/             # Porte das celulas do Colab
|   `-- relatorios/         # insight.py (gerador de relatorios)
|-- tools/                  # Scripts de auditoria, treino, coleta
|-- docs/                   # Documentacao tecnica
`-- data/                   # (ignorado) Dados baixados da ANA
```

---

## Como rodar

```bash
# 1. Clonar
git clone https://github.com/deegpnini/ARCTURUS_CLIMATIK.git
cd ARCTURUS_CLIMATIK

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Criar .env com credenciais da ANA
echo "ANA_CPF=SEU_CPF" > .env
echo "ANA_SENHA=SUA_SENHA" >> .env

# 4. Rodar insight (modo retrospectivo)
python -m src.relatorios.insight --modo retrospectivo --data "2026-09-22 00:00"
```

---

## Fontes de dados

- **ANA HidroWebService** — telemetria de 15 min (cota, chuva, vazao)
- **INMET** — meteorologia
- **EPAGRI/CIRAM** — planejado (estacoes classicas de SC)
- **USGS, Sentinel-1, Open-Meteo, NASA POWER** — projetos paralelos

---

## Limitacoes declaradas

**Trabalho em andamento.** O que esta pronto e o que nao esta:

- **Uma bacia apenas.** Modelo treinado e validado para a bacia do Rio Tubarao.
- **Sem previsao ao vivo.** A estacao 84580000 esta caida desde 22/09/2026.
- **Sem alerta oficial.** E analise tecnica. Complementa a Defesa Civil, nao substitui.
- **Sem peer review.** Projeto pessoal, nao publicado.
- **26 features, nao 27.** A feature vazao foi removida (derivada da cota, Spearman 1.0).
- **Features de montante nao implementadas.** Candidatas testadas, correlacao de delta fraca (~0.11).
- **27 eventos historicos.** Amostra pequena. IC pode ser otimista.
- **Cobertura esparsa entre eventos.** 55% no treino, 96-100% dentro dos eventos.

---

## Documentacao tecnica

- [docs/ARCTURUS_FORECAST_v1.0.md](docs/ARCTURUS_FORECAST_v1.0.md) — arquitetura do modelo
- [docs/regras_completude_v1.0.md](docs/regras_completude_v1.0.md) — regras de completude
- [docs/STATUS_20260922.md](docs/STATUS_20260922.md) — status do dia 22/09/2026

---

## Roadmap

- [x] Corrigir README (concluido em 09/10/2026)
- [ ] Implementar insight_parte3.py (geracao de relatorios JSON + Markdown)
- [ ] Buscar estacao alternativa para a ancora (ou aguardar retorno)
- [ ] Testar features de grade de chuva (Open-Meteo, CHIRPS)
- [ ] Expandir para Chapeco, Uruguai, Itajai, Ararangua
- [ ] Ativar bot do Telegram em producao
- [ ] Publicar preprint cientifico

---

## Metodo

Este projeto aplica 10 principios de trabalho:

1. **Raw Evidence First** — o disco manda, memoria nao
2. **Mover nunca deletar**
3. **Pre-voo antes de mover**
4. **Confirmacao explicita antes de executar**
5. **Print linha a linha**
6. **LEIA-ME por pasta**
7. **Rollback escrito antes**
8. **Template antes de executavel**
9. **Descoberta dinamica**
10. **Nao classificar sem avaliar valor**

E 3 principios cientificos:

- **Correlacao != causalidade**
- **Backtest decide, nao correlacao**
- **Teste e intocado ate a decisao final**

---

## Licenca

MIT. Veja [LICENSE](LICENSE).

---

## Contato

Helyton Renato Goncalves Ronchi
deegp.nini@gmail.com

## Limitacoes

- Uma bacia apenas (Tubarao).
- Sem previsao ao vivo (estacao caida desde 22/09/2026).
- Nao e alerta oficial. Complementa Defesa Civil e CEMADEN.
- 26 features (vazao removida por redundancia, Spearman 1.0).
- 27 eventos historicos. Amostra pequena.

## Como rodar

git clone https://github.com/deegpnini/ARCTURUS_CLIMATIK.git
pip install -r requirements.txt
echo "ANA_CPF=SEU_CPF" > .env
echo "ANA_SENHA=SUA_SENHA" >> .env
python -m src.relatorios.insight --modo retrospectivo --data "2026-09-22 00:00"

## Fontes

- ANA HidroWebService (telemetria 15 min)
- INMET (meteorologia)
- EPAGRI/CIRAM (planejado)

## Contato

Helyton Renato Goncalves Ronchi
deegp.nini@gmail.com

## Limitacoes

- Uma bacia apenas (Tubarao).
- Sem previsao ao vivo (estacao caida desde 22/09/2026).
- Nao e alerta oficial. Complementa Defesa Civil e CEMADEN.
- 26 features (vazao removida por redundancia, Spearman 1.0).
- 27 eventos historicos. Amostra pequena.

## Como rodar

git clone https://github.com/deegpnini/ARCTURUS_CLIMATIK.git
pip install -r requirements.txt
echo "ANA_CPF=SEU_CPF" > .env
echo "ANA_SENHA=SUA_SENHA" >> .env
python -m src.relatorios.insight --modo retrospectivo --data "2026-09-22 00:00"

## Fontes

- ANA HidroWebService (telemetria 15 min)
- INMET (meteorologia)
- EPAGRI/CIRAM (planejado)

## Contato

Helyton Renato Goncalves Ronchi
deegp.nini@gmail.com

## Limitacoes

- Uma bacia apenas (Tubarao).
- Sem previsao ao vivo (estacao caida desde 22/09/2026).
- Nao e alerta oficial. Complementa Defesa Civil e CEMADEN.
- 26 features (vazao removida por redundancia, Spearman 1.0).
- 27 eventos historicos. Amostra pequena.

## Como rodar

git clone https://github.com/deegpnini/ARCTURUS_CLIMATIK.git
pip install -r requirements.txt
echo "ANA_CPF=SEU_CPF" > .env
echo "ANA_SENHA=SUA_SENHA" >> .env
python -m src.relatorios.insight --modo retrospectivo --data "2026-09-22 00:00"

## Fontes

- ANA HidroWebService (telemetria 15 min)
- INMET (meteorologia)
- EPAGRI/CIRAM (planejado)

## Contato

Helyton Renato Goncalves Ronchi
deegp.nini@gmail.com
