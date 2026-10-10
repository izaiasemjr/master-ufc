# Classificação

Esta etapa consome `matching/<variante>/pair_scores.csv` e publica uma única
decisão por probe e por `k` em `classification/<variante>/predictions.csv`.
Ela exige que todos os probes tenham a mesma galeria. No protocolo Bosphorus
atual isso corresponde a 105 comparações por probe, mas esse número vem do
YAML: `expected_count` é opcional e pode ser removido ou alterado em outro
desenho treino/teste.

A decisão é a menor `distance_mean_l1`. Empates são ordenados de modo
determinístico pelo identificador completo da galeria e são preservados pela
coluna `tie_count_at_best`; `true_rank` usa a mesma regra, tornando a análise
CMC reproduzível.
