# ARCTURUS CLIMATIK

## Evolução: ARCTURUS v2 (Integração de Montante)
**Data:** 23/10/2026

Após a descontinuação da estação âncora ANA 84580000 (encerramento do contrato ANA/IGAM), o modelo foi re-treinado utilizando dados de 3 estações vivas a montante (CGH São Maurício, PCH Rio Fortuna e CGH Invernadinha). 

**Descoberta Científica (Tempo de Viagem):**
Através de um teste A/B focado em momentos de subida (delta > 5cm), descobrimos que o tempo de viagem da água a montante para a bacia do Tubarão é de **2 horas**. Modelos com lag de 6h ou 12h pioravam a previsão; o lag de 2h reduziu o erro.

**Resultados do v2 (Backtest 2025-2026):**
- **Features:** 30 (adicionadas as variações de cota de montante com lag de 2h).
- **RMSE Geral:** 3.77 cm (ante 6.90 cm do modelo antigo sem montante).
- **RMSE em Subidas:** 11.53 cm (foco no que realmente importa para alertas).
- **R²:** 0.98 (o modelo explica 98% da variação local).

O arquivo do modelo está salvo em `modelos/modelo_delta_1h_com_montante.txt` com o respectivo manifesto de reprodutibilidade.

---

**Projeto experimental de pesquisa hidrológica para Santa Catarina.**

O ARCTURUS CLIMATIK investiga se dados históricos, telemetria dos rios e
informações meteorológicas podem ajudar a antecipar a elevação do nível
da água.

É um projeto pessoal de pesquisa. Não é um sistema oficial de alerta, não
substitui a Defesa Civil, o CEMADEN ou os órgãos responsáveis e ainda não
demonstrou desempenho prospectivo suficiente para orientar decisões de
emergência.

## Objetivo

Estimar a variação do nível de uma estação fluviométrica com 1, 3 e 6 horas
de antecedência e reconstruir a cota prevista:

`cota_prevista = cota_atual + delta_previsto`

A meta é demonstrar ganho sobre referências simples, como persistência e
tendência, e verificar se esse ganho oferece antecedência útil para
identificar elevações perigosas do rio.

Prever o nível do rio não é o mesmo que prever inundação urbana. Para estudar
impactos, também são necessários registros dos locais atingidos, chuva,
condições do terreno e informações sobre os danos.

## Estado atual

- Estação de referência: ANA 84580000, Rio do Pouso, bacia do Rio Tubarão.
- Algoritmo de referência: LightGBM, com alvo delta.
- Modelo de produção documentado: 26 features, sem a variável `vazao`.
- Avaliação histórica: leave-one-event-out (LOEO), com 27 eventos.
- Estado operacional: não considerar o sistema pronto para previsão pública
  em tempo real. A atual disponibilidade e a qualidade da telemetria precisam
  ser verificadas antes de qualquer operação ao vivo.
- O projeto não emite alertas oficiais.

## Registros históricos em investigação

A extração local do arquivo
`data/_backup/cache/historico_84580000_MASTER.csv` contém os valores abaixo:

| Data registrada | Cota no arquivo local |
|---|---:|
| 24/03/1974 | 727 cm |
| 01/10/2001 | 730 cm |
| 05/05/2022 | 700 cm |
| 01/12/2022 | 746 cm |

Esses valores documentam o conteúdo da extração local. Não devem ser tratados
como classificação oficial dos maiores desastres ou como prova isolada de
inundação urbana. A unidade, o significado do campo, a consistência e a
resolução temporal precisam ser confirmados junto à fonte original.

A maior tragédia urbana e a maior cota de uma estação são medidas diferentes.
Uma leitura diária também não revela necessariamente o pico intradiário.

### Caso de setembro de 2026

A análise local identificou uma leitura de 446 cm na estação 84580000 após
uma lacuna de telemetria. O nível máximo ocorrido durante o intervalo sem
dados não foi observado e permanece desconhecido.

Portanto, 446 cm não deve ser apresentado como o pico máximo real da cheia,
nem como prova isolada de inundação urbana. O caso permanece como uma
investigação de qualidade da série e do comportamento do modelo diante de
dados incompletos.

## Resultados históricos e validação

O modelo LightGBM prevê `delta`, a mudança estimada da cota. Os resultados
abaixo são retrospectivos e não garantem desempenho em novas tempestades.

Na versão sem `vazao`, quatro execuções (padrão e sementes 11, 22 e 33)
produziram as seguintes faixas:

| Horizonte | MAE médio do delta por evento | Vitórias sobre persistência | Vitórias sobre modelo absoluto |
|---|---:|---:|---:|
| 1h | 2,09–2,10 cm | 26–27 de 27 | 18–20 de 27 |
| 3h | 6,15–6,20 cm | 26 de 27 | 17–22 de 27 |
| 6h | 10,07–10,35 cm | 23–24 de 27 | 16–20 de 27 |

As faixas mostram variação entre execuções. As contagens de vitórias usam
margens de empate definidas no relatório técnico. O MAE apresentado é a
média dos MAEs por evento, não uma métrica ponderada pelo número de leituras.

### Análise da remoção de `vazao`

A diferença é calculada como MAE do modelo sem `vazao` menos MAE do modelo
com `vazao`. Valor positivo significa erro maior após remover a variável.

| Horizonte | Diferença média | IC 95% bootstrap |
|---|---:|---:|
| 1h | -0,001 cm | -0,021 a +0,016 cm |
| 3h | -0,060 cm | -0,131 a +0,004 cm |
| 6h | +0,205 cm | +0,035 a +0,410 cm |

O resultado de 6h sugere um pequeno custo médio após remover `vazao`.
A versão com 26 features favorece a simplicidade e reduz a dependência de
uma variável considerada redundante na auditoria. Isso não prova que as
duas versões sejam equivalentes em todas as situações.

Os intervalos são estimativas exploratórias baseadas na avaliação por
eventos. Não eliminam a incerteza causada por novas cheias, diferenças entre
eventos ou escolhas de treinamento.

## Limitações

- Uma estação de referência e 27 eventos na avaliação documentada.
- Poucos eventos severos para concluir que o modelo antecipa cheias extremas.
- A avaliação retrospectiva não comprova desempenho em operação real.
- A série histórica diária não substitui dados sub-horários para avaliar
  previsões de 1h, 3h e 6h.
- Valores ausentes podem permitir que o modelo gere uma saída sem informação
  suficiente. A operação deve identificar essas situações e bloquear
  previsões que não cumpram critérios de qualidade previamente definidos.
- Estações distintas podem ter referências de nível e características
  próprias. O modelo não deve ser transferido sem calibração e validação.
- O projeto ainda não demonstrou capacidade validada de prever inundação
  em uma rua ou bairro específico.

## Dados e reprodutibilidade

As pastas locais `data/` e `resultados/` não fazem parte deste commit público.
Dados brutos, respostas de API e configurações locais devem ser preservados
e auditados separadamente. Credenciais nunca devem ser publicadas.

Resultados públicos devem indicar os arquivos de referência, versões,
configurações, hashes e protocolo usados. Métricas de execuções distintas
não devem ser combinadas sem explicitar a regra de comparação.

## Fontes de dados em investigação

- ANA HidroWebService: dados fluviométricos, cotas e chuva.
- INMET: observações meteorológicas.
- CEMADEN: monitoramento de chuva e referências de eventos.
- EPAGRI/CIRAM e órgãos de defesa civil: estações, boletins e registros de
  impactos, sujeitos a verificação.
- Registros oficiais de desastres: datas dos eventos, locais atingidos e
  descrição dos impactos.

Disponibilidade, qualidade, horários e significado de cada campo precisam
ser verificados antes da integração ao conjunto de treinamento.

## Próximas etapas

1. Auditar os registros históricos e os códigos de consistência da ANA.
2. Montar um catálogo de eventos com níveis, chuva e impactos documentados.
3. Testar a antecipação de ultrapassagens de níveis de referência em eventos
   que não participaram do treinamento.
4. Medir eventos detectados, falsos alarmes e antecedência útil.
5. Expandir para outras bacias somente após auditar e validar cada estação.

## Princípios de trabalho

- Raw Evidence First: a evidência observada prevalece sobre a memória.
- Correlação não implica causalidade.
- Backtest não substitui avaliação prospectiva.
- Dados de referência não são sobrescritos.
- Dados ausentes não são preenchidos sem regra explícita.
- Limitações devem ser declaradas antes dos resultados.

## Licença

Consulte o arquivo `LICENSE`.

---

## Testes que não funcionaram (Honestidade Radical)

Esta seção documenta os testes que foram feitos, mas que **não agregaram valor** ao modelo. Ela existe porque a ciência não é feita só de acertos. Cada teste descartado é uma prova de rigor.

### GloFAS (Vazão Simulada do Copernicus)
- **O que foi testado:** Adicionar a vazão simulada do GloFAS (Open-Meteo Flood API) como feature do modelo.
- **Resultado:** Não agregou valor. No 3h, o RMSE piorou de 8.49 para 8.55. No 6h, empatou (14.43 vs 14.42), mas a performance na subida piorou (50.72 vs 51.50).
- **Conclusão:** A cota local (e seus lags) já capturam a informação que o GloFAS tentaria adicionar. O GloFAS é uma simulação global que não tem a resolução temporal nem a precisão da cota local.

### LSTM e GRU (Redes Neurais)
- **O que foi testado:** Treinar LSTM e GRU com janelas de 48 passos (12h) para prever o delta de 6h.
- **Resultado:** O LightGBM venceu com folga. RMSE de 14.60 cm (LightGBM) vs 15.92 cm (GRU) e 16.92 cm (LSTM). O tempo de treino foi 1.385x maior para as redes.
- **Conclusão:** Para dados tabulares com features bem construídas, o gradient boosting (LightGBM/XGBoost) é mais eficiente e preciso que as redes neurais. A literatura confirma isso para datasets com menos de 10.000 amostras.

### Invernadinha (Estação de Montante)
- **O que foi testado:** Usar a CGH Invernadinha (70110000) como feature de montante.
- **Resultado:** A estação é da Bacia do Uruguai (prefixo 7x), não da Bacia do Tubarão (prefixo 84). A correlação com o Rio do Pouso era espúria.
- **Conclusão:** Removida do modelo. A chuva da bacia (Open-Meteo) carrega a informação que a Invernadinha deveria fornecer.

### CEMADEN (Pluviômetros Densos)
- **O que foi testado:** Coletar dados de pluviômetros do CEMADEN via API.
- **Resultado:** O IP da API (`150.163.255.240`) está fora do ar. O fallback para Open-Meteo foi implementado.
- **Conclusão:** O CEMADEN é uma fonte instável. O HydroBR (pacote R) é a rota recomendada para o futuro.

---

## Campeonato de Modelos (1 passo à frente = 15 min)

| Modelo | RMSE (cm) | Tempo (s) |
| :--- | :--- | :--- |
| **LightGBM** | **0.09** | 0.3 |
| XGBoost | 0.38 | 0.2 |
| LSTM | 2.00 | 179.5 |
| GRU | 2.18 | 279.7 |

## Campeonato de Modelos (6h à frente)

| Modelo | RMSE (cm) | Tempo (s) |
| :--- | :--- | :--- |
| **LightGBM** | **14.60** | 0.2 |
| XGBoost | 15.26 | 0.2 |
| GRU | 15.92 | 277.1 |
| LSTM | 16.92 | 148.7 |

**Veredito:** O LightGBM é o modelo de produção. As redes neurais (LSTM/GRU) foram lentas e imprecisas para este dataset.

---



Esta seção documenta os testes que foram feitos, mas que **não agregaram valor** ao modelo. Ela existe porque a ciência não é feita só de acertos. Cada teste descartado é uma prova de rigor.

### GloFAS (Vazão Simulada do Copernicus)
- **O que foi testado:** Adicionar a vazão simulada do GloFAS (Open-Meteo Flood API) como feature do modelo.
- **Resultado:** Não agregou valor. No 3h, o RMSE piorou de 8.49 para 8.55. No 6h, empatou (14.43 vs 14.42), mas a performance na subida piorou (50.72 vs 51.50).
- **Conclusão:** A cota local (e seus lags) já capturam a informação que o GloFAS tentaria adicionar. O GloFAS é uma simulação global que não tem a resolução temporal nem a precisão da cota local.

### LSTM e GRU (Redes Neurais)
- **O que foi testado:** Treinar LSTM e GRU com janelas de 48 passos (12h) para prever o delta de 6h.
- **Resultado:** O LightGBM venceu com folga. RMSE de 14.60 cm (LightGBM) vs 15.92 cm (GRU) e 16.92 cm (LSTM). O tempo de treino foi 1.385x maior para as redes.
- **Conclusão:** Para dados tabulares com features bem construídas, o gradient boosting (LightGBM/XGBoost) é mais eficiente e preciso que as redes neurais. A literatura confirma isso para datasets com menos de 10.000 amostras.

### Invernadinha (Estação de Montante)
- **O que foi testado:** Usar a CGH Invernadinha (70110000) como feature de montante.
- **Resultado:** A estação é da Bacia do Uruguai (prefixo 7x), não da Bacia do Tubarão (prefixo 84). A correlação com o Rio do Pouso era espúria.
- **Conclusão:** Removida do modelo. A chuva da bacia (Open-Meteo) carrega a informação que a Invernadinha deveria fornecer.

### CEMADEN (Pluviômetros Densos)
- **O que foi testado:** Coletar dados de pluviômetros do CEMADEN via API.
- **Resultado:** O IP da API (`150.163.255.240`) está fora do ar. O fallback para Open-Meteo foi implementado.
- **Conclusão:** O CEMADEN é uma fonte instável. O HydroBR (pacote R) é a rota recomendada para o futuro.

---

## Campeonato de Modelos (1 passo à frente = 15 min)

| Modelo | RMSE (cm) | Tempo (s) |
| :--- | :--- | :--- |
| **LightGBM** | **0.09** | 0.3 |
| XGBoost | 0.38 | 0.2 |
| LSTM | 2.00 | 179.5 |
| GRU | 2.18 | 279.7 |

## Campeonato de Modelos (6h à frente)

| Modelo | RMSE (cm) | Tempo (s) |
| :--- | :--- | :--- |
| **LightGBM** | **14.60** | 0.2 |
| XGBoost | 15.26 | 0.2 |
| GRU | 15.92 | 277.1 |
| LSTM | 16.92 | 148.7 |

**Veredito:** O LightGBM é o modelo de produção. As redes neurais (LSTM/GRU) foram lentas e imprecisas para este dataset.

---

## Calibração ERAB x 84580000 (Bloqueio Atual)

O modelo v8 foi treinado na régua do Rio do Pouso (84580000). O painel de produção usa a cota da ERAB (Tubarão Saneamento), que é outro ponto do rio, com outra escala.

**O problema:** Não existe período de sobreposição entre as duas séries. O cache da ANA termina em 22/09/2026. O JSON da ERAB tem um único ponto (23/10/2026, 67 cm).

**Consequência:** O modelo não pode ser operado em tempo real com a cota da ERAB até que a Tubarão Saneamento forneça o histórico da ERAB (pelo menos 12 meses, incluindo o período de 18 a 26/09/2026).

**Ação:** Pedido formal enviado à Tubarão Saneamento. Enquanto isso, o painel deve exibir o rótulo **"EXPERIMENTAL — ERAB NÃO CALIBRADA"** e bloquear a previsão se o dado tiver mais de 45 minutos.

---

---

## Limitações Conhecidas

### Julho/2024 (Evento Perdido)
O evento de julho/2024 (cota máxima diária de 335 cm) está presente na série longa da ANA (1939-2026), mas **não está no cache de telemetria de 15 min**. A API da ANA não retornou os dados desse período, e o `build_dataset.py` não pôde incluí-lo no dataset de treino.

**Consequência:** O modelo de 15 min nunca viu o maior evento do período 2023-2026. Ele foi treinado em um período calmo (cota máxima de 253 cm) e testado em um período com eventos extremos (cota máxima de 312 cm), mas sem o evento de 335 cm de julho/2024.

**Isso é uma limitação da fonte de dados, não do modelo.**

### Resolução Temporal da Série Longa
A série longa da ANA (1939-2026) é **diária**, não horária. Ela é útil para contar quantos eventos extremos existem (182 eventos com cota > 300 cm), mas não para treinar o modelo de previsão de 15 min.

### Calibração ERAB (Bloqueio Atual)
O modelo v8 foi treinado na régua do Rio do Pouso (84580000). O painel de produção usa a cota da ERAB (Tubarão Saneamento). Não existe período de sobreposição entre as duas séries.

**Ação:** Pedido formal enviado à Tubarão Saneamento. Enquanto isso, o painel deve exibir o rótulo **"EXPERIMENTAL — ERAB NÃO CALIBRADA"** e bloquear a previsão se o dado tiver mais de 45 minutos.

---

---

## Validação de Dados (24/10/2026)

### Queda da Cota (67 cm → 26 cm)
No dia 23/10/2026, a cota da ERAB (Tubarão Saneamento) estava em 67 cm. No dia 24/10/2026, às 12:15, caiu para 26 cm. **Isso não é erro do Playwright.** O rio está em recessão (período de seca), e a cota de 26 cm é consistente com o histórico da bacia (cota mínima de 24 cm em dias secos).

### Interpretação do Modelo (0.35% de Probabilidade)
Com a cota em 26 cm e a chuva prevista de 56.9 mm em 48h, o classificador de cheia calculou uma probabilidade de **0.35%** de o rio atingir 300 cm em 2 dias. Isso é consistente com a física da bacia: o rio está tão baixo que, mesmo com chuva significativa, a água não sobe 274 cm em 48h.

### Fontes de Dados e Confiabilidade
- **Cota:** Tubarão Saneamento (ERAB) via Playwright. Dado validado (26 cm em 24/10 às 12:15).
- **Chuva Prevista:** Open-Meteo Forecast. 56.9 mm em 48h.
- **Classificador de Cheia:** Treinado com 87 anos de dados (1939-2026) e 182 eventos extremos. AUC de 0.869.

### Limitações Conhecidas
- **Calibração ERAB x 84580000:** O modelo foi treinado na régua do Rio do Pouso (84580000), mas opera com a cota da ERAB. A calibração está pendente (pedido enviado à Tubarão Saneamento).
- **Evento de Julho/2024:** O evento de 335 cm (média diária) está na série longa, mas não no cache de 15 min. O modelo não pôde aprender com ele.
- **Eventos Extremos:** O modelo tem maior incerteza em subidas muito rápidas (RMSE de ~12 cm na subida).

---

## Desenvolvimento Assistido por IA (XERJ)

O ARCTURUS utiliza o **XERJ** (v1.0.0) para indexação local do código-fonte.

**Benefícios:**
- Busca semântica do código (sem ler arquivos inteiros).
- Economia de tokens (o Copilot recebe o trecho exato, não o arquivo todo).
- Localização rápida de funções (ex: "onde o Vz é calculado?").
- Integração com GitHub Copilot via MCP (Model Context Protocol).
- Navegação contextual do projeto.

**Índices disponíveis:**
- `src/` (109 arquivos, 1.462 documentos) → prefixo `ax`.
- `tools/` (59 arquivos, 455 documentos) → prefixo `tools`.

**Exemplos de perguntas:**
- "Onde é calculado o Vz?"
- "Onde o Az é escrito no JSON?"
- "Onde o regime é atualizado?"
- "Onde o SQLite recebe novas leituras?"

**Configuração:**
- O arquivo `.vscode/mcp.json` contém a configuração do servidor XERJ.
- O XERJ roda na porta `9200` (MCP stdio server).

