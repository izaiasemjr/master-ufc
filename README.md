# master-researches

Configurações globais em YAML organizam experimentos de reconhecimento facial
3D. Um experimento declara a base, grupos de amostras, parâmetros e as etapas
da pipeline; o executor gera os arquivos específicos de cada etapa apenas no
momento da execução. Os scripts existentes continuam independentes.

## Estrutura

```text
configs/
  datasets/                 # como cada base está organizada
  experiments/              # contextos de teste reutilizáveis
src/pipeline/run.py         # executor global
src/{preprocessing,registration,crop,keypoints,feature_extraction,matching,classification,evaluation}/
data/results/<BASE>/experiments/<TESTE>/
```

Há três contextos Bosphorus prontos:

- `bosphorus_neutrals`: somente nuvens neutras;
- `bosphorus_neutrals_occlusions`: neutras e oclusões;
- `bosphorus_neutrals_expressions`: neutras e expressões.

Cada um grava em uma árvore própria de resultados. Por exemplo, o segundo usa
`data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions/`; portanto,
resultados de cenários diferentes não se misturam.

## Executar

Sempre comece verificando o contexto, sem escrever arquivos:

```powershell
python src/pipeline/run.py --experiment bosphorus_neutrals_occlusions --dry-run
```

Para executar toda a cadeia em Linux/WSL, depois de compilar os executáveis
PCL e instalar os utilitários PCL:

```bash
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions
```

Para uma etapa somente, preserve o mesmo contexto global e selecione-a:

```bash
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions --stage preprocessing
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions --stage registration
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions --stage crop
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions --stage keypoints
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions --stage feature_extraction
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions --stage matching
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions --stage classification
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions --stage evaluation
```

`--stage` pode ser repetido. `--limit 3` processa três nuvens nas etapas que
operam em nuvens, e `--overwrite` permite regenerar saídas existentes. Use
`--print-config` para inspecionar a configuração final que será entregue aos
executores de cada etapa. Uma etapa isolada pressupõe que as saídas das suas
dependências já existam; por exemplo, `crop` requer registro e landmarks.
`feature_extraction` requer tanto `crop` quanto o conjunto de keypoints
referenciado pela variante.
`matching` requer todos os descritores do protocolo; `classification` requer os
scores de matching; e `evaluation` requer as previsões de classificação. As
três etapas analíticas deliberadamente ignoram `--limit`: uma execução parcial
não representa o protocolo científico configurado.

## Matching, classificação e avaliação (modo paper)

O experimento `bosphorus_neutrals_occlusions` declara no YAML a galeria
`N_N_0` e as categorias `N`, `O_EYE`, `O_GLASSES`, `O_MOUTH` e `O_HAIR`.
As quantidades são inferidas da base local, salvo quando `expected_count` é
declarado para reproduzir um protocolo fechado. Ele publica:

```text
matching/<variante>/pair_scores.csv      # probe × galeria × k
matching/<variante>/timing.csv           # I/O, índice e matching separados
classification/<variante>/predictions.csv
evaluation/<variante>/accuracy_by_k.csv  # RR no rank 1
evaluation/<variante>/cmc.csv            # ranks 1..20
```

O modo `paper` usa distância L1 nos 33 bins FPFH em toda a cadeia: busca de
vizinhos na correspondência dinâmica e média dos exatamente `k` menores
valores para a decisão. A variante de grid fixo exige cardinalidades idênticas
de descritores; ela não descarta índices extras silenciosamente. A seleção de
`k` continua sendo apenas relatada para todos os valores configurados — não há
ainda divisão validação/teste para escolher um `k`.

Os números 105 e 575 do protocolo completo Bosphorus são asserções possíveis,
não limites do software. Em outro experimento, altere ou omita `expected_count` e selecione a
galeria/probes com os campos `subject`, `type`, `expression`, `sample`, listas
ou seus equivalentes `*_regex`. Sem `expected_count`, a quantidade é inferida
dos descritores encontrados, mas classificação e avaliação ainda exigem que a
mesma população esteja presente em todos os valores de `k`.

`time_match_ms` mede somente o núcleo em memória de cada par. Leitura de PCD,
inicialização de processo, escrita de arquivo e construção compartilhada dos
índices L1 não entram nesse número; `timing.csv` mantém leitura e indexação em
colunas separadas para que o custo completo também possa ser auditado. Como um
par é calculado uma vez e reutilizado para todos os `k`, não some
`time_match_ms` entre linhas que diferem apenas em `k`.

Se uma etapa falhar, a pipeline para antes das etapas dependentes e imprime um
**Resumo de falhas** com etapa, nuvem e diagnóstico. Ele também é salvo em
`pipeline/pipeline-run.json`. Para falhas de CP-ICP, há ainda um log completo
por nuvem em `registration/errors/<sujeito>/<amostra>.log`, contendo o comando
executado, código de saída, `stdout` e `stderr`.

As etapas ainda podem ser chamadas diretamente com os arquivos JSON históricos
em `data/configs/`. Para novos testes, a interface recomendada é o executor
global com YAML, pois ela garante que o mesmo recorte de amostras seja usado
em todas as etapas.

## Criar um novo teste na mesma base

Copie `configs/experiments/_template.yaml`, altere `id` e escolha os grupos:

```yaml
samples:
  groups: [neutral, occlusion]
```

Os grupos disponíveis para Bosphorus estão em
`configs/datasets/bosphorus.yaml`: `neutral`, `occlusion` e `expression`.
Altere também qualquer parâmetro específico da hipótese, como raio de crop,
detector, raios FPFH, parâmetros CP-ICP ou o processamento de oclusão. O `id` faz parte
do caminho de saída e deve ser exclusivo.

## Adicionar outra base

Crie `configs/datasets/<base>.yaml` usando `bosphorus.yaml` como modelo:

1. defina `paths.raw_clouds` e `paths.landmarks`;
2. defina um `selection.glob` e um regex para cada grupo de amostras;
3. registre a convenção de referência neutra em `reference`;
4. informe os comandos/executáveis aplicáveis à base.

Depois crie um experimento que use `dataset: <base>`. O runner preserva o
caminho relativo de cada nuvem; assim, diferentes organizações por sujeito ou
subdiretório são mantidas nos resultados. Se a nova base exigir uma referência
ou uma estratégia de registro incompatível com CP-ICP/Bosphorus, ela poderá
ter um runner próprio, mantendo o mesmo contrato de experimento.

## Reprodutibilidade

Em uma execução real, o executor salva em
`.../pipeline/resolved-context.json` a configuração expandida e seu hash, e
em `.../pipeline/pipeline-run.json` o resultado de cada etapa. Isso permite
reconstruir exatamente os caminhos, filtros e parâmetros de um resultado.

## Evolução planejada

O desenho entregue e as melhorias ainda futuras — especialmente a comparação
controlada com os resultados legados e a eventual seleção de `k` em uma divisão
independente — estão em [docs/MATCHING_BATCH_ROADMAP.md](docs/MATCHING_BATCH_ROADMAP.md).
