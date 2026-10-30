# Relatório de Impacto — A.C. Atlas

## Evento de maio de 2019

| Indicador | Resultado |
|---|---:|
| Edificações afetadas | **1.290** |
| Escolas afetadas em Tubarão | **0** |
| UBS afetadas em Tubarão | **0** |
| População estimada afetada | **N/D — estimativa não publicada** |

### Edificações

O total de **1.290 edificações afetadas** (0,36% de 360.920 edificações analisadas) vem de `resultados/dano_inundacao_tubarao_2019_edificacoes.json`. A análise original cruza edifícios do Google Open Buildings v3 com pixels positivos da máscara binária `mapa_inundacao_tubarao_2019_binario.tif`.

### Escolas e unidades de saúde

Foram consultados dados do OpenStreetMap pela Overpass API, limitados ao município de Tubarão (código IBGE 4218707; relação administrativa OSM 296517). A consulta encontrou 31 elementos `amenity=school`, 2 `amenity=college` e 13 candidatos a unidades de saúde (`amenity=clinic` ou `healthcare=clinic/centre`).

O cruzamento espacial com a máscara resultou em **0 escolas** e **0 UBS** afetadas dentro do limite municipal. Para pontos foi verificado o pixel correspondente; polígonos foram considerados intersectantes quando tocavam ao menos um pixel positivo (`all_touched`). Os elementos de saúde são candidatos OSM — as tags não distinguem necessariamente uma UBS de outras clínicas.

A consulta à bbox regional original também encontrou uma escola intersectante, a Escola de Educação Básica de São Ludgero. Ela fica fora do limite municipal de Tubarão e, por isso, não está incluída nos totais municipais acima.

O estado dos dados OSM usado foi `2026-10-30T17:35:01Z`. OSM representa os mapeamentos disponíveis nessa data, não necessariamente os equipamentos existentes ou suas condições durante o evento de 2019. Fonte: [OpenStreetMap](https://www.openstreetmap.org/copyright), consultado via [Overpass API](https://overpass-api.de/).

### População

A população afetada **não foi estimada**. O CNEFE do Censo 2022 não foi obtido e a densidade média municipal do IBGE não permite determinar quais moradores residiam nas áreas atingidas. A máscara binária disponível cobre uma extensão regional e pode incluir água permanente; multiplicar sua área positiva pela densidade municipal produziria uma estimativa sem validade espacial. Para calcular esse indicador, é necessário cruzar a inundação com endereços CNEFE ou setores censitários/população do IBGE e distinguir água permanente de alagamento.

### Limitações

- Os quantitativos de edificações reproduzem a análise registrada no JSON de origem; a máscara binária não discrimina, por si só, alagamento de água permanente.
- A contagem de escolas e saúde usa o limite municipal de Tubarão; OSM pode estar incompleto e seus dados são atuais, não uma reconstituição histórica de 2019.
- Os quantitativos de unidades de saúde são uma aproximação baseada nas tags OSM disponíveis; não há uma tag universal que identifique UBS.
