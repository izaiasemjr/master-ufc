# Bosphorus: k automático pelo incremento do desvio padrão

Experimento: `bosphorus-neutrals-occlusions-auto-k-increment`.
Configuração: `configs/experiments/bosphorus_neutrals_occlusions_auto_k_increment.yaml`.

Para cada comparação probe × galeria:

1. Ordenar as distâncias L1 das correspondências em ordem crescente.
2. Começar com k=2 e calcular o desvio padrão populacional `DPCurrent`.
3. Calcular `DPNext` incluindo a próxima distância (prefixo k+1).
4. Se `DPNext / DPCurrent > DPThreshold`, parar e usar o prefixo de tamanho k,
   **excluindo** a distância que provocou a ultrapassagem.
5. Caso contrário, aceitar a distância, incrementar k, atualizar `DPCurrent`
   e repetir até ocorrer uma ultrapassagem ou selecionar todas as distâncias.

A parada é na **primeira** ultrapassagem. Igualdade com o limiar permite
continuar. O score final é a média das distâncias selecionadas; a mediana
continua disponível com `matching.aggregation: median`. O cálculo dos desvios
usa Welford e divisor k (populacional), mantendo a convenção do auto-k anterior.
O limiar agora é uma razão adimensional, não um limite absoluto de desvio padrão.

Convenções para os casos extremos:

- `DPCurrent = DPNext = 0`: razão 1 (nenhum aumento de dispersão).
- `DPCurrent = 0` e `DPNext > 0`: razão infinita, portanto parar.
- Sem ultrapassagem: usar todas as correspondências.
- Apenas uma ou duas correspondências disponíveis: usar todas, sem teste de
  uma próxima distância. k=1 somente quando há apenas uma correspondência.
- Os limiares configurados precisam ser positivos e finitos.

## Configuração e execução

O YAML completo mantém a população, os seletores e as variantes Radial Grid,
SIFT e ISS do experimento base. Os descritores de galeria e probes são
reutilizados diretamente do base para isolar a mudança no matching.

```yaml
matching:
  mode: paper
  selection: auto_k_increment
  reuse_descriptors_from: bosphorus-neutrals-occlusions
  dp_threshold_values: [1.01, 1.025, 1.05, 1.1, 1.15, 1.2, 1.3, 1.4, 1.5, 1.75, 2, 3]
```

```bash
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_auto_k_increment
```

Para outra varredura, copiar o YAML, alterar seu `id` e a lista
`matching.dp_threshold_values` e executar com o novo nome de arquivo.
Uma lista com somente `[1.5]` também é válida. `--overwrite` permite regenerar
as saídas de uma configuração já executada. O YAML usa CMC em 1,5 para todas
as variantes, como no exemplo solicitado; as curvas RR incluem os 12 limiares.

## Saídas

Diretório: `data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions-auto-k-increment/`.

- `matching/<variante>/pair_scores.csv`: `dp_threshold`, score,
  `correspondence_count`, `selected_count` (k escolhido), `selected_stddev`
  (DPCurrent), `next_stddev` e `next_stddev_ratio`.
  As duas últimas colunas ficam vazias se todas as correspondências foram
  selecionadas; razão infinita é exportada como `inf`.
- `classification/<variante>/predictions.csv`: identificação por limiar.
- `evaluation/<variante>/accuracy_by_dp_threshold.csv`: RR por limiar/categoria.
- `evaluation/<variante>/cmc.csv`: CMC para cada limiar/categoria.
- `evaluation/visualization/<variante>/rr_by_dp_threshold.png`: curvas com os
  limiares como posições discretas no eixo horizontal, como no gráfico por k.
- `evaluation/visualization/<variante>/cmc_dp_threshold_1.5.png`: CMC em 1,5.
- `pipeline/resolved-context.json` e `pipeline/pipeline-run.json`: configuração
  resolvida e situação das etapas.

Os testes (`python3 -m unittest discover -s tests -v`) exercitam o executável
real com descritores sintéticos, confrontam a seleção incremental com
`statistics.pstdev`, verificam parada estrita, zeros, conjuntos pequenos,
correspondência fixa/dinâmica e média/mediana. Os testes anteriores cobrem a
compatibilidade com k fixo e o auto-k por limite absoluto de DP.

## Resultado local

Execução concluída com 105 amostras de galeria, 575 probes e 12 limiares nas
três variantes. Todas as quatro etapas terminaram sem falhas.

| Variante | RR global em 1,5 (%) | Melhor limiar da varredura | Melhor RR global (%) |
| --- | ---: | ---: | ---: |
| Radial Grid | 47,130435 | 1,01 | 69,913043 |
| SIFT | 37,913043 | 1,01 | 51,130435 |
| ISS | 42,260870 | 1,01 | 67,478261 |

Os melhores valores acima descrevem a varredura na população local. Não
foi usada uma partição adicional para selecionar o limiar. O melhor resultado
ficou no limite inferior testado; a tabela não estabelece um ótimo fora dessa faixa.
