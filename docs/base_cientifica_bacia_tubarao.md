# Base Científica Unificada — Bacia Hidrográfica do Rio Tubarão (RH9 / SC)

> **Classificação Epistemológica:**
> * **`[P]` Publicado / Medido:** Relatórios oficiais (Plano de Bacia SDM/SDS-SC, PLAMCON 2014/2025, ANA/HidroWeb, IPH/UFRGS, dissertações/TCCs revisados).
> * **`[D]` Derivado:** Calculado a partir de dados publicados (ex.: Kirpich via MDE 30 m, balanço de áreas, observações empíricas do ARCTURUS).
> * **`[E]` Estimativa / Relato:** Declarações técnicas, imprensa ou extrapolações de curva-chave sujeitas a incerteza.
>
> **Regra Anti-Alucinação:** Nenhuma constante hidrológica ou limiar operacional entra em produção no ARCTURUS sem rastreabilidade a este documento ou calibração auditada em `data/lag_eventos.jsonl`.

---

## 1. Fisiografia, Morfometria e Estações de Referência

### 1.1 Dimensões da Bacia (`[P]`)
* **Área de drenagem estrita do Rio Tubarão (até a Lagoa de Santo Antônio dos Anjos):** **$4.728,0\text{ km}^2$** (Plano de Bacia / SDM; dispersão de $\approx 1\%$ entre SGB $4.685\text{ km}^2$, PERH/SC $4.735\text{ km}^2$ e IPH $4.740\text{ km}^2$).
* **Área total da Região Hidrográfica 9 (Rio Tubarão + Rio D'Una + Complexo Lagunar):** **$5.959,97\text{ km}^2$** ($\approx 5.960\text{ km}^2$).
* **Extensão do curso principal:** **$\approx 120,0\text{ km}$** a partir da confluência dos rios Bonito e Rocinha (a jusante de Lauro Müller) até a Lagoa de Santo Antônio dos Anjos ($130,72\text{ km}$ medidos em MDE 30 m até a cabeceira mais remota).
* **Relevo e precipitação climatológica (SDS 2017 / TCC UFSC 2019 `[P]`):** Desnível superior a $1.000\text{ m}$ (nascentes na Serra Geral/Serra do Rio do Rastro até o nível do mar); relevo fortemente ondulado ($20\%\text{ a }45\%$ de declividade nas encostas); precipitação média anual de **$1.550\text{ mm/ano}$** (faixa de $1.100\text{ a }1.900\text{ mm}$; médias de Thiessen por sub-bacia entre $1.351\text{ e }1.909\text{ mm}$).

### 1.2 Sub-bacias Hidrográficas (Plano de Bacia / SDM `[P]`)

| Sub-bacia | Área ($\text{km}^2$) | Papel Hidrológico |
| :--- | :---: | :--- |
| **Formadores do Tubarão** (Orleans, Lauro Müller, Pedras Grandes) | $946,6$ | Cabeceira serrana de resposta rápida (*flash floods*) |
| **Rio Braço do Norte** (Anitápolis, Sta. Rosa, Rio Fortuna, Grão-Pará, Braço do Norte, São Ludgero) | $1.756,2$ | Principal afluente da margem esquerda; grande volume acumulado |
| **Rio Capivari** (São Bonifácio, São Martinho, Armazém, Gravatal, Capivari de Baixo) | $1.078,4$ | Afluente no baixo curso sujeito a remanso |
| **Baixo Tubarão** (Tubarão, Pedras Grandes jusante, Laguna) | $998,0$ | Planície costeira retificada (DNOS) com forte influência de maré |
| **Rio D'Una e Complexo Lagunar** (Lagoas Sto. Antônio, Imaruí e Mirim) | $1.180,5$ | Condição de contorno de jusante (amortecimento e remanso) |

*(Nota `[D]`: As 4 sub-bacias fluviais do Rio Tubarão somam $4.779,2\text{ km}^2$, divergência de $\approx 1,1\%$ frente aos $4.728\text{ km}^2$ consolidados no Plano de Bacia).*

### 1.3 Estações Fluviométricas da Rede ANA (TCC UFSC 2019 — Tabelas 4 e 10 `[P]`)

| Código ANA | Estação / Rio | Altitude ($\text{m}$) | Área ANA ($\text{km}^2$) | Área MDE 30m ($\text{km}^2$) | $L$ Canal ($\text{km}$) | $S = \Delta H/L$ ($\text{m/m}$) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`84250000`** | **Orleans** (Alto Tubarão) | $90$ | $606$ | $613,4$ | $39,66$ | $0,01482$ |
| **`84559800`** | **Braço do Norte** (Rio Braço do Norte) | $68$ | $1.515$ | $1.495,3$ | $85,57$ | $0,01009$ |
| **`84560000`** | **São Ludgero** (Rio Braço do Norte) | $40$ | $1.690$ | $1.683,5$ | $92,94$ | $0,00945$ |
| **`84580000`** | **Tubarão / Rio do Pouso** (Série longa ARCTURUS) | $23$ | $2.740$ | $2.731,6$ | $112,31$ | $0,00815$ |
| **`84580500`** | **Tubarão Jusante** (Referência PLAMCON 2025) | $14$ | $2.840$ | $2.835,3$ | $130,72$ | $0,00703$ |

> **Alerta de Reconciliação de Datum:** A estação **`84580500`** (onde o PLAMCON 2025 define alarme em $4,70\text{ m}$ e extravasamento em $\approx 5,50\text{ m}$) situa-se **$\approx 12,5\text{ km}$ em linha reta a jusante** da **`84580000`** (série histórica longa `ana_longa84580000.csv`). Leituras da régua urbana **ERAB (Tubarão Saneamento)** devem ser pareadas simultaneamente com ambas antes de transpor limiares absolutos.

---

## 2. Tempos de Concentração ($t_c$) e Lags de Propagação

* **Lacuna Documental Confirmada (`[P]`):** Não há tabela oficial publicada pela ANA, SGB/CPRM, EPAGRI/CIRAM ou Comitê da Bacia fixando tempos de trânsito determinísticos entre Orleans, Lauro Müller, São Ludgero e Tubarão.
* **Estimativas Teóricas por Kirpich (`[D]` — apenas ordem de grandeza, $t_c = 57 \cdot L^{1,155} \cdot \Delta H^{-0,385}$):**
  * Orleans (`84250000`): **$5,7\text{ h}$**
  * Braço do Norte (`84559800`): **$12,0\text{ h}$**
  * São Ludgero (`84560000`): **$13,1\text{ h}$**
  * Tubarão (`84580000`): **$16,1\text{ h}$**
  * Tubarão Jusante (`84580500`): **$19,1\text{ h}$**
* **Referência Histórica Externa (`[E]`):** Defasagem de pico **Orleans $\rightarrow$ Tubarão $\approx 8\text{ h}$** (evento de ago/2019; celeridade média implícita de $\approx 9\text{ km/h}$ ou $2,5\text{ m/s}$ sobre $72,7\text{ km}$).
* **Evidência Empírica Auditada pelo ARCTURUS (`[D]` — `data/lag_eventos.jsonl`):**
  * **Evento `20261115_2116` (15/11/2026):** Chuva distribuída com dominante 24h em **São Ludgero (`57,6 mm`)**, **Lauro Müller (`41,8 mm`)** e **Orleans (`40,4 mm`)** (média espacial da bacia `38,75 mm`); resposta inicial na ERAB em **`0,25 h`** após o patamar base e pico em **`7,76 h`** (`55,0 cm → 105,0 cm`, $\Delta Z_{\text{total}} = +50,0\text{ cm}$).

---

## 3. Formulações Físicas e Hidráulica Costeira

1. **Quantis de Vazão em Tubarão — Estação `84580000` (IPH/UFRGS — Plano de Macrodrenagem `[P]`):**
   * Ajustados via curva-chave extrapolada pelo método de Stevens e distribuição de Gumbel:
     * **$TR = 10\text{ anos}$:** $1.183,8\text{ m}^3/\text{s}$
     * **$TR = 25\text{ anos}$:** $1.460,3\text{ m}^3/\text{s}$
     * **$TR = 100\text{ anos}$:** $1.869,0\text{ m}^3/\text{s}$
   * Quantis em Armazém (Rio Capivari): $TR_{10} = 330,9\text{ m}^3/\text{s}$, $TR_{25} = 413,9\text{ m}^3/\text{s}$, $TR_{100} = 536,5\text{ m}^3/\text{s}$.
   * Regionalização da $Q_{98}$ por área na bacia: $R^2 = 0,745$.
2. **Acoplamento Chuva–Rio–Maré e Remanso Lagunar (IPH-ECO / Vanelli UFRGS / Melo UNISUL `[P]`):**
   * Série observada de maré em Laguna (2014–2016): **$-0,49\text{ m}$ a $+0,95\text{ m}$** (amortecida pela Lagoa do Imaruí para **$-0,40\text{ m}$ a $+0,67\text{ m}$**).
   * A diferença entre maré alta e maré baixa altera a mancha de inundação no baixo curso em **$\approx 60\text{ km}^2$** em todos os tempos de retorno (similaridade espacial $\le 50\%$). O RIMA da dragagem confirma avanço da cunha de maré pelo fundo do canal, exigindo equações dinâmicas completas de **Saint-Venant 1D/2D** (HEC-RAS / MGB-IPH hidrodinâmico) no trecho final.
3. **Equações Hidrológicas de Referência Geral (sem parâmetros oficiais publicados para o Tubarão `[P]`):**
   * **API:** $\text{API}_t = k \cdot \text{API}_{t-1} + P_t$
   * **SCS-CN:** $Q = \frac{(P - I_a)^2}{(P - I_a) + S}, \quad S = \frac{25400}{\text{CN}} - 254 \text{ (mm)}$
   * **Propagação Muskingum / Muskingum-Cunge:** $O_2 = C_0 I_2 + C_1 I_1 + C_2 O_1$, com $K = \frac{\Delta x}{c}$ e $X = \frac{1}{2}\left(1 - \frac{Q}{B \cdot S_0 \cdot c \cdot \Delta x}\right)$ (válido apenas a montante da zona de remanso lagunar; $K \approx 8\text{ h}$ derivado para Orleans–Tubarão `[D]`).

---

## 4. Limiares Operacionais e Eventos Históricos

### 4.1 Limiares Oficiais PLAMCON (Estação ANA `84580500` `[P]`)

| Indicador / Gatilho | Valor Oficial | Fonte |
| :--- | :---: | :--- |
| **Início de Alarme (Rio)** | **$4,70\text{ m}$** (medido na `84580500`) | PLAMCON 2025 `[P]` |
| **Extravasamento Bairros Baixos** (Bom Pastor, São João, Madre) | **$\approx 5,50\text{ m}$** (dependente do assoreamento da calha) | PLAMCON 2025 `[P]` |
| **Desativação do Plano** | **$\le 3,50\text{ m}$** | PLAMCON 2014 `[P]` |
| **Gatilho de Chuva (Urbano / Encostas)** | **$\approx 30\text{ mm/h}$** (vias) / **$\approx 100\text{ mm/dia}$** (encostas) | PLAMCON 2025 `[P]` (vs. $50\text{ mm/h}$ e $300\text{ mm}$ no PLAMCON 2014) |

### 4.2 Marcos Históricos Documentados (`[P]` vs. `[E]`)
* **Março de 1974 (22 a 25/03/1974):** Decreto de Calamidade `267/1974` com **199 óbitos** `[P]`. Marcas de cheia citadas entre **$9,5\text{ m}$ (s.n.m.) e $10,22\text{ m}$** `[E]` (ausentes da série `84580000`, cujo máximo histórico registrado é $7,46\text{ m}$ — requer auditoria de lacuna/datum). Motivou a retificação e construção de diques pelo DNOS (concluída em 1978/1982).
* **Maio de 2022 (03 a 05/05/2022):** Decreto municipal de 04/05; **$1.936$ desalojados/desabrigados e $25.000$ atingidos** `[P]`. Rio permaneceu acima de $7,0\text{ m}$ entre 23h de 04/05 e 07h de 05/05 ($6,40\text{ m}$ na régua do Exército; taxa de subida de $\approx 20\text{ cm/h}$ em 03/05 e recessão de $\approx 5\text{ cm/h}$ em 05/05) `[E]`. Evidenciou o papel crítico do fechamento de comportas e drenagem interna urbana.
* **Dezembro/2022, Outubro/2025 e Setembro/2026 (`[E]`):** Picos de $4,93\text{ m}$ (01/12/2022, sem transbordo), $150\text{ mm/24h}$ (out/2025) e $107\text{ mm}$ na Guarda (21/09/2026, comportas fechadas, aporte principal de Lauro Müller e Orleans).

---

## 5. Implicações Diretas para a Engenharia do ARCTURUS

1. **Correlação Cruzada Horária (Substituindo Lags Fixos):** Como não há $t_c$ nem $K$ oficiais publicados para a bacia, a calibração do **v11c** deve usar exclusivamente séries horárias observadas (Defesa Civil SC / AGR / ERAB) acumuladas em `data/lag_eventos.jsonl` e `data/proveniencia_observacoes.jsonl`.
2. **Acoplamento de Jusante (Vento / Maré):** Como a variação de maré muda a área inundável em $\approx 60\text{ km}^2$, incorporar o nível astronômico/meteorológico de Laguna como feature de contorno de jusante é prioritário para eventos acima da cota de atenção.
3. **Auditoria de Série Longa (`ana_longa84580000.csv`):** Verificar a lacuna de março/1974 (máximo $746\text{ cm}$ no CSV vs. relatos $> 9,5\text{ m}$) e reconciliar simultaneamente as réguas `84580000`, `84580500` e ERAB.
