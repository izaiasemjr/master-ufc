# Influência do registro no reconhecimento facial 3D

Protocolo e pesquisa preparados em 20/10/2026, a partir de
`configs/experiments/bosphorus_neutrals_occlusions.yaml`.

## Experimentos disponíveis

| Condição | Galeria de classificação | Probes | YAML |
| --- | --- | --- | --- |
| A — base | CP-ICP original | CP-ICP original | `bosphorus_neutrals_occlusions.yaml` |
| B — somente galeria registrada | Galeria original preservada | Sem registro | `bosphorus_neutrals_occlusions_gallery_only_registration.yaml` |
| C — nenhum registro | Sem registro | Sem registro | `bosphorus_neutrals_occlusions_no_registration.yaml` |

O protocolo seleciona as mesmas neutras e oclusões nos três casos. A galeria
contém somente `N_N_0` de cada sujeito. `N_N_1`, `N_N_2` etc. são probes,
assim como EYE, GLASSES, MOUTH e HAIR. Na cópia local inspecionada, são
105 galerias e 575 probes: 194 neutras e 381 oclusões.

No código atual, `target_suffix: N_N_0` não significa que cada probe seja
registrada contra a neutra de sua própria identidade. O Python passa
`-target_special mask_mls.pcd` ao C++, e esse destino tem precedência.
A máscara global é construída com as `N_N_0` pré-processadas, alinhadas à
`bs000_N_N_0`. Depois o CP-ICP registra cada face contra essa máscara.
A construção da máscara também não é a mesma operação que registrar a galeria
final usada para extrair descritores.

Em B, `registration.mode: gallery_only` e
`registration.reuse_gallery_from: bosphorus-neutrals-occlusions` copiam
as nuvens registradas, matrizes e landmarks transformados da galeria original.
No matching, somente os descritores da galeria são lidos diretamente do
experimento original; os descritores das probes vêm do novo experimento.
Essa origem fica explícita em `matching/<variante>/descriptor-manifest.tsv`
e em `matching/run.json`. As etapas intermediárias da nova galeria são
executadas, mas seus descritores recalculados não são usados na classificação B.
Isso mantém a galeria efetiva exatamente igual à da condição A.

O controle evita a variação na reconstrução da máscara documentada na auditoria
anterior. No teste nativo desta alteração, os arquivos ISS recalculados também
diferiram, mesmo com a nuvem registrada preservada. Um controle adicional em
`bs000` e `bs005` mostrou conjuntos de keypoints e FPFH exatamente iguais,
apenas em outra ordem. Nesse controle, a permutação não altera o matching
dinâmico, que busca vizinhos por descritor e ordena as distâncias. Portanto,
essa diferença de arquivos ISS, isoladamente, não demonstra mudança de scores.
Ainda assim, B usa os descritores originais para preservar integralmente a
galeria efetiva. O experimento B falha se os artefatos originais necessários estiverem
ausentes; ele não reconstrói silenciosamente outra galeria.

Em C, `registration.mode: none` copia todas as nuvens pré-processadas sem
alterar seus bytes e grava matrizes identidade para manter a interface entre
etapas. Os landmarks originais também são copiados sem transformação ou
resseriação. Nenhum ICP ou CP-ICP é executado nessa condição.

Os dois YAMLs mantêm remoção de outliers, voxelização, crop, grids, detectores,
raios de normais/FPFH, correspondência, agregação, k, classificação e avaliação
do YAML base. A etapa `reference_mask` sai da lista porque sua saída não é
consumida nessas duas condições. `registration` continua como etapa de
encaminhamento/cópia; `landmarks` mantém cada anotação no sistema da sua face.
As matrizes identidade não representam um alinhamento estimado.

## Execução e resultados

O experimento original deve estar concluído e preservado antes de B.
Os resultados locais já existentes não foram sobrescritos nesta implementação.

```bash
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_gallery_only_registration --dry-run
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_no_registration --dry-run

python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_gallery_only_registration
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_no_registration
```

As duas execuções completas ficam em diretórios independentes:

```text
data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions-gallery-only-registration/
data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions-no-registration/
```

Não use `--limit` para medir reconhecimento. Não reexecute A com `--overwrite`
entre as comparações, pois B depende de seus artefatos. Se alterar o protocolo
ou os parâmetros, crie novos IDs e preserve o contexto de origem.

O dry-run principal valida a compilação do plano; ele não executa todas as
validações de entrada de cada etapa. O runner de registro também foi validado
diretamente contra a população pré-processada completa existente: B selecionou
105 cópias da galeria e 575 bypasses; C selecionou 680 bypasses.

A implementação passou pelos testes Python de preservação de coordenadas,
seleção da galeria, ausência de ferramentas PCL nos bypasses, retomada de saída
incompleta, entradas congeladas ausentes e preservação dos demais parâmetros.
Também foi executada a cadeia nativa inteira nos dois modos, com seis faces
reais de dois sujeitos, incluindo galeria, neutra probe e oclusão de olho.
Os logs e controles ficam em
`data/results/BOSPHORUS/analyses/registration-ablation-validation/report.json`.
O controle de ordem do ISS está em `iss-repeat-control.json` no mesmo diretório.
Esse teste reduzido valida a integração; as duas avaliações completas de
680 faces ainda precisam ser executadas para produzir taxas comparáveis.

## Como medir a influência

Compare `evaluation/<variante>/accuracy_by_k.csv` e `cmc.csv` entre A, B e C.
Mantenha o mesmo k ao calcular a diferença em pontos percentuais:

- `accuracy(B) − accuracy(A)`: efeito de retirar registro das probes com a
  galeria registrada fixa.
- `accuracy(C) − accuracy(B)`: efeito adicional de retirar o registro da
  galeria, quando as probes já estão sem registro.
- `accuracy(C) − accuracy(A)`: mudança total ao retirar o registro dos dois lados.

Esses efeitos são condicionais; os três casos não completam um desenho
fatorial 2×2. Para estimar a interação entre registrar galeria e probes,
faltaria uma quarta condição: galeria sem registro e probes registradas.

Use `k=30` no radial, `k=20` no SIFT e `k=50` no ISS para a comparação
compatível com os CMC configurados; apresente também todos os k. Escolher o
melhor k separadamente em cada condição responde outra pergunta e pode esconder
a degradação. Para otimizar k futuramente, use validação separada.

Reporte Rank-1 e CMC por N, cada oclusão, O_ALL e ALL, com denominadores.
Confirme os mesmos IDs de galeria e probes em todas as variantes e condições.
Inspecione `pipeline/pipeline-run.json`, manifests e falhas antes de interpretar
uma taxa: o YAML base infere a população a partir dos descritores existentes.

Compare também `classification/<variante>/predictions.csv` por identidade da
probe e k: quantas passaram de acerto para erro e de erro para acerto?
Para incerteza, recomendo bootstrap pareado por sujeito, preservando todas as
suas probes em cada reamostragem; elas não são observações independentes.
Meça tempo total e o custo economizado no registro. Não compare médias de
`metrics.csv` como se houvesse fitness de ICP nos casos de bypass.

Uma boa taxa em C ainda não demonstra invariância a pose: o protocolo atual
seleciona neutras e oclusões, sem o grupo de rotações explícitas do Bosphorus.
Além disso, o crop e o radial continuam dependentes de landmarks fornecidos.
Retirar registro e retirar landmarks são objetivos distintos.

## Onde o código ainda depende da orientação

O diagnóstico a seguir vem da leitura do projeto, não de taxas que ainda não
foram medidas nas ablações completas.

| Componente | Dependência observada | Consequência |
| --- | --- | --- |
| Crop | Esfera de raio 80 centrada no landmark 13, offset zero | A esfera é compatível com transformações rígidas se face e landmark se moverem juntos; continua exigindo a ponta do nariz. |
| Radial | Círculos em XY; superfície projetada no plano do nariz; vizinho mais próximo em XY | O grid acompanha a translação do nariz, mas não acompanha automaticamente uma rotação 3D da face. |
| Correspondência fixa | Descritor `i` da probe contra descritor `i` da galeria | Mesmo índice pode representar outra região após rotação. |
| Projeção radial sob oclusão | Sempre escolhe o vizinho disponível, sem limite explícito de distância no código | Pode preencher regiões ausentes com bordas ou repetir um ponto; quantidade fixa não garante cobertura válida. |
| SIFT e ISS | Keypoints detectados na geometria; matching dinâmico dos FPFH | São candidatos naturais para começar a retirar registro; sua estabilidade precisa ser medida. |
| Matching dinâmico | Conjunto menor consulta o maior; correspondências muitos-para-um são possíveis | Pequenos subconjuntos de bons matches podem parecer convincentes mesmo com pouca cobertura. |

No projeto, “SIFT” identifica o **detector**, e a descrição também é FPFH.
O SIFT de `PointNormal` usa `curvature` como campo escalar na PCL instalada,
apesar do comentário antigo no código mencionar componentes XYZ das normais.
Isso está confirmado no [código oficial da PCL](https://pointclouds.org/documentation/sift__keypoint_8h_source.html).

O FPFH combina relações angulares locais e distâncias; sua construção oferece
um ponto de partida para descrição sem referencial global. Isso não torna
toda a cadeia invariante: trocar os pontos amostrados ou suas vizinhanças muda
o descritor. A [documentação de FPFH](https://pointclouds.org/documentation/tutorials/fpfh_estimation.html)
também destaca a dependência das normais e dos raios de suporte.

A orientação das normais merece uma auditoria própria. A PCL resolve seu sinal
usando o viewpoint; o extrator não configura esse ponto explicitamente. Nos
cabeçalhos locais inspecionados o viewpoint é zero, e `transformPointCloud`
preserva a origem do sensor na implementação instalada. Assim, transformar a
face sem transformar o viewpoint pode mudar a regra de orientação das normais.
É uma hipótese verificável para parte da sensibilidade, não uma causa já
quantificada. A [documentação de normais da PCL](https://pointclouds.org/documentation/tutorials/normal_estimation.html)
explica a ambiguidade do sinal e sua orientação em relação ao sensor.
Nenhuma correção desse comportamento foi misturada às ablações.

## Pesquisa e estratégias de evolução

Há precedente diretamente ligado ao problema: **Li et al., Towards 3D Face
Recognition in the Real**, publicado online em 2014 no IJCV. O método combina
keypoints de curvatura, descritores em sistemas locais e matching por
representação esparsa, com avaliação em Bosphorus e FRGC. É uma referência
mais próxima deste projeto que classificadores genéricos de objetos 3D.
Remove o registro global, mas ainda constrói referenciais locais. Os protocolos
e descritores diferem dos nossos; suas taxas não constituem uma previsão para
esta implementação. [Artigo no IJCV](https://link.springer.com/article/10.1007/s11263-014-0785-6),
[texto dos autores](https://liris.cnrs.fr/Documents/Liris-6964.pdf).

Minha primeira recomendação é manter ISS/SIFT + FPFH, retirar CP-ICP e
fortalecer as correspondências. Isso permite medir quanto se ganha mudando o
matching antes de trocar a representação. Como novas experiências, testar
vizinhos mútuos, controle de ambiguidade e atribuição parcial com rejeição de
outliers. Exigir cobertura mínima e penalizar muitos-para-um evita que poucos
matches fáceis dominem o score. Esses filtros precisam ser validados, pois
também podem remover correspondências legítimas em faces ocluídas.

Uma forma de preservar estrutura sem estimar rotação/translação é verificar
consistência entre pares de correspondências:

```text
| ||p_i − p_j|| − ||q_a − q_b|| | < tolerância
```

Distâncias internas são invariantes a movimentos rígidos. Um grafo pode
selecionar matches mutuamente compatíveis sem alinhar nuvens. Esta é uma
proposta para o matcher do projeto; não foi implementada nestas ablações.
Expressões exigem tolerância e seleção local, pois alteram distâncias.

Para o radial, uma experiência simples é comparar os mesmos FPFH com
correspondência dinâmica, como variante adicional, sem substituir a fixa dos
três protocolos. Ela testa se a restrição por índice explica parte da perda,
mas o grid XY ainda continua sensível à pose. Para mudar a amostragem,
investigar regiões definidas por distâncias 3D ao nariz, relações entre pontos
e pooling de conjuntos. Só a distância ao nariz perde informação angular e
pode confundir regiões diferentes; será necessário medir esse compromisso.

Se o objetivo for apenas eliminar ICP, um referencial anatômico calculado com
landmarks ou uma base tangente local pode orientar o grid de forma mais barata.
Isso ainda é normalização de orientação. PCA global pode oscilar com oclusão,
simetria e sinais dos autovetores. Para eliminar também essa normalização,
prefira relações invariantes e matching de conjuntos, sem um azimute global
obrigatório.

Descrições intrínsecas, como distâncias geodésicas e regiões sobre a superfície,
também merecem estudo para expressões aproximadamente isométricas. Porém,
buracos e oclusões podem romper caminhos ou criar atalhos numa malha reconstruída.
Eu as trataria como uma linha posterior, com avaliação explícita da topologia,
e não como substituição imediata do radial.

Na linha de aprendizado, estas referências oferecem mecanismos úteis:

| Referência primária | Mecanismo relevante | Como considerar no projeto |
| --- | --- | --- |
| [SpinNet, CVPR 2021](https://arxiv.org/abs/2011.12149) | Descrição local em representação cilíndrica com tratamento da orientação | Candidato a substituir FPFH; testar transferência de domínio para faces e sensibilidade à normal local. |
| [GeoTransformer, CVPR 2022](https://openaccess.thecvf.com/content/CVPR2022/html/Qin_Geometric_Transformer_for_Fast_and_Robust_Point_Cloud_Registration_CVPR_2022_paper.html) | Distâncias entre pares e ângulos de triplas para correspondências | Inspira codificação e consistência geométrica sem depender de XYZ global. O sistema completo estima registro. |
| [RoITr, CVPR 2023](https://openaccess.thecvf.com/content/CVPR2023/html/Yu_Rotation-Invariant_Transformer_for_Point_Cloud_Matching_CVPR_2023_paper.html) | Atenção com relações geométricas invariantes para matching sob rotações | Candidato para descritores/correspondências; desempenho em registro não comprova discriminação de identidade facial. |
| [Vector Neurons, ICCV 2021](https://arxiv.org/abs/2104.12229) | Operações de rede equivariantes a SO(3) | Possível encoder; para reconhecimento, construir uma saída invariante e treinar para identidade. |
| [Beyond Random Masking, 2025](https://arxiv.org/abs/2509.14975) | Pré-treinamento com máscaras estruturadas em modelos invariantes | Linha exploratória para representação; a avaliação publicada citada é de objetos, não deste protocolo facial. |

Esses trabalhos fornecem componentes e hipóteses, sem garantir um reconhecedor
facial pronto. Para retirar registro de fato, extrair descritores ou embedding
e comparar identidades sem usar a transformação estimada pelos métodos de
registro. Também não basta adotar PointNet: sua invariância à permutação dos
pontos não implica invariância garantida a rotações arbitrárias.
[PointNet, CVPR 2017](https://openaccess.thecvf.com/content_cvpr_2017/html/Qi_PointNet_Deep_Learning_CVPR_2017_paper.html).

Treinar uma rede de identidade com somente estes sujeitos traz risco de
superajuste. Separe identidades de treino, validação e teste; não escolha
thresholds ou arquitetura pelas probes finais. Considere pré-treinamento,
augmentation de pose/oclusão e avaliação de transferência. Invariância rígida
também não resolve automaticamente expressão, oclusão ou reamostragem.

## Sequência recomendada

1. Executar A/B/C com as mesmas populações e comparar taxas por k fixo.
2. Testar invariância controlada: aplicar rotações conhecidas em yaw, pitch e
   roll, por exemplo 0°, 5°, 10°, 20° e 30°, e translações, à mesma nuvem
   **depois do pré-processamento**. Transformar também landmarks e viewpoint.
   Isso evita misturar a sensibilidade do voxel com a do descritor/grid.
3. Separar dois testes: transformar os keypoints existentes para medir FPFH e
   redetectar keypoints para medir a cadeia de amostragem. Medir também a
   repetibilidade de ISS e do radial.
4. Repetir o teste transformando os dados antes do pré-processamento para medir
   a cadeia inteira; a grade de voxels fixa aos eixos pode mudar a amostragem.
5. Testar radial dinâmico e ISS/SIFT com matching parcial e consistência por
   distâncias, cada mudança isoladamente.
6. Só então comparar descritores aprendidos ou uma representação invariante.

Se B degradar e C recuperar, haverá evidência de que a incompatibilidade entre
os referenciais dos dois lados contribui para a perda. Se radial degradar mais
que ISS/SIFT, o grid/correspondência fixa passa a ser um candidato prioritário
a investigação. Se ambos os lados sem registro preservarem desempenho, o
CP-ICP poderá ser dispensável **nesse protocolo**, ainda sujeito aos testes
de pose e à dependência de landmarks. Essas são interpretações condicionais
para resultados futuros, não conclusões quantitativas já obtidas.
