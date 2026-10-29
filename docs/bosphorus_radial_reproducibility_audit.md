# Auditoria: por que o Radial Grid mudou ao incluir expressões

Análise realizada em 20/10/2026. Resultados originais preservados.

A inclusão de probes não alterou o protocolo da galeria. Os manifests das três
variantes têm os mesmos 105 IDs de galeria N_N_0 e todos os IDs anteriores de
probe. Os 453 IDs adicionais têm papel probe e tipo E. A configuração do dataset,
pré-processamento, registro, crop, keypoints, extração e execução é igual nos
contextos salvos. Ambos usam média L1 nos resultados radiais.

O novo experimento reexecutou toda a cadeia. A composição da galeria foi mantida,
mas seus artefatos processados foram recalculados e mudaram.

## Primeira divergência observada

Comparação binária dos arquivos comuns:

| Artefatos | Idênticos | Diferentes |
| --- | ---: | ---: |
| Nuvens pré-processadas | 680 | 0 |
| Galeria alinhada para construir a máscara | 102 | 3 |
| Nuvens após CP-ICP | 0 | 680 |
| Nuvens recortadas | 0 | 680 |
| Keypoints sparse_15_11_11_6 | 0 | 680 |
| Descritores FPFH radiais | 0 | 680 |

As três faces diferentes no alinhamento da máscara são bs056_N_N_0,
bs070_N_N_0 e bs089_N_N_0. A maior distância entre pontos correspondentes dessas
faces é, respectivamente, aproximadamente 0,000370, 0,003384 e 0,000177 nas
unidades da base. Não se trata apenas de diferenças de cabeçalho: as coordenadas
mudaram. A máscara MLS tem 1.020.844 pontos em ambos; 773.355 posições XYZ diferem
por índice, com distância média 0,0001633 e máxima 0,60665. Essas distâncias são
comparações por índice, não distâncias ao vizinho mais próximo.

Repeti pcl_icp com a mesma nuvem pré-processada bs000_N_N_0 como referência,
a mesma bs056_N_N_0 como entrada e os mesmos parâmetros -d 200 -r 50 -i 50.
Uma das três execuções diferiu das outras duas, com diferença máxima absoluta
por coordenada de aproximadamente 0,0003171. Isso reproduz variação numérica
na etapa sem adicionar expressões. O mecanismo interno de baixo nível dessa
variação não foi isolado; não atribuo a causa a semente aleatória ou OpenMP.

## Controle causal: trocar somente a máscara

Reprocessei bs053_N_N_0 com a mesma entrada, executável e parâmetros, variando
apenas mask_mls.pcd entre as duas versões existentes. O CP-ICP testa seis
partições (duas em cada eixo) e aplica à face completa a transformação da que
tem menor getFitnessScore().

| Máscara | Fitness da partição 2 | Fitness da partição 3 | Partição escolhida |
| --- | ---: | ---: | ---: |
| Original | 0,365794 | 0,380486 | 2 |
| Com expressões | 0,386996 | 0,380330 | 3 |

Os índices começam em zero. As duas transformações reproduzidas são exatamente
iguais, inclusive na serialização .mat, às versões salvas nos respectivos
experimentos. As posições dos pontos da face bs053_N_N_0 após registro diferem
em média 10,0883 unidades e até 19,1041. Portanto, uma diferença pequena na máscara
pode resultar numa troca discreta de partição e numa transformação maior.

O grid mantém a regra e a ordem dos 106 índices, mas usa a ponta do nariz
transformada e busca o ponto da superfície mais próximo de cada posição no
plano XY. Ordem igual não garante coordenadas iguais quando a face de entrada
muda. Os FPFH também dependem da superfície recortada e das normais/vizinhanças.
No exemplo bs000_N_N_0, todos os 106 keypoints e todos os 106 vetores FPFH têm
alguma coordenada/componente diferente entre os experimentos.

## Controle causal: adicionar somente probes

Criei um manifest com a galeria e todas as probes do experimento original
apontando para seus descritores originais, acrescentando os 453 descritores
de expressão do novo experimento. Rodei o matcher atual com correspondência
fixa, média L1 e os mesmos oito valores de k.

- Scores originais comparados: 575 probes × 105 galerias × 8 k = 483.000.
- Scores originais idênticos: 483.000.
- Scores originais diferentes: zero.
- Scores adicionais de expressões: 380.520.

A comparação cobre todas as colunas exceto time_match_ms. Assim, com os
artefatos anteriores preservados, adicionar expressões mantém exatamente todos
os scores antigos e consequentemente seus rankings e taxas.

## Leitura das figuras

A legenda mostra a melhor taxa da categoria entre os k avaliados, com o k entre
colchetes; não corresponde necessariamente ao mesmo k nos dois gráficos.

| Categoria | Melhor taxa original | Melhor taxa com expressões |
| --- | --- | --- |
| Neutral | 188/194 = 96,91% (k=20) | 186/194 = 95,88% (k=10) |
| Eye | 97/105 = 92,38% (k=30) | 97/105 = 92,38% (k=40) |
| Glasses | 93/104 = 89,42% (k=40) | 94/104 = 90,38% (k=50) |
| Mouth | 89/105 = 84,76% (k=20) | 90/105 = 85,71% (k=20) |
| Hair | 54/67 = 80,60% (k=5) | 55/67 = 82,09% (k=5) |

Mesmo em k fixo há diferenças: em k=30, Neutral passa de 187 para 185 acertos,
Eye de 97 para 96 e Mouth de 85 para 86. Glasses permanece com 91, mas duas
probes trocam de estado de acerto em sentidos opostos. O_ALL mantém 322 acertos
nesse k por compensação. A igualdade de uma taxa agregada não garante igualdade
das decisões individuais.

Para um experimento que isole a inclusão de probes, preservar os descritores
originais da galeria e das probes antigas; processar as expressões usando a
mesma máscara original. Para avaliar variação entre execuções completas,
tratar a reconstrução da máscara como uma fonte de variabilidade separada.

## Evidências locais

`data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions-expressions/analyses/reproducibility-audit/`:

- artifact-comparison.json: contagens e faces diferentes no alinhamento.
- icp-repeat.json e icp-bs*/stdout.log: repetições com entradas fixas.
- cp-icp-bs053-original/stdout.log e cp-icp-bs053-expressions/stdout.log:
  fitness e seleção de partição sob as duas máscaras.
- cp-icp-mask-control.json: igualdade das transformações reproduzidas.
- controlled-manifest.tsv, controlled-scores.csv e controlled-comparison.json:
  controle com descritores antigos preservados e novas probes adicionadas.
- changed-predictions-k30.json: mudanças de acerto em k=30.
