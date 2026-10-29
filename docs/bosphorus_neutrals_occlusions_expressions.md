# Bosphorus: neutras, oclusões e expressões

Configuração: `configs/experiments/bosphorus_neutrals_occlusions_expressions.yaml`.

Galeria: 105 amostras `N_N_0`, uma por sujeito. Probes: 194 neutras adicionais,
381 oclusões e 453 expressões, totalizando 1.028. Expressões: ANGER (71),
DISGUST (69), FEAR (70), HAPPY (106), SADNESS (66) e SURPRISE (71).
As contagens esperadas no YAML impedem uma avaliação silenciosa de uma
população incompleta.

Mantém os parâmetros do experimento `bosphorus_neutrals_occlusions`, incluindo
agregação pela média L1, variantes sparse_15, SIFT e ISS e um worker.
O reconhecimento usa comparação com a galeria; não há uma etapa adicional
de treinamento neste pipeline.

```bash
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_expressions
```

Resultados em `data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions-expressions/`:

- `evaluation/<variante>/accuracy_by_k.csv`: taxas por categoria e k.
- `evaluation/<variante>/cmc.csv`: curvas CMC.
- `evaluation/visualization/`: figuras.
- `pipeline/pipeline-run.json`: resultado das etapas ao encerrar a execução.

A execução inicial foi iniciada em segundo plano em 19/10/2026. Seus arquivos
adicionais de acompanhamento estão em `pipeline/`: `execution.log`,
`execution.pid` e `execution-status.json`. O launcher desta execução gera
`occlusion-comparison.json` após sucesso, comparando as linhas O_* das tabelas
de acurácia e CMC com o experimento original. Essa comparação adicional pertence
ao launcher local; o comando padrão acima executa somente a pipeline.

Com a mesma galeria, os mesmos descritores e os mesmos parâmetros, adicionar
probes não altera o ranking das probes anteriores nem as taxas de O_* e O_ALL.
A taxa ALL passa a incluir as expressões. Esta execução refaz o processamento;
se as taxas de oclusão divergirem, é necessário verificar os artefatos e o
processamento, pois a simples ampliação das probes não explica a diferença.
