# Matching em lote

`run_matching.py` organiza o protocolo declarado no YAML e chama
`matching_batch`, o núcleo C++ em lote. Cada descritor é carregado uma vez por
variante; o núcleo calcula todas as combinações probe × galeria e todos os
valores de `k` em memória.

O único modo atual é `paper`. Ele usa L1 nos 33 bins FPFH, procura vizinho mais
próximo por L1 nas variantes dinâmicas e usa exatamente os `k` menores valores
(ou todos, quando `k` é maior que o número de correspondências). A variante
`fixed` exige a mesma quantidade de descritores nos dois arquivos; ela jamais
trunca silenciosamente uma comparação indexada.

`gallery` e cada categoria de `probes` aceitam seletores por valor, lista ou
regex (`subject_regex`, `type_regex`, `expression_regex`, `sample_regex`).
`expected_count` é opcional: quando presente, funciona como uma asserção de
protocolo; quando ausente, a quantidade é inferida dos descritores selecionados.
Assim, uma nova divisão treino/teste não exige alteração de código.

`pair_scores.csv` contém uma linha por `probe × gallery × k`. `timing.csv`
separa `descriptor_loading_ms`, `index_build_ms` e `pair_matching_ms`. Apenas
`time_match_ms` em `pair_scores.csv` é a medida por par: inicia antes da busca
de correspondências e termina após o cálculo da métrica; leitura de PCD,
criação de processo, escrita de CSV e construção de índices não fazem parte
dessa medida.

Compile em Linux/WSL:

```bash
cmake -S src/matching -B src/matching/build
cmake --build src/matching/build -j
```
