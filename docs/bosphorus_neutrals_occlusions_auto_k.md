# Bosphorus com seleção automática de k por desvio padrão

Configuração: `configs/experiments/bosphorus_neutrals_occlusions_auto_k.yaml`.
O id é `bosphorus-neutrals-occlusions-auto-k`.

Para cada comparação probe × galeria, as distâncias L1 das correspondências
são ordenadas em ordem crescente. Para cada prefixo de tamanho k, calcula-se
seu desvio padrão **populacional** (divisor k). Escolhe-se o **maior k ≥ corr_min**
com `stddev(distancias[:k]) < DP`. Se nenhum prefixo a partir desse mínimo
atender ao critério, usa-se **k = corr_min**, mesmo que seu desvio padrão
seja maior ou igual a DP. O score permanece a média L1 das distâncias
selecionadas (`aggregation: median` também é suportado). O k varia entre
comparações, inclusive para a mesma probe e o mesmo DP.

A comparação é estrita: igualdade com DP não atende ao critério. DP deve ser
finito e positivo; `matching.corr_min` deve ser um inteiro positivo. O YAML
principal usa **corr_min=5**. Quando o parâmetro é omitido, o padrão do código
é 1 para compatibilidade. Se uma comparação tiver menos correspondências
que o mínimo configurado, o matching falha com um diagnóstico explícito. Distâncias
iguais podem permitir selecionar todas as correspondências mesmo com DP baixo.
O algoritmo verifica todos os prefixos: seu desvio padrão não é necessariamente
monótono. Os momentos são calculados com o algoritmo de Welford.

DP usa as unidades das distâncias L1 dos FPFH; não é uma porcentagem nem um
valor normalizado. A busca inicial usa:

```yaml
matching:
  mode: paper
  selection: auto_k
  corr_min: 5
  reuse_descriptors_from: bosphorus-neutrals-occlusions
  dp_values: [0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 40, 60, 80, 100]
```

O YAML completo mantém os seletores da galeria, probes e variantes Radial Grid,
SIFT e ISS do experimento base. A execução reutiliza os descritores existentes
de **toda** a população do base, sem recalcular registro, keypoints ou FPFH.
Esse caminho é registrado no contexto resolvido. O base deve existir previamente.
A reutilização exige um pipeline contendo somente etapas de reconhecimento.

```bash
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_auto_k
```

Para uma nova varredura independente, copie o YAML, altere o `id` e
`matching.dp_values` e execute usando o nome do arquivo novo sem `.yaml`.
Uma lista com um único DP também é válida. Para substituir resultados da mesma
configuração, use `--overwrite`. Experimentos sem `selection: auto_k` continuam
usando `k_values` e os nomes de arquivos originais.

Saídas em `data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions-auto-k/`:

- `matching/<variante>/pair_scores.csv`: DP, score, `selected_count` (k
  escolhido), `selected_stddev`, `corr_min` e total de correspondências.
  `selected_stddev ≥ DP` é permitido somente quando `selected_count = corr_min`.
- `classification/<variante>/predictions.csv`: identificação e rank por DP.
- `evaluation/<variante>/accuracy_by_dp.csv`: RR por DP e categoria.
- `evaluation/<variante>/cmc.csv`: CMC por DP e categoria.
- `evaluation/visualization/<variante>/rr_by_dp.png`: curva RR × DP (eixo DP logarítmico para separar os limiares baixos).
- `evaluation/visualization/<variante>/cmc_dp_<DP>.png`: CMC no DP declarado
  em `visualization.cmc_dp`: 30 para Radial Grid, 20 para SIFT e 15 para ISS,
  limiares declarados para essas figuras. As legendas das curvas RR informam
  o melhor DP observado para cada categoria.
- `pipeline/resolved-context.json` e `pipeline/pipeline-run.json`: contexto,
  proveniência e situação das etapas.

O maior RR da varredura é descritivo deste conjunto de avaliação; a escolha de
DP para generalização precisa de validação separada.

Validação automatizada: `python3 -m unittest discover -s tests -v`.
Os testes usam descritores sintéticos no executável real, conferem o resultado
com `statistics.pstdev`, os casos de igualdade, prefixos não monótonos,
correspondência fixa/dinâmica, média/mediana e compatibilidade com k fixo.

## Varredura de corr_min

O experimento principal foi sobrescrito com `corr_min=5`. Para preservar as
outras execuções, há mais três YAMLs e diretórios independentes:

| corr_min | YAML (em configs/experiments/) | ID / diretório de resultados |
| ---: | --- | --- |
| 5 | bosphorus_neutrals_occlusions_auto_k.yaml | bosphorus-neutrals-occlusions-auto-k |
| 7 | bosphorus_neutrals_occlusions_auto_k_corr_min_7.yaml | bosphorus-neutrals-occlusions-auto-k-corr-min-7 |
| 9 | bosphorus_neutrals_occlusions_auto_k_corr_min_9.yaml | bosphorus-neutrals-occlusions-auto-k-corr-min-9 |
| 12 | bosphorus_neutrals_occlusions_auto_k_corr_min_12.yaml | bosphorus-neutrals-occlusions-auto-k-corr-min-12 |

Todos usam os mesmos 14 DPs, 575 probes, 105 amostras de galeria e os mesmos
descritores do base. Cada execução contém matching, classificação, avaliação
e visualização para Radial Grid, SIFT e ISS. A seleção por razão incremental
permanece independente deste parâmetro.

```bash
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_auto_k --overwrite
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_auto_k_corr_min_7 --overwrite
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_auto_k_corr_min_9 --overwrite
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_auto_k_corr_min_12 --overwrite
```

## Resultados com o piso de correspondências

As quatro execuções concluíram as quatro etapas sem falhas. Os 15 testes
passaram, incluindo a regra de piso forçado, os quatro mínimos, o caso de
menos correspondências disponíveis e a compatibilidade com os modos anteriores.
Melhores taxas globais por variante e corr_min (menor DP em caso de empate):

| corr_min | Radial Grid RR (%) | DP | SIFT RR (%) | DP | ISS RR (%) | DP |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 86.434783 | 30 | 90.782609 | 20 | 93.913043 | 15 |
| 7 | 86.434783 | 0.5 | 90.782609 | 20 | 93.913043 | 15 |
| 9 | 87.478261 | 0.5 | 90.782609 | 20 | 93.913043 | 15 |
| 12 | 88.000000 | 0.5 | 90.782609 | 20 | 93.913043 | 15 |

Aumentar corr_min reduziu o vale de reconhecimento em DP entre 5 e 10,
mas ele ainda aparece. O maior ganho no Radial Grid ocorreu nos DPs baixos;
os melhores resultados globais de SIFT e ISS permaneceram iguais entre os
quatro mínimos testados.

O comparativo fica em `evaluation/corr_min_comparison/`, dentro do experimento
principal: `rr_by_dp_all_corr_min.png`, `accuracy_by_dp_corr_min.csv`
(todas as categorias) e `best_accuracy_by_corr_min.csv` (melhor RR global).
Para regenerá-lo após concluir as quatro execuções:

```bash
python3 scripts/analyses/compare_auto_k_corr_min.py
```
