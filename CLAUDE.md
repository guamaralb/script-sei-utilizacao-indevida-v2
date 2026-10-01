# Script SEI - Utilização Indevida (v2)

Automação Selenium no SEI-MG (IPSEMG) que prepara a apuração de utilização
indevida da assistência à saúde:

- classifica os processos;
- extrai as instruções dos memorandos da APIS;
- avalia o uso da rede própria;
- gera os memorandos para DISA e DEPROC.

A pesquisa da utilização indevida em si **ainda não foi implementada**.

O fluxo completo está desenhado em [`docs/fluxo.drawio`](docs/fluxo.drawio)
(seção [Fluxo do processo](#fluxo-do-processo)).

## Glossário

- **APIS-Utilização**: unidade que envia as instruções. O memorando traz
  titular, dependentes e períodos.
- **GEACS-Utilização**: nossa unidade. Emite os memorandos.
- **DISA**: levanta os atendimentos na rede própria.
- **DEPROC**: levanta a coparticipação. Recebe sempre todos os beneficiários.
- **Processo NOVO**: sem nenhum documento da GEACS na árvore.
- **Processo VELHO**: já contém documento da GEACS.
- **Marcador (tag)**: marcador do SEI. É a memória do sistema entre
  execuções: registra o que foi feito e permite retomar o trabalho.

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Script principal: classifica e processa qualquer processo |
| `main_add_memo_nao_usou_rede_propria.py` | Script de correção dos NOVOS enviados sem avaliação da rede própria |
| `processar_novo.py` | Fluxo normal dos NOVOS; `obter_dados_ui()` lê o último memo da APIS |
| `processar_velho.py` | Fluxo dos VELHOS (**somente estrutura**, com TODOs) |
| `correcao_rede_propria.py` | Rotina de correção, usada pelos dois scripts |
| `rede_propria.py` | Carga da planilha de rede própria e da base geral, normalização de matrícula, `avaliar_uso()`, `ErroAvaliacao`, `MatriculasNaoEncontradas` |
| `docs_processo.py` | Filtros da árvore e busca, pelo assunto, do memo de correção e do memo à APIS |
| `extrator_dados_ui.py` | Extrai as instruções do texto do memo da APIS (modelos "novo" e "velho") |
| `matriculas_nao_encontradas.py` | Registra as matrículas não encontradas, cria o memo à APIS (base geral) e adiciona o marcador de cada base (NOVO ou VELHO) |
| `tags.py` | Todos os marcadores, `registrar_tags()` e `adicionar_tag()` |
| `marcadores_disponiveis.py` | `garantir_marcadores_no_sei()`: confere, antes de criar memos, se os marcadores existem no SEI |
| `constantes.py` | Unidades, blocos, signatária, caminhos fixos |
| `log_config.py` | Logging compartilhado: processo atual em cada linha e resumo final |
| `Registro.py` | Um registro por processo (uma linha da planilha de controle), `ProxAcao` e `registrar_erro()` |
| `planilha_controle.py` | Grava e formata a planilha de controle (usado pelos dois scripts) |
| `memorandos/` | `DadosUI`, `MemoDisa`, `MemoDeproc`, `MemoDisaUsoRede`, `MemoApisMatNaoEncontradas` |
| `docs/fluxo.drawio` | Diagrama do fluxo (uma página por seção do [Fluxo do processo](#fluxo-do-processo)) |

A biblioteca `sei_automacao` é externa (login, árvore, marcadores,
memorandos, blocos). Não altere a biblioteca; use apenas a API dela.

## Convenções

- Python 3.10+ (`str | None`, `zip(strict=True)`).
- Código, nomes e mensagens em português.
- Aspas simples.
- Lint com **ruff** (preview ativo, ex.: PLR6301).
- Os dois `main` ficam em arquivos separados, e **um nunca importa o
  outro**. Lógica comum vai para os módulos compartilhados.
- Caminhos de arquivos de entrada são **fixos**, com data no nome. Não
  parametrize.
- Grafias de unidade são **diferentes de propósito**. Use as constantes:
  - `'IPSEMG/GEACS - Utilização'` (com espaços);
  - `'IPSEMG/APIS-Utilização'` (sem espaços).
- Estilos de import existentes: `from Registro import ...` e
  `from script_sei_utilizacao_indevida_v2.memorandos... import ...`.
  Siga o padrão do arquivo que estiver editando.
- Tratamento de erros:
  - erro esperado nos dados: levante `ErroAvaliacao` ou
    `FormatoMemorandoInvalido`; é logado sem traceback;
  - falha inesperada: logada com `logger.exception`.
- Um erro em um processo **nunca** interrompe os demais.
- Logs:
  - use `logging.getLogger(__name__)`;
  - não prefixe o número do processo na mensagem, pois
    `contexto_processo` já o injeta;
  - toda ação no SEI (memo criado, bloco, marcador, reabertura) gera um
    `logger.info`.
- Marcadores: adicione **sempre** com `tags.adicionar_tag(driver, registro,
  tag)`, que também preenche o atributo e a coluna
  `marcadores_adicionados`. Não chame `adicionar_marcador` direto.
- **Antes de criar qualquer memo**, chame
  `garantir_marcadores_no_sei(driver, [marcadores que serão adicionados])`.
  Se um nome não existir no SEI, o processo para antes do memo (senão o
  memo fica no bloco sem marcador). A lista é lida na tela "Gerenciar
  Marcador", sem salvar, uma vez por execução; se faltar um nome, é relida
  uma vez.
- `prox_acao`: use os valores de `Registro.ProxAcao`. Não escreva textos
  soltos; detalhes vão para as demais colunas e para o log.
- Erros: registre com `Registro.registrar_erro(registro, e)` (preenche
  `tipo_erro`, `erro` e, se preciso, `prox_acao = Verificar erro`). A
  coluna `erro` recebe só uma frase; erros do Selenium sem mensagem viram
  "Tempo esgotado esperando elemento do SEI em <função>". O traceback
  completo fica no log.
- Ao mudar o fluxo (pergunta, ação, marcador ou `prox_acao`), atualize a
  seção [Fluxo do processo](#fluxo-do-processo) **e** a página
  correspondente de `docs/fluxo.drawio`.

## Regras de negócio

### Bases de matrículas (compartilhadas)

- **Base da rede própria (DISA)**:
  `beneficiarios_atendidos_rede_propria-2026_09_23.xlsx`, abas
  `UI 2025 EX-TITULARES` (coluna `MATRICULAS TITULARES`) e
  `UI 2025 EX-DEPENDENTES` (coluna `MATRICULAS DEPENDENTES - SEM DV`), com
  a resposta em `UTILIZOU A REDE PRÓPRIA?`.
- **Base geral** (listagem de todos os beneficiários):
  `planilha_da_galantini_com_listagem_de_todos_beneficiarios.xlsx`, abas
  `UI 2025 EX-TITULARES` (coluna `MATRICULAS TITULARES`, cabeçalho com
  espaço sobrando) e `UI 2025 EX-DEPENDENTES` (coluna
  `MATRICULAS DEPENDENTES`). **Todas as matrículas têm DV.**
- Nos processos, o **titular vem com DV** e os **dependentes vêm sem DV**.
  O DV é o último dígito: ele é retirado dos dependentes da base geral na
  carga.
- Matrícula normalizada: sem hífen, sem zeros à esquerda.
- Matrícula repetida: um SIM prevalece. Resposta inválida prevalece sobre
  NÃO.
- `avaliar_uso` busca o titular e os dependentes nas **duas** bases antes
  de parar. Se alguma matrícula não for encontrada, levanta
  `MatriculasNaoEncontradas` (subclasse de `ErroAvaliacao`) com o
  resultado de cada base, e quem chamou executa a rotina da
  [seção 5](#5-matrículas-não-encontradas-marcar_matriculas_nao_encontradas).
  Os demais processos continuam normalmente.
- São `ErroAvaliacao` em `avaliar_uso`:
  - resposta inválida (nem SIM nem NÃO);
  - dependentes citados sem matrícula explícita (`AVERIGUAR`, modelo
    velho);
  - matrícula em formato inválido;
  - sem matrícula de titular.
- Os períodos **não** são usados na consulta de rede própria. Eles só são
  compilados na planilha de controle para a consulta final.

### Marcadores (`tags.py`)

Prefixo de todos os nomes: `Script v2 - `.

| Marcador | Significado | Onde é adicionado |
|---|---|---|
| `1 - Processo NOVO` | Classificação: NOVO | [1](#1-script-principal-mainpy-início-e-classificação) |
| `1.1 - Período Variável p/ Dependentes` | Memo da APIS tem período específico para dependentes | [3](#3-novo-fluxo-normal-processar_novo), antes dos memos |
| `1.2 - Avaliado Se Usou Rede Própria` | Uso da rede própria avaliado | [3](#3-novo-fluxo-normal-processar_novo), depois dos memos; [4](#4-rotina-de-correção-corrigir_uso_rede_propria) |
| `1.2.1 - Mat. N Encontradas Base Geral` | NOVO parado: matrícula não encontrada na base geral; memo à APIS no bloco | [5](#5-matrículas-não-encontradas-marcar_matriculas_nao_encontradas) |
| `1.2.2 - Mat. N Encontradas Base DISA` | NOVO parado: matrícula não encontrada na base da rede própria | [5](#5-matrículas-não-encontradas-marcar_matriculas_nao_encontradas) |
| `1.3 - Memos DISA e DEPROC no Bloco` | Alguém usou; os dois memos estão no bloco | [3](#3-novo-fluxo-normal-processar_novo), depois do 1.2 |
| `1.3 - Memo DEPROC no Bloco` | Ninguém usou; só a DEPROC foi acionada | [3](#3-novo-fluxo-normal-processar_novo), depois do 1.2 |
| `1.4 - Memo Não Usou Rede no Bloco` | Memo de correção no bloco | [4](#4-rotina-de-correção-corrigir_uso_rede_propria), antes do 1.2 |
| `2 - Processo VELHO` | Classificação: VELHO | [1](#1-script-principal-mainpy-início-e-classificação) |
| `2.1 - Transformar Excel em PDF` | VELHO sem instrução de nova pesquisa (fluxo não implementado) | [6](#6-velho-somente-estrutura) |
| `2.1 - Refazer Relatório de UI` | VELHO com instrução de nova pesquisa (fluxo não implementado) | [6](#6-velho-somente-estrutura) |
| `2.1.1 - Mat. N Encontradas Base Geral` | VELHO parado: matrícula não encontrada na base geral; memo à APIS no bloco | [5](#5-matrículas-não-encontradas-marcar_matriculas_nao_encontradas) (previsto) |
| `2.1.2 - Mat. N Encontradas Base DISA` | VELHO parado: matrícula não encontrada na base da rede própria | [5](#5-matrículas-não-encontradas-marcar_matriculas_nao_encontradas) (previsto) |
| `2.2 - Excel Transformado em PDF` | Conclusão do 2.1 "Transformar Excel em PDF" | Não implementado |
| `2.2 - Relatório de UI Refeito` | Conclusão do 2.1 "Refazer Relatório de UI" | Não implementado (após a pesquisa) |
| `PLANILHADO`, `UTILIZAÇÃO INSERIDA` (sem prefixo) | Manuais; não interferem na classificação | Manualmente |
| `MANUAL`, `ASSINADO` (sem prefixo) | Manuais; tiram o processo do escopo do script de correção | Manualmente |

- Numeração: o primeiro número é o ramo (1 = NOVO, 2 = VELHO) e o número
  após o ponto é a ordem de inserção. **Mesmo número = alternativas** (o
  processo recebe um ou outro).
- O SEI limita o nome do marcador a **50 caracteres**.
- Os nomes em `tags.py` precisam ser **idênticos** aos cadastrados no SEI.
  Para renomear, edite o marcador existente no SEI (não crie outro) e
  atualize `tags.py` antes da próxima execução; senão os processos já
  marcados deixam de ser reconhecidos.

### Invariantes (não quebrar)

- Os marcadores de conclusão são adicionados **somente depois** que os memos
  estão no bloco. A ordem é AVALIADO e depois o marcador de memos no
  bloco. Isso impede memos duplicados quando o script falha no meio.
- O memo DISA do fluxo normal **só existe se alguém usou** a rede própria.
  `MemoDisa` levanta `ValueError` se ninguém usou.
- O memo de correção **só existe se alguém NÃO usou**.
  `MemoDisaUsoRede` levanta `ValueError` se todos usaram.
- O memo de correção é identificado na árvore **pelo assunto**
  (`PADRAO_ASSUNTO_MEMO_USO_REDE`, que aceita também a grafia antiga
  "Rede Prória"). Antes de criar, sempre verifique se ele já existe.
- O memo à APIS só existe se alguma matrícula **não foi encontrada na
  base geral**. Também é identificado **pelo assunto**
  (`PADRAO_ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS`; **não altere o assunto**).
  Se já existir sem o marcador `1.2.1`/`2.1.1`, é **retomada**: o memo não
  é recriado e só os marcadores são adicionados (coluna
  `memo_apis_mat_nao_encontradas_na_arvore`). Diferente do memo de
  correção, que nesse caso gera erro para verificação manual.
- Blocos de assinatura:
  - `7697744`: memos DISA e DEPROC do fluxo normal;
  - `7707212`: memo de correção;
  - `7711907` (`BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS`): memo à APIS. Se a
    constante for `None`, o processo para com erro antes de criar o memo
    e sem adicionar marcadores.
- Signatária: Bruna Miiller Lavarini, Gerência de Auditoria e Contas da
  Saúde.

---

## Fluxo do processo

Diagrama: [`docs/fluxo.drawio`](docs/fluxo.drawio). Cada subseção abaixo
corresponde a uma página do diagrama com o mesmo número. A página 8 traz a
legenda e a tabela de marcadores.

### Como ler

- Um processo avança **ao longo de várias execuções**. Os marcadores do SEI
  guardam o estado: cada execução lê os marcadores, decide o que falta e
  continua dali.
- As perguntas de cada seção estão **na ordem em que o código as avalia**;
  vale a primeira que for verdadeira.
- **➕ `X`** indica o ponto exato em que o marcador `X` é adicionado
  (sempre via `tags.adicionar_tag`).
- Todo processo termina com uma `prox_acao` (valor de `ProxAcao`) ou com
  erro (`registrar_erro`). Em ambos os casos o registro vira uma linha da
  planilha de controle e o loop segue para o próximo processo.

### Ciclo de vida dos marcadores

| Caminho | Sequência de marcadores |
|---|---|
| NOVO, fluxo normal | `1` → [`1.1`] → `1.2` → `1.3` (um dos dois) |
| NOVO enviado sem avaliação (correção) | `1` → `1.3 Memos DISA e DEPROC` (já existentes) → [`1.4`] → `1.2` |
| NOVO parado | `1` → `1.2.1` e/ou `1.2.2` |
| VELHO | `2` → `2.1` (uma das pendências) → [`2.1.1`/`2.1.2`] → `2.2` (conclusão correspondente) |

### 1. Script principal (`main.py`): início e classificação

**Início**

1. Lê `dados/inputs/processos_nao_processados.xlsx` (aba
   `processos_reais`, coluna `num_sei`).
2. Carrega a base da rede própria e a base geral.
3. Faz login no SEI.

**Para cada processo**

1. Abre o processo, lista a árvore, conta documentos e memorandos da GEACS
   e lê os marcadores **do SEI**.
2. Classificação (`_classificar_e_processar`):

| # | Pergunta | Se sim |
|---|---|---|
| 1 | Tem `1` e `2`? | Erro |
| 2 | Tem `2` (VELHO)? | [Seção 6](#6-velho-somente-estrutura) |
| 3 | Tem `1` (NOVO)? | [Seção 2](#2-novo-roteamento-_tratar_novo) |
| 4 | Tem outro marcador `Script v2`? | Erro (marcadores do script sem NOVO/VELHO) |
| 5 | Há documento da GEACS na árvore? | **➕ `2`**; `prox_acao` = Processar VELHO. O fluxo VELHO só roda na **próxima execução** |
| — | (nenhuma das anteriores) | **➕ `1`** e segue, **na mesma execução**, para a [seção 3](#3-novo-fluxo-normal-processar_novo) |

Marcadores manuais (`PLANILHADO`, `UTILIZAÇÃO INSERIDA`) não contam na
pergunta 4.

**Fim**: salva a planilha de controle e o resumo no log
([Saídas](#saídas)).

### 2. NOVO: roteamento (`_tratar_novo`)

Entrada: processo com `1`. **Nenhum marcador é adicionado nesta seção**:
ela só decide para onde o processo vai.

| # | Pergunta | Se sim |
|---|---|---|
| 1 | Tem `1.2.1` ou `1.2.2`? | Erro: processo parado. `prox_acao` = Verificar matrículas não encontradas. Para reprocessar, corrija a base e remova os marcadores manualmente no SEI |
| 2 | Tem `1.2` (AVALIADO)? | Conferência (abaixo) |
| 3 | Tem `1.3 Memos DISA e DEPROC` (sem `1.2`)? | Processo enviado sem avaliação: lê as matrículas do último memo da APIS (`obter_dados_ui`) e executa a [rotina de correção](#4-rotina-de-correção-corrigir_uso_rede_propria) |
| 4 | Tem `1.3 Memo DEPROC` (sem `1.2`)? | Erro de combinação de marcadores |
| 5 | Tem `1.4` (sem `1.2`)? | Erro de combinação de marcadores |
| 6 | Há memos da GEACS na árvore? | Erro: memos sem marcador de conclusão; verificar manualmente (evita duplicidade) |
| — | (nenhuma das anteriores) | [Fluxo normal](#3-novo-fluxo-normal-processar_novo) |

**Conferência dos já avaliados** (`_tratar_novo_avaliado`):

1. Se tem `1.4`, confirma o memo de correção na árvore (pelo assunto).
   Não encontrou: erro.
2. Calcula a quantidade esperada de memos da GEACS
   (`qnt_memos_geacs_esperada`):

   | Marcador `1.3` | Memos esperados | `prox_acao` se conferir |
   |---|---|---|
   | Memos DISA e DEPROC | 2 (3 com `1.4`) | Assinar memos DISA e DEPROC e encaminhar |
   | Memo DEPROC | 1 | Assinar memo DEPROC e encaminhar |
   | nenhum | — | Erro |

3. Quantidade diferente: `prox_acao` = Verificar quantidade de memos da
   GEACS.

### 3. NOVO: fluxo normal (`processar_novo`)

Entrada: NOVO recém-classificado (➕ `1`) ou NOVO sem memos da GEACS.

1. Localiza o **último memorando da APIS-Utilização**. Não encontrou: erro.
2. Lê o texto, identifica o modelo (novo/velho) e extrai
   (`extrair_dados_ui`): nome e matrícula do titular, período do titular,
   matrículas dos dependentes e se há período variável para dependentes.
   Formato inválido: `FormatoMemorandoInvalido` e `prox_acao` = Verificar
   formato do memo da APIS.
3. `avaliar_uso`. **Todas as matrículas foram encontradas nas duas bases?**
   Não: [seção 5](#5-matrículas-não-encontradas-marcar_matriculas_nao_encontradas)
   (**➕ `1.2.1`** e/ou **➕ `1.2.2`**) e para.
4. `garantir_marcadores_no_sei` com `1.2`, o `1.3` do caso e, se for o
   caso, `1.1`. Faltou algum no SEI: erro, sem memo.
5. **Há período variável para dependentes?** Sim: **➕ `1.1`**.
6. **Alguém usou a rede própria?**
   - Sim: cria o memo DISA (quem usou e quem não usou) e insere no bloco
     `7697744`.
7. Cria o memo DEPROC (todos os beneficiários) e insere no bloco
   `7697744`.
8. **➕ `1.2`** (AVALIADO).
9. **➕ `1.3`**: `Memos DISA e DEPROC no Bloco` (alguém usou) ou
   `Memo DEPROC no Bloco` (ninguém usou).
10. Relê a árvore para obter o número SEI dos memos (falha só gera log).
11. `prox_acao` = Assinar memos DISA e DEPROC e encaminhar (ou Assinar memo
    DEPROC e encaminhar).

Se o script falhar entre os passos 6 e 9, o processo fica com `1` e com
memos da GEACS, sem marcador de conclusão. Na próxima execução ele cai na
pergunta 6 da [seção 2](#2-novo-roteamento-_tratar_novo) (erro) em vez de
duplicar os memos.

### 4. Rotina de correção (`corrigir_uso_rede_propria`)

Usada pelo `main.py` ([seção 2](#2-novo-roteamento-_tratar_novo),
pergunta 3; matrículas do último memo da APIS) e pelo script de correção
([seção 7](#7-script-de-correção-main_add_memo_nao_usou_rede_propriapy);
matrículas da planilha compilada).

Entrada: NOVO com `1.3 Memos DISA e DEPROC` e **sem** `1.2`. Todo marcador
desta rotina é adicionado com o processo **reaberto** na unidade.

1. **Tem `1.4`?** (retomada) Sim:
   1. confirma o memo de correção na árvore (não encontrou: erro);
   2. reabre o processo;
   3. **➕ `1.2`**;
   4. `prox_acao` = Assinar memo de uso da rede própria e encaminhar.
2. `avaliar_uso`. **Todas as matrículas foram encontradas?** Não: reabre o
   processo,
   [seção 5](#5-matrículas-não-encontradas-marcar_matriculas_nao_encontradas)
   (**➕ `1.2.1`** e/ou **➕ `1.2.2`**) e para.
3. **Alguém NÃO usou?** Não (todos usaram):
   1. reabre o processo;
   2. **➕ `1.2`**;
   3. `prox_acao` = Nada a fazer: todos usaram a rede própria (memo
      dispensado).
4. **O memo de correção já existe na árvore** (pelo assunto)? Sim: erro
   para verificação manual (verificar se está no bloco e adicionar os
   marcadores). Nenhum marcador é adicionado.
5. Reabre o processo.
6. `garantir_marcadores_no_sei` com `1.4` e `1.2`.
7. Cria `MemoDisaUsoRede` (quem usou e quem não usou).
8. Insere no bloco `7707212`.
9. **➕ `1.4`**.
10. **➕ `1.2`**.
11. Relê a árvore para obter o número SEI do memo (falha só gera log).
12. `prox_acao` = Assinar memo de uso da rede própria e encaminhar.

Se falhar entre os passos 9 e 10, a próxima execução entra pela retomada
(passo 1).

### 5. Matrículas não encontradas (`marcar_matriculas_nao_encontradas`)

Chamada quando `avaliar_uso` levanta `MatriculasNaoEncontradas`, com os
marcadores do ramo:

- [seção 3](#3-novo-fluxo-normal-processar_novo) e
  [seção 4](#4-rotina-de-correção-corrigir_uso_rede_propria): `1.2.1` /
  `1.2.2`;
- [seção 6](#6-velho-somente-estrutura), fluxo "Refazer relatório de UI"
  (previsto): `2.1.1` / `2.1.2`.

Passos:

1. Registra as matrículas na planilha de controle:
   - base geral: `titular_nao_encontrado_base_geral` e
     `deps_nao_encontrados_base_geral`;
   - base da rede própria: `titular_nao_encontrado` e
     `deps_nao_encontrados`.
2. `prox_acao` = Verificar matrículas não encontradas.
3. `garantir_marcadores_no_sei` com os marcadores das bases afetadas.
   Faltou algum: erro, sem memo.
4. **Faltou matrícula na base geral?** Sim:
   1. **O bloco `BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS` está configurado?**
      Não: erro, sem memo e sem marcador.
   2. **O memo à APIS já existe na árvore** (pelo assunto)?
      - Sim: retomada; não recria o memo.
      - Não: cria `MemoApisMatNaoEncontradas` e insere no bloco `7711907`.
        O memo devolve o processo à APIS para conferir as matrículas, pede
        a retificação e o reencaminhamento à GEACS-Utilização se houver
        erro e, se a matrícula estiver correta, o encaminhamento à
        IPSEMG/GEACS.
   3. **➕ `1.2.1` (NOVO) ou `2.1.1` (VELHO)**. O marcador também indica
      que o memo está no bloco.
   4. `prox_acao` = Assinar memo à APIS (matrículas não encontradas) e
      encaminhar.
5. **Faltou matrícula na base da rede própria?** Sim: **➕ `1.2.2` (NOVO)
   ou `2.1.2` (VELHO)**.
6. Se o memo foi criado, relê a árvore para obter o número SEI.
7. Quem chamou relança o erro: o processo para sem memos DISA/DEPROC e sem
   `1.2`.

As perguntas 4 e 5 podem ser verdadeiras no mesmo processo. Nas execuções
seguintes, o processo com esses marcadores gera erro e não é processado.
Para reprocessar, corrija a base e remova os marcadores manualmente no SEI.

### 6. VELHO (somente estrutura)

Entrada: processo com `2` (adicionado na classificação de uma execução
anterior).

**Roteamento** (`main._tratar_velho`):

| # | Pergunta | Se sim |
|---|---|---|
| 1 | Tem `2.1.1` ou `2.1.2`? | Erro: processo parado (`prox_acao` = Verificar matrículas não encontradas) |
| 2 | Tem `2.2 Excel Transformado em PDF`? | Stub `_tratar_tag_rel_ui_transformado_pdf`; `prox_acao` = VELHO: fluxo após conclusão |
| 3 | Tem `2.2 Relatório de UI Refeito`? | Stub `_tratar_tag_novo_rel_ui_gerado`; `prox_acao` = VELHO: fluxo após conclusão |
| 4 | Tem as duas pendências `2.1`? | Erro |
| 5 | Tem `2.1 Transformar Excel em PDF`? | Stub `_tratar_tag_transformar_excel_em_pdf`; `prox_acao` = VELHO: transformar Excel em PDF |
| 6 | Tem `2.1 Refazer Relatório de UI`? | Stub `_tratar_tag_refazer_rel_ui`; `prox_acao` = VELHO: refazer relatório de UI |
| — | (nenhuma das anteriores) | Identificação da instrução (abaixo) |

**Identificação da instrução** (`processar_velho`):

1. Localiza o e-mail de referência da APIS. Não encontrou: erro.
2. Lista **todos os memos da APIS posteriores ao e-mail**. Nenhum: erro.
3. Lê cada memo e identifica a instrução (`atualizar_pesquisa` ou
   `nova_pesquisa`) pelos padrões de texto de `_MARCADORES_INSTRUCOES`. Um
   dicionário vazio significa que a instrução ainda não foi definida e é
   ignorada.
4. **Mais de uma instrução?** Sim: erro (instruções conflitantes).
5. **Instrução `nova_pesquisa`?** Sim: **➕ `2.1 - Refazer Relatório de
   UI`**; `prox_acao` = VELHO: refazer relatório de UI.
6. **`atualizar_pesquisa` identificada, ou critérios de `nova_pesquisa`
   definidos?** Sim: **➕ `2.1 - Transformar Excel em PDF`**; `prox_acao` =
   VELHO: transformar Excel em PDF.
7. Não: **nenhum marcador**; `prox_acao` = VELHO: aguardar definição dos
   critérios das instruções. Enquanto os critérios de `nova_pesquisa`
   estiverem vazios, não dá para afirmar que o processo não tem essa
   instrução; ele é reavaliado na próxima execução.

**Fluxos previstos (não implementados; tracejados no diagrama)**:

- **Transformar Excel em PDF** (a partir de `2.1 Transformar Excel em
  PDF`): transforma o relatório de UI antigo e, ao concluir, **➕ `2.2 -
  Excel Transformado em PDF`**.
- **Refazer relatório de UI** (a partir de `2.1 Refazer Relatório de UI`):
  1. consulta à DISA e à DEPROC, igual à
     [seção 3](#3-novo-fluxo-normal-processar_novo) (`avaliar_uso` e
     memos DISA/DEPROC no bloco `7697744`);
  2. matrícula não encontrada:
     [seção 5](#5-matrículas-não-encontradas-marcar_matriculas_nao_encontradas)
     (**➕ `2.1.1`** e/ou **➕ `2.1.2`**) e para;
  3. pesquisa da utilização indevida em si (ainda não implementada);
  4. só depois da pesquisa: **➕ `2.2 - Relatório de UI Refeito`**.

**TODO**:

- critérios de texto que distinguem as duas instruções (ainda em
  avaliação pelo usuário; não invente);
- avaliação da rede própria dentro do fluxo VELHO;
- download das planilhas antigas;
- implementar `_tratar_tag_transformar_excel_em_pdf` e
  `_tratar_tag_refazer_rel_ui` em `main.py`;
- fluxo completo da pesquisa da utilização indevida, que é quem insere
  `2.2 - Relatório de UI Refeito`.

### 7. Script de correção (`main_add_memo_nao_usou_rede_propria.py`)

Objetivo: corrigir os processos NOVOS que foram encaminhados à DISA e à
DEPROC **sem** avaliação do uso da rede própria.

**Início**

1. Lê
   `dados/controle/main/_processos_processados-COMPILADO-2026_09_23.xlsx`
   (aba `FINAL`, colunas `num_processo`, `matricula_titular` e
   `matriculas_dependentes`).
2. Carrega a base da rede própria e a base geral.
3. Faz login no SEI.

**Triagem de cada processo** (`_avaliar_processo`). Os marcadores são
lidos **do SEI**, não da planilha. A triagem não adiciona marcadores; só a
rotina de correção adiciona.

| # | Pergunta | Se sim |
|---|---|---|
| 1 | **Não** tem `1` (NOVO)? | Tem `2`: fora do escopo. Tem `MANUAL` ou `ASSINADO`: fora do escopo (tratado manualmente). Nenhum dos dois: erro (nem NOVO nem VELHO) |
| 2 | Tem `1.2.1` ou `1.2.2`? | Erro: processo parado |
| 3 | Tem `1.2` (AVALIADO)? | Com `1.4`: lista a árvore e confere o memo de correção (`prox_acao` = Assinar memo de uso da rede própria e encaminhar). Sem `1.4`: Nada a fazer |
| 4 | **Não** tem `1.3 Memos DISA e DEPROC`? | Fora do escopo (não se enquadra) |
| — | (nenhuma das anteriores) | Lista a árvore e executa a [rotina de correção](#4-rotina-de-correção-corrigir_uso_rede_propria) com as matrículas da planilha |

**Fim**: salva a planilha de controle e o resumo no log
([Saídas](#saídas)).

---

## Saídas

### Script principal

- `dados/controle/processos_processados_<data>.xlsx`, uma linha por
  processo, gerada por `RegistroMain.to_dict()` e gravada por
  `salvar_planilha_controle`.
  - **Não renomeie as colunas existentes**: a compilação dessas planilhas
    alimenta o script de correção.
  - Primeiras colunas: `num_processo`, `data_execucao` (identifica a
    execução no compilado), `fluxo`, `prox_acao`, `tipo_erro`, `erro`.
  - Rastreabilidade: `memo_apis_sei`, `modelo_memo_apis`,
    `memo_disa_sei`, `memo_deproc_sei`, `memo_uso_rede_sei`,
    `marcadores_sei` (lidos no início) e `marcadores_adicionados`.
  - `tem_periodo_var_deps` (sim/não) e `periodo_dependentes` (só as
    datas, modelo velho). Até 2026-09-25, `periodo_dependentes` também
    trazia `True/False` do modelo novo.
  - `qnt_memos_geacs_esperada`: preenchida na conferência dos NOVOS já
    avaliados.
  - Matrículas não encontradas: colunas da
    [seção 5](#5-matrículas-não-encontradas-marcar_matriculas_nao_encontradas)
    (nos dois scripts).
  - Formatação: cabeçalho congelado e com filtro; linha com erro em
    vermelho claro; matrículas não encontradas em amarelo. Se a formatação
    falhar, a planilha fica salva sem ela.
  - O número SEI dos memos criados é obtido relendo a árvore **depois**
    dos marcadores; uma falha nessa leitura só gera log e não afeta o
    processo.
- Log em `logs/<data>_execucao.log`, com resumo final.

### Script de correção

- `dados/controle/main_add_memo_nao_usou_rede_propria/<data>_processos_add_memo_nao_uso_rede_propria.xlsx`
- Log em `logs/main_add_memo_nao_usou_rede_propria/`, com resumo final.

---

## Pontos a validar no ambiente real

- Confirmar que `obter_conteudo_doc` devolve a linha de **assunto** do memo.
  A busca do memo de correção depende disso.
- Confirmar que `incluir_doc_sei_memo` funciona com um documento
  selecionado na árvore.
- Confirmar que `listar_documentos_arvore` logo após criar os memos traz
  os memos novos no fim da árvore, na ordem de criação (DISA antes de
  DEPROC). Os números SEI dos memos dependem disso.
- Confirmar que a leitura da lista de marcadores ("Gerenciar Marcador",
  opções `#selMarcador label.dd-option-text`) traz todos os marcadores da
  unidade e sai da tela sem salvar.
- Processos que já receberam `1.2.1` antes da criação do memo à APIS
  (até 2026-09-25) não têm o memo. Para gerá-lo, remova manualmente o
  `1.2.1` (e o `1.2.2`) e rode de novo.
- A planilha de controle tem nomes e matrículas (LGPD). Restrinja o
  acesso à pasta `dados/controle`.
- Processos antigos com 2 memos da GEACS e **sem** o marcador de memos no
  bloco aparecem como erro. Se forem casos de correção, adicione
  manualmente `Memos DISA e DEPROC no bloco` e rode de novo.
- Os logs contêm matrículas, que são dados pessoais (LGPD). Restrinja o
  acesso à pasta `logs`.
