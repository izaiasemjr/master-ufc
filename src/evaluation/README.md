# Avaliação

`run_evaluation.py` transforma as previsões em duas tabelas CSV por variante:

- `accuracy_by_k.csv`: taxa de reconhecimento (RR) no rank 1 para cada `k`;
- `cmc.csv`: taxa cumulativa para ranks 1 até `rank_max`.

As categorias elementares vêm do YAML (`N`, `O_EYE`, `O_GLASSES`, `O_MOUTH`,
`O_HAIR` no protocolo Bosphorus). `O_ALL` e `ALL` são agregadas de forma
explícita. Esta etapa relata todos os `k` configurados; ela **não** escolhe um
`k` usando uma divisão de validação/teste neste momento.

`src/evaluation/visualization/run_visualization.py` consome estas tabelas e
salva figuras em `evaluation/visualization/`, sem misturar dados numéricos e
apresentação gráfica.
