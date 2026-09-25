# Script SEI - Utilização Indevida (v2)

Automação Selenium no SEI-MG (IPSEMG) que prepara a apuração de utilização
indevida da assistência à saúde:

- classifica os processos;
- extrai as instruções dos memorandos da APIS;
- avalia o uso da rede própria;
- gera os memorandos para DISA e DEPROC.

A pesquisa da utilização indevida em si **ainda não foi implementada**.

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
| `docs_processo.py` | Filtros da árvore e busca do memo de correção pelo assunto |
| `extrator_dados_ui.py` | Extrai as instruções do texto do memo da APIS (modelos "novo" e "velho") |
| `matriculas_nao_encontradas.py` | Registra as matrículas não encontradas e adiciona o marcador de cada base (NOVO ou VELHO) |
| `tags.py` | Todos os marcadores, `registrar_tags()` e `adicionar_tag()` |
| `constantes.py` | Unidades, blocos, signatária, caminhos fixos |
| `log_config.py` | Logging compartilhado: processo atual em cada linha e resumo final |
| `Registro.py` | Um registro por processo (uma linha da planilha de controle), `ProxAcao` e `registrar_erro()` |
| `planilha_controle.py` | Grava e formata a planilha de controle (usado pelos dois scripts) |
| `memorandos/` | `DadosUI`, `MemoDisa`, `MemoDeproc`, `MemoDisaUsoRede` |

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
- `prox_acao`: use os valores de `Registro.ProxAcao`. Não escreva textos
  soltos; detalhes vão para as demais colunas e para o log.
- Erros: registre com `Registro.registrar_erro(registro, e)` (preenche
  `tipo_erro`, `erro` e, se preciso, `prox_acao = Verificar erro`).

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
- Matrícula (titular ou dependente) **não encontrada na base geral ou na
  base da rede própria para o processamento do processo**:
  - `avaliar_uso` busca nas **duas** bases antes de parar e levanta
    `MatriculasNaoEncontradas` (subclasse de `ErroAvaliacao`) com o
    resultado de cada base;
  - quem chamou adiciona, via `marcar_matriculas_nao_encontradas`, o
    marcador de cada base com ausência, sem criar memos nem adicionar
    AVALIADO:
    - base geral: `1.2.1` (NOVO) ou `2.1.1` (VELHO);
    - base da rede própria: `1.2.2` (NOVO) ou `2.1.2` (VELHO);
  - colunas da planilha de controle (nos dois scripts):
    - base geral: `titular_nao_encontrado_base_geral` e
      `deps_nao_encontrados_base_geral`;
    - base da rede própria: `titular_nao_encontrado` e
      `deps_nao_encontrados`;
  - nas execuções seguintes, o processo com esse marcador gera erro e não
    é processado. Para reprocessar, corrija a base e remova os marcadores
    manualmente no SEI.
  - Os demais processos continuam normalmente.
- São `ErroAvaliacao`:
  - resposta inválida (nem SIM nem NÃO);
  - dependentes citados sem matrícula explícita (`AVERIGUAR`, modelo
    velho).
- Os períodos **não** são usados na consulta de rede própria. Eles só são
  compilados na planilha de controle para a consulta final.

### Marcadores (`tags.py`)

| Marcador | Significado |
|---|---|
| `Script v2 - 1 - Processo NOVO` | Classificação: NOVO |
| `Script v2 - 1.1 - Período Variável p/ Dependentes` | Memo da APIS tem período específico para dependentes |
| `Script v2 - 1.2 - Avaliado Se Usou Rede Própria` | Uso da rede própria avaliado |
| `Script v2 - 1.2.1 - Mat. N Encontradas Base Geral` | NOVO parado: matrícula não encontrada na base geral |
| `Script v2 - 1.2.2 - Mat. N Encontradas Base DISA` | NOVO parado: matrícula não encontrada na base da rede própria |
| `Script v2 - 1.3 - Memos DISA e DEPROC no Bloco` | Alguém usou; os dois memos estão no bloco |
| `Script v2 - 1.3 - Memo DEPROC no Bloco` | Ninguém usou; só a DEPROC foi acionada |
| `Script v2 - 1.4 - Memo Não Usou Rede no Bloco` | Memo de correção no bloco (na correção, inserido antes do 1.2) |
| `Script v2 - 2 - Processo VELHO` | Classificação: VELHO |
| `Script v2 - 2.1 - Transformar Excel em PDF` | VELHO sem instrução de nova pesquisa (fluxo não implementado) |
| `Script v2 - 2.1 - Refazer Relatório de UI` | VELHO com instrução de nova pesquisa (fluxo não implementado) |
| `Script v2 - 2.1.1 - Mat. N Encontradas Base Geral` | VELHO parado: matrícula não encontrada na base geral |
| `Script v2 - 2.1.2 - Mat. N Encontradas Base DISA` | VELHO parado: matrícula não encontrada na base da rede própria |
| `Script v2 - 2.2 - Excel Transformado em PDF` | Conclusão do 2.1 "Transformar Excel em PDF" |
| `Script v2 - 2.2 - Relatório de UI Refeito` | Conclusão do 2.1 "Refazer Relatório de UI" |
| `PLANILHADO`, `UTILIZAÇÃO INSERIDA` | Manuais; não interferem na classificação |

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
- Blocos de assinatura:
  - `7697744`: memos DISA e DEPROC do fluxo normal;
  - `7707212`: memo de correção.
- Signatária: Bruna Miiller Lavarini, Gerência de Auditoria e Contas da
  Saúde.

---

## 1. Script principal (`main.py`)

### Início

1. Lê `dados/inputs/processos_nao_processados.xlsx` (aba
   `processos_reais`, coluna `num_sei`).
2. Carrega a planilha de rede própria e a base geral.
3. Faz login no SEI e percorre os processos um a um.

### Leitura de cada processo

- Abre o processo e lista a árvore.
- Conta documentos e memorandos da GEACS.
- Lê os marcadores **do SEI**.

### Classificação (`_classificar_e_processar`)

- NOVO e VELHO ao mesmo tempo: erro.
- VELHO: `_tratar_velho`.
- NOVO: `_tratar_novo`.
- Marcadores do script sem NOVO/VELHO: erro.
- Sem marcadores do script (`_tratar_sem_marcadores`):
  - com documento da GEACS: adiciona VELHO e termina com a próxima ação
    "Processar processos VELHOS";
  - sem documento da GEACS: adiciona NOVO e segue para `processar_novo`.

### NOVO: fluxo normal (`processar_novo`)

1. Lê o **último memorando da APIS**.
2. `extrair_dados_ui` obtém:
   - nome e matrícula do titular;
   - período do titular;
   - matrículas dos dependentes;
   - se há período variável para dependentes.
3. `avaliar_uso` busca as matrículas na base geral e na planilha de rede
   própria. Se alguma não for encontrada, adiciona `1.2.1` e/ou `1.2.2` e
   para.
4. Se há período variável para dependentes, adiciona o marcador de período
   variável.
5. Cria os memos no bloco `7697744`:
   - alguém usou: memo DISA (lista quem usou e quem não usou) e memo DEPROC
     (todos);
   - ninguém usou: só o memo DEPROC.
6. Adiciona AVALIADO e depois `Memos DISA e DEPROC no bloco` ou
   `Memo DEPROC no bloco`.

### NOVO já tratado (`_tratar_novo`)

- **Com `1.2.1` ou `1.2.2` (matrículas não encontradas)**: erro; o
  processo fica parado até a remoção manual do marcador.
- **Com AVALIADO** (`_tratar_novo_avaliado`): confere a quantidade de
  memorandos da GEACS.

  | Situação | Memos esperados |
  |---|---|
  | DISA e DEPROC | 2 |
  | DISA, DEPROC e memo de correção | 3 |
  | Só DEPROC | 1 |

  - Se houver o marcador de memo de correção, confirma o memo na árvore.
  - Se a quantidade não bater, a próxima ação é "Verificar".
- **Com `Memos DISA e DEPROC no bloco` e sem AVALIADO**: é processo afetado
  pelo erro. Extrai as matrículas do memo da APIS e executa a **rotina de
  correção** (seção 2).
- **Com `Memo DEPROC no bloco` ou memo de correção, sem AVALIADO**: erro de
  combinação de marcadores.
- **Sem memos da GEACS**: fluxo normal.
- **Com memos da GEACS e sem marcador de conclusão**: erro para verificação
  manual (evita duplicidade).

### VELHO (`processar_velho`, somente estrutura)

- Localiza o e-mail de referência da APIS.
- Lê **todos os memos da APIS posteriores ao e-mail**.
- Identifica a instrução: `atualizar_pesquisa` ou `nova_pesquisa`.
- Os marcadores de texto de cada instrução ficam em `_MARCADORES_INSTRUCOES`.
  Um dicionário vazio significa que a instrução ainda não foi definida e é
  ignorada.

#### Fluxo por instrução

Por enquanto o script **só adiciona o marcador da pendência**. Os fluxos
em si ainda não foram implementados.

- **Sem instrução de nova pesquisa** (`atualizar_pesquisa` ou nenhuma
  instrução): adiciona `TAG_TRANSFORMAR_EXCEL_EM_PDF` ('Script v2 -
  2.1 - Transformar Excel em PDF').
  - Enquanto os critérios de `nova_pesquisa` estiverem vazios, um processo
    **sem nenhuma instrução identificada não recebe marcador**: não dá
    para afirmar que ele não tem a instrução de nova pesquisa. Ele é
    reavaliado na próxima execução.
- **Com instrução de nova pesquisa** (`nova_pesquisa`): adiciona
  `TAG_REFAZER_REL_UI` ('Script v2 - 2.1 - Refazer Relatório de UI').
- Instruções conflitantes: erro.
- Na execução seguinte, `_tratar_velho` encaminha pelo marcador:
  - `2.1.1` ou `2.1.2` (matrículas não encontradas): erro (processo parado);
  - `TAG_REL_UI_TRANSFORMADO_PDF` / `TAG_NOVO_REL_UI_GERADO` (conclusão)
    têm prioridade;
  - depois `_tratar_tag_transformar_excel_em_pdf` ou
    `_tratar_tag_refazer_rel_ui` (stubs);
  - os dois marcadores de pendência juntos: erro.

Fluxos previstos (não implementados):

- **Transformar Excel em PDF**: transforma o relatório de UI antigo e, ao
  concluir, adiciona `TAG_REL_UI_TRANSFORMADO_PDF` ('Script v2 - 2.2 -
  Excel Transformado em PDF').
- **Refazer relatório de UI**: executa primeiro o fluxo de consulta à
  DISA e à DEPROC — o mesmo da Seção 1 (`avaliar_uso` e criação dos memos
  DISA/DEPROC no bloco `7697744`). Matrícula não encontrada: marcadores
  `2.1.1`/`2.1.2` e processamento parado (ver regras das bases).
  - `TAG_NOVO_REL_UI_GERADO` ('Script v2 - 2.2 - Relatório de UI Refeito') só é
    inserida depois que a pesquisa da utilização indevida em si for
    realizada — fluxo **ainda não implementado** (ver introdução).

- **TODO**:
  - critérios de texto que distinguem as duas instruções (ainda em
    avaliação pelo usuário; não invente);
  - avaliação da rede própria dentro do fluxo VELHO;
  - download das planilhas antigas;
  - implementar `_tratar_tag_transformar_excel_em_pdf` e
    `_tratar_tag_refazer_rel_ui` em `main.py`;
  - fluxo completo da pesquisa da utilização indevida, que é quem insere
    `TAG_NOVO_REL_UI_GERADO`.

### Saídas

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
  - Formatação: cabeçalho congelado e com filtro; linha com erro em
    vermelho claro; matrículas não encontradas em amarelo. Se a formatação
    falhar, a planilha fica salva sem ela.
  - O número SEI dos memos criados é obtido relendo a árvore **depois**
    dos marcadores; uma falha nessa leitura só gera log e não afeta o
    processo.
- Log em `logs/<data>_execucao.log`, com resumo final.

---

## 2. Script de correção (`main_add_memo_nao_usou_rede_propria.py`)

### Objetivo

Corrigir os processos NOVOS que foram encaminhados à DISA e à DEPROC **sem**
avaliação do uso da rede própria.

### Início

1. Lê
   `dados/controle/main/_processos_processados-COMPILADO-2026_09_23.xlsx`
   (aba `FINAL`, colunas `num_processo`, `matricula_titular` e
   `matriculas_dependentes`).
2. Carrega a planilha de rede própria e a base geral.
3. Faz login no SEI e percorre os processos um a um.

### Triagem (`_avaliar_processo`)

Os marcadores são lidos **do SEI**, não da planilha.

| Situação | Ação |
|---|---|
| VELHO | Fora do escopo |
| Nem NOVO nem VELHO | Erro |
| NOVO com `1.2.1` ou `1.2.2` (matrículas não encontradas) | Erro (processo parado) |
| AVALIADO e com memo de correção | Confere o memo na árvore |
| AVALIADO e sem memo de correção | Nada a fazer |
| NOVO sem `Memos DISA e DEPROC no bloco` | Não se enquadra |
| NOVO com `Memos DISA e DEPROC no bloco` e sem AVALIADO | Rotina de correção |

### Rotina de correção (`corrigir_uso_rede_propria`, também usada pelo `main.py`)

1. **Retomada**: se já existe o marcador de memo de correção, confirma o
   memo na árvore, reabre o processo, adiciona AVALIADO e encerra.
2. `avaliar_uso`. Se alguma matrícula não for encontrada: reabre o
   processo, adiciona `1.2.1` e/ou `1.2.2` e para.
3. Se **todos usaram**: reabre o processo e adiciona AVALIADO. O memo é
   dispensado.
4. Se **alguém não usou**:
   1. Procura o memo de correção pelo assunto. Se ele existir sem os
      marcadores, é `ErroAvaliacao` para verificação manual.
   2. Reabre o processo.
   3. Cria `MemoDisaUsoRede` (quem usou e quem não usou).
   4. Insere no bloco `7707212`.
   5. Adiciona o marcador de memo de correção.
   6. Adiciona AVALIADO.

### Saídas

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
- A planilha de controle tem nomes e matrículas (LGPD). Restrinja o
  acesso à pasta `dados/controle`.
- Processos antigos com 2 memos da GEACS e **sem** o marcador de memos no
  bloco aparecem como erro. Se forem casos de correção, adicione
  manualmente `Memos DISA e DEPROC no bloco` e rode de novo.
- Os logs contêm matrículas, que são dados pessoais (LGPD). Restrinja o
  acesso à pasta `logs`.