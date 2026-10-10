# Roadmap: matching FPFH em lote

Status: **modo `paper` implementado**. A etapa está em `src/matching`, seguida
por `src/classification` e `src/evaluation`.

## Desenho entregue

Python orquestra e valida o protocolo YAML; C++ executa o matching FPFH em
lote. Cada descritor é carregado uma vez por variante e os índices L1 são
construídos uma vez antes das comparações. O resultado é separado em matching,
classificação e avaliação para deixar explícita a transição entre métrica de
par, decisão de identidade e estatística de reconhecimento.

```text
YAML -> runner Python -> matching_batch (C++) -> CSVs auditáveis
                         |- carrega cada PCD uma vez
                         |- constrói índice L1 compartilhado
                         |- compara probe x galeria
                         `- calcula todos os valores de k sem repetir o match
```

## Decisões metodológicas do modo `paper`

- Usa PCL e FPFH de 33 dimensões, com L1 tanto na busca dinâmica quanto no
  escore. Isso corrige a divergência histórica entre o texto metodológico
  (Manhattan/L1) e o antigo uso de `sqrt(sum(abs(...)))`.
- `dynamic`: o conjunto menor consulta a KD-tree L1 do maior. `fixed`:
  compara os índices correspondentes, mas falha se as cardinalidades diferirem.
- Para cada `k`, a métrica é a média dos **exatamente** `min(k, n)` menores
  escores. Empates no limiar não adicionam correspondências extras.
- `expected_count` no YAML é opcional. Quando declarado, valida a população da
  galeria, probes e categorias; quando omitido, a quantidade é inferida dos
  descritores selecionados. O CSV continua exigindo a mesma galeria para cada
  probe e a mesma população em todos os valores de `k`.
- `time_match_ms` exclui I/O, processo e construção de índice; estes custos
  ficam discriminados em `timing.csv`.

## Estrutura de resultados

```text
matching/<variante>/
  descriptor-manifest.tsv
  pair_scores.csv
  timing.csv
classification/<variante>/predictions.csv
evaluation/<variante>/accuracy_by_k.csv
evaluation/<variante>/cmc.csv
```

## Configuração YAML

```yaml
matching:
  mode: paper
  k_values: [2, 5, 10, 20, 30, 40, 50, 1000000]
  gallery:
    type: N
    expression: N
    sample: 0
    expected_count: 105
  probes:
    expected_count: 575
    categories:
      O_EYE:
        type: O
        expression: EYE
        expected_count: 105
  variants:
    sparse_15:
      correspondence: fixed
    sift:
      correspondence: dynamic
```

Para uma divisão treino/teste diferente, use, por exemplo,
`subject_regex: "^bs00[0-4]$"` na galeria e omita ou ajuste os
`expected_count`. Os seletores aceitam valores únicos, listas ou regex para
`subject`, `type`, `expression` e `sample`.

## Próximas melhorias, ainda não implementadas

1. Criar um modo `legacy` isolado somente para reproduzir e comparar os
   resultados históricos. Ele não deve ser confundido com o modo `paper`, pois
   o histórico usa L2 na busca dinâmica e `sqrt(L1)` no escore.
2. Fazer uma comparação controlada `legacy × paper` no mesmo subconjunto e
   registrar, por par, onde as decisões mudam.
3. Se a hipótese exigir escolher um único `k`, definir previamente uma divisão
   validação/teste ou validação cruzada por sujeito. A implementação atual
   apenas relata todos os `k`, conforme o protocolo vigente.
4. Registrar memória máxima e throughput junto aos tempos separados de I/O,
   construção de índices e matching.
