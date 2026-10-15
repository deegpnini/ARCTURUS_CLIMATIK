# ARCTURUS CLIMATIK

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
