# Script SEI - Utilização Indevida (v2)

Automação Selenium no SEI-MG (IPSEMG) que prepara a apuração de utilização
indevida da assistência à saúde:

- separa os processos VELHOS (não processados; fluxo a definir);
- lê o último memorando da APIS destinado à GEACS;
- confere as matrículas na base APIS e compara o uso da rede própria na
  base DISA e no MANTIS;
- gera o memorando à DISA (um por caso da comparação, com os relatórios do
  MANTIS em PDF) **ou** o memorando à DEPROC.

A pesquisa da utilização indevida em si **ainda não foi implementada**.

O fluxo está descrito na seção [Fluxo do processo](#fluxo-do-processo) e
desenhado em [`docs/fluxo.drawio`](docs/fluxo.drawio) (uma aba, gerada por
[`docs/gerar_fluxo.py`](docs/gerar_fluxo.py)). O
`docs/fluxo_com_comments.drawio` é da versão anterior do fluxo.

## Glossário

- **APIS-Utilização**: unidade que envia as instruções. O memorando traz
  titular, dependentes e períodos. A APIS pede sempre para refazer
  (atualizar) a consulta, mesmo em processo que já tem documento da GEACS.
- **GEACS-Utilização**: nossa unidade. Emite os memorandos.
- **DISA**: valida os atendimentos na rede própria e levanta os dela.
- **DEPROC**: levanta a coparticipação. Recebe todos os beneficiários e o
  relatório da rede credenciada, **só** quando ninguém usou a rede própria
  (base DISA e MANTIS). Processo enviado à DISA não vai para a DEPROC.
- **Base APIS**: listagem de todos os beneficiários da demanda. É nela que
  se confere se as matrículas existem. (Antes chamada de "base geral"; as
  colunas da planilha de controle mantêm o nome antigo.)
- **Base DISA**: planilha, feita a partir da base APIS, que diz apenas se o
  beneficiário teve atendimento na rede própria (sem os atendimentos).
- **MANTIS**: atendimentos detalhados (rede própria e rede credenciada).
- **RP / RC**: rede própria / rede credenciada.
- **Processo VELHO**: processo enviado à DISA e à DEPROC **antes** da
  avaliação da rede própria. Identificado pelo marcador `0 - Processo
  VELHO`, pelo `1.3 - Memos DISA e DEPROC no Bloco` (versão anterior) ou
  pelos memos da GEACS ([regra](#processo-velho)). **Não é processado**
  (TODO: fluxo próprio). Todos os outros são tratados como NOVOS, inclusive
  os que já têm documento da GEACS.
- **Rodada**: documentos depois do último memorando da APIS destinado à
  GEACS (`registro.docs_rodada`). Memos e relatórios já criados só são
  procurados nela, para não confundir com os de pedidos anteriores.
- **Marcador (tag)**: marcador do SEI. É a memória do sistema entre
  execuções: registra o que foi feito e permite retomar o trabalho.

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Script principal: separação do VELHO (`_separar_velho`) e roteamento pelos marcadores (`_tratar`). Não roda enquanto a `sei_automacao` não tiver `remover_marcador` |
| `processar_novo.py` | Fluxo dos processos não VELHOS (com retomada pelo marcador de estado); `obter_dados_ui()` lê o último memo da APIS destinado à GEACS; `_avaliar_mantis_e_criar_docs()` compara base DISA × MANTIS e escolhe o memo |
| `relatorios_mantis.py` | `incluir_relatorios()`: gera os PDFs do MANTIS (titular e dependentes) e os anexa como documento externo, com retomada pelo nome na árvore |
| `transformar_xls_em_pdf.py` | Monta o PDF do relatório de utilização (ReportLab) |
| `memos_sei.py` | `incluir_memo()` (procura o memo pelo assunto na rodada, ou cria e insere no bloco) e `registrar_numeros_memos()` (número SEI dos memos criados) |
| `sessao_sei.py` | `abrir_sei()`: navegador e login (credenciais do `.env`) |
| `rede_propria.py` | Carga da base DISA e da base APIS, normalização de matrícula, `verificar_base_apis()` (existência), `avaliar_uso_rede_propria_disa()` (uso), `ErroAvaliacao` |
| `mantis.py` | Carga das bases do MANTIS (rede própria e credenciada, com os atendimentos), interpretação do período de apuração, `avaliar_uso_rede_propria_mantis()` e `usos_mantis_alem_disa()` |
| `docs_processo.py` | Filtros da árvore, memos da APIS destinados à GEACS, busca de memos da GEACS pelo assunto e de documentos pelo nome, `encontrar_memos_velho()` (memos DISA → DEPROC antigos) |
| `extrator_dados_ui.py` | Extrai as instruções do texto do memo da APIS (só o modelo "novo_novo"; os outros são formato inválido) |
| `matriculas_nao_encontradas.py` | Memo à APIS de matrículas não encontradas na base APIS (`incluir_memo_apis_mat_nao_encontradas`) |
| `tags.py` | Todos os marcadores, grupos de estado e pares, `registrar_tags()`, `adicionar_tag()` (troca o estado ou o par), `adicionar_tag_se_ausente()`, `remover_tag()`, `tem_tag()`, `estado_atual()`, `eh_velho_pelos_marcadores()`, `conferir_marcadores()` e o placeholder de `remover_marcador` |
| `marcadores_disponiveis.py` | `garantir_marcadores_no_sei()`: confere, antes de criar memos, se os marcadores existem no SEI |
| `constantes.py` | Unidades, blocos, signatária, caminhos fixos, data de corte do VELHO |
| `log_config.py` | Logging: processo atual em cada linha e resumo final |
| `Registro.py` | Uma passagem de um processo (`RegistroBase`, `RegistroMain`): árvore, rodada, marcadores e resultado; `ProxAcao` e `registrar_erro()` |
| `planilha_controle.py` | `PlanilhaControleGeral`: atualiza e formata a planilha de controle geral a cada processo, com backup |
| `memorandos/` | `DadosUI`, `UsoRede` (`UsoRedeBeneficiarios`), `MemoDisa` (`MemoDisaValidarConsta`, `MemoDisaValidarNaoConsta`, `MemoDisaRelatorio`), `MemoDeproc`, `MemoApisMatNaoEncontradas`, `MemoApisSemMemo`, `MemoApisFormatoInvalido`, `MemoApisPeriodoDependentes` (ver `TextoPendente`) |
| `main_pdf_unico.py` | Utilitário avulso: gera um PDF a partir de um Excel |
| `docs/gerar_fluxo.py` | Gera o `docs/fluxo.drawio` (`python docs/gerar_fluxo.py docs/fluxo.drawio`). O conteúdo do diagrama fica no script |
| `tests/` | Testes (`poetry run task test`). `sei_falso.py` simula o SEI em memória (árvore, textos, marcadores e PDFs); `test_fluxo_novo.py` roda o `main.py` em várias passagens |

A biblioteca `sei_automacao` é externa (login, árvore, marcadores,
memorandos, documento externo, blocos). Não altere a biblioteca; use apenas
a API dela.

## Convenções

- Python 3.10+ (`str | None`, `zip(strict=True)`).
- Código, nomes e mensagens em português.
- Aspas simples.
- Lint com **ruff** (preview ativo, ex.: PLR6301).
- Testes com **pytest** (`poetry run task test`). O main não tem efeito
  colateral ao importar (logging e pastas são configurados em `main()`).
  Ao mudar o fluxo, ajuste ou acrescente o cenário em
  `tests/test_fluxo_novo.py`.
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
    `FormatoMemorandoInvalido`; é logado sem traceback (`TextoMemoPendente`
    também);
  - falha inesperada: logada com `logger.exception`.
- Um erro em um processo **nunca** interrompe os demais.
- Logs:
  - use `logging.getLogger(__name__)`;
  - não prefixe o número do processo na mensagem, pois
    `contexto_processo` já o injeta;
  - toda ação no SEI (memo criado, relatório anexado, bloco, marcador)
    gera um `logger.info`.
- O registro é o contexto do processo: guarda a árvore (`tds_docs`,
  `docs_geacs`, `memos_geacs`, via `registro.registrar_arvore`), a rodada
  (`docs_rodada`, definida em `obter_dados_ui`) e os marcadores
  (`marcadores_sei`, lidos no início, e `marcadores_atuais`). As funções
  recebem `(driver, registro)` e, quando precisam, as bases. Campos de
  trabalho ficam em `_CAMPOS_INTERNOS` e não vão para a planilha.
- Marcadores: adicione **sempre** com `tags.adicionar_tag(driver, registro,
  tag)` (ou `adicionar_tag_se_ausente`, na retomada), que também preenche
  `marcadores_adicionados` e, se o marcador for de estado ou de um par base
  DISA/MANTIS, remove o anterior do grupo (`marcadores_removidos`).
  Consulte com `tem_tag`/`estado_atual` (marcadores atuais). Não chame
  `adicionar_marcador`/`remover_marcador` direto.
- **Antes de criar qualquer memo ou relatório**, chame
  `garantir_marcadores_no_sei(driver, [marcadores que serão adicionados])`.
  Se um nome não existir no SEI, o processo para antes (senão o memo fica
  no bloco sem marcador). A lista é lida na tela "Gerenciar Marcador", sem
  salvar, uma vez por execução; se faltar um nome, é relida uma vez.
- `prox_acao`: use os valores de `Registro.ProxAcao`. Não escreva textos
  soltos; detalhes vão para as demais colunas e para o log. Toda
  `prox_acao` de fluxo (parada, conclusão, VELHO) tem um marcador; as de
  erro (`Verificar erro`, `Verificar marcadores inconsistentes`) ficam só na
  planilha.
- Erros: registre com `Registro.registrar_erro(registro, e)` (preenche
  `tipo_erro`, `erro` e, se preciso, `prox_acao = Verificar erro`). A
  coluna `erro` recebe só uma frase; erros do Selenium sem mensagem viram
  "Tempo esgotado esperando elemento do SEI em <função>". O traceback
  completo fica no log.
- Ao mudar o fluxo (pergunta, ação, marcador ou `prox_acao`), atualize a
  seção [Fluxo do processo](#fluxo-do-processo) **e** o conteúdo em
  `docs/gerar_fluxo.py`, e regere o `docs/fluxo.drawio` (não edite o
  `.drawio` à mão: a próxima geração sobrescreve). No diagrama, os nomes
  dos marcadores vão sempre inteiros (sem o prefixo `Script v2 - `).

## Regras de negócio

### Processo VELHO

- É VELHO o processo com o marcador `0 - Processo VELHO` ou `1.3 - Memos
  DISA e DEPROC no Bloco` (versão anterior), ou cujos memorandos da GEACS
  (toda a árvore, não só a rodada) tenham **dois seguidos** (entre os
  memorandos da GEACS): um com "Para: IPSEMG/DISA-UTI-INDEV" e o seguinte
  com "Para: IPSEMG/DEPROC", **os dois datados antes de 01/10/2026**
  (`DATA_CORTE_PROCESSO_VELHO`). A data é a linha "Belo Horizonte, 18 de
  setembro de 2026." (espaços e maiúsculas são ignorados).
- Par encontrado sem data legível: `ErroAvaliacao`, sem ação no SEI (não dá
  para saber se é VELHO).
- O VELHO recebe `0 - Processo VELHO` e **não é processado**
  (`prox_acao` = VELHO: não processado). Com `MANUAL` ou `ASSINADO`: fora do
  escopo, sem marcador.
- **TODO**: definir o fluxo do VELHO. Todos os processos com `0` (ou com o
  `1.3`) e os identificados na execução devem passar por ele
  (`main._separar_velho`).
- A busca nos memos é feita antes de qualquer ação, em todo processo que
  ainda vai para `processar_novo` (sem estado ou em retomada).

### Memo da APIS

- Vale o **último** memorando da APIS-Utilização destinado à GEACS (na
  ordem da árvore); os anteriores são ignorados.
- Destinado à GEACS: o texto contém algum dos trechos de
  `TRECHOS_DESTINO_GEACS` ("Solicita-se à Gerência de Auditoria e Contas da
  Saúde - GEACS", "Para: Bruna Miller Lavarini" ou "Para: Bruna Miiller
  Lavarini"; espaços e maiúsculas são ignorados).
- Só o modelo **novo_novo** é válido (exemplo: Memorando
  IPSEMG/APIS-UTILIZAÇÃO nº 2627/2026). Ele tem os campos `Nome completo`,
  `Matrícula`, `Período de apuração do titular` e `Matrícula dos
  dependentes` **e** o pedido de "atualização do levantamento de
  utilização". Sem esse pedido é o modelo novo_velho; com "Segurado(a)", o
  velho. Os dois são formato inválido.
- Matrícula do titular com DV separado por barra (`1289612 / 8`) é aceita.
- Período: `(01/05/2019 a 31/12/2019) e (01/02/2020 a 12/06/2024)` e os
  formatos de [MANTIS](#bases-de-matrículas).

### Bases de matrículas

- **Base APIS** (listagem de todos os beneficiários):
  `planilha_da_galantini_com_listagem_de_todos_beneficiarios.xlsx`, abas
  `UI 2025 EX-TITULARES` (coluna `MATRICULAS TITULARES`, cabeçalho com
  espaço sobrando) e `UI 2025 EX-DEPENDENTES` (coluna
  `MATRICULAS DEPENDENTES`). **Todas as matrículas têm DV.** A existência
  das matrículas é conferida **só nela**: faltou alguma, o processo para com
  `1.2.1` e memo à APIS.
- **Base DISA (rede própria)**, feita a partir da base APIS:
  `beneficiarios_atendidos_rede_propria-2026_09_23.xlsx`, abas
  `UI 2025 EX-TITULARES` (coluna `MATRICULAS TITULARES`) e
  `UI 2025 EX-DEPENDENTES` (coluna `MATRICULAS DEPENDENTES - SEM DV`), com
  a resposta em `UTILIZOU A REDE PRÓPRIA?`. Diz só se houve atendimento.
  Matrícula fora dela conta como **não usou** (sem marcador; o `1.2.2` é da
  versão anterior).
- Nos processos, o **titular vem com DV** e os **dependentes vêm sem DV**.
  O DV é o último dígito: ele é retirado dos dependentes da base APIS na
  carga.
- Matrícula normalizada: sem hífen, ponto, barra ou espaço e sem zeros à
  esquerda.
- Matrícula repetida na base DISA: um SIM prevalece. Resposta inválida
  prevalece sobre NÃO; resposta inválida de matrícula consultada é
  `ErroAvaliacao`.
- Os períodos **não** são usados na consulta da base DISA, só na do
  MANTIS.
- **Bases do MANTIS**: `utilizacao_MANTIS-rede_propria.xlsx` e
  `utilizacao_MANTIS-rede_credenciada.xlsx`, uma linha por item atendido:
  - aba `TITULARES`, matrícula em `MATRICULA_TITULAR`;
  - aba `DEPENDENTES`, matrícula em `MATRICULA_DEPENDENTE` (e
    `NOME_DEPENDENTE`);
  - nas duas: `DATA_DO_ATENDIMENTO` (data ou número de série do Excel),
    `VALOR_A_PAGAR`, `NOME_PRESTADOR` e `PROCEDIMENTO`.
  - Conta como uso o atendimento com data dentro do **período de apuração
    do titular** (vale para os dependentes, pois o processo com período
    variável para antes do MANTIS). Titular e dependentes são avaliados.
  - Formatos de período aceitos: `01/08/2023 a 12/06/2024`,
    `09/2023 a 06/2024` e `02 a 06/2024`, com vários intervalos (entre
    parênteses ou não). Qualquer outro número no texto, data inválida ou
    início depois do fim: `ErroAvaliacao`.
  - Atendimento sem data válida de uma matrícula consultada:
    `ErroAvaliacao`. Sem valor: conta como 0.
  - **TODO**: confirmar o DV. Assume-se titular **sem DV**
    (`TITULAR_MANTIS_COM_DV = False`) e dependentes sem DV
    (`DEPENDENTE_MANTIS_COM_DV = False`).

### Decisão base DISA × MANTIS

Pelo **processo inteiro**: DISA = alguém tem SIM na base DISA; MANTIS =
alguém tem atendimento na rede própria do MANTIS no período. Cada base tem
um par de marcadores (`1.6.2` e `1.8.2`, "Usou RP" / "Não Usou RP").

| Base DISA | MANTIS (RP) | Ação | Memo (bloco) | Marcador |
|---|---|---|---|---|
| sim | sim | Relatórios RP em PDF + memo à DISA para **validar e complementar** com os dados dela | `MemoDisaValidarConsta` (`BLOCO_MEMO_DISA_VALIDAR_CONSTA`) | `1.9 - Aguarda DISA: Validar (Consta)` |
| não | sim | Relatórios RP em PDF + memo à DISA para **validar**, informando que não consta na planilha | `MemoDisaValidarNaoConsta` (`BLOCO_MEMO_DISA_VALIDAR_NAO_CONSTA`) | `1.9 - Aguarda DISA: Validar (N Consta)` |
| sim | não | Memo à DISA pedindo o **relatório** com os dados dela (sem PDF) | `MemoDisaRelatorio` (`BLOCO_MEMO_DISA_RELATORIO`) | `1.9 - Aguarda DISA: Relatório` |
| não | não | Relatórios RC em PDF (só de quem usou) + memo DEPROC | `MemoDeproc` (`7697744`) | `1.10 - Concluído: Memo DEPROC` |

- Processo enviado à DISA **não** vai para a DEPROC: nem memo DEPROC nem
  relatório RC. O memo à DISA é uma **parada** (aguarda o retorno da DISA).
- No memo "validar e complementar", cada beneficiário com uso no MANTIS vem
  com "consta"/"NÃO consta na planilha"; quem consta na base DISA sem uso
  no MANTIS vem num parágrafo à parte.
- A coluna `mats_uso_mantis_alem_disa` lista quem usou no MANTIS e não
  consta na base DISA; `caso_disa_mantis` diz o caso
  ("DISA sim, MANTIS não").

### Relatórios em PDF (`relatorios_mantis.py`)

- Um PDF para o titular (prestador, data, procedimento, valor) e um para os
  dependentes (prestador, matrícula e nome do dependente, data, valor), só
  de quem tem atendimento.
- Documento externo: tipo `PDF`, número `Utilização <Tit.|Dep.> <RP|RC> -
  <matrícula do titular> - <AAAAMMDD_HHMMSS>`, Nato-digital, data de hoje,
  Restrito, Informação Pessoal. O SEI limita o nome a 50 caracteres (há
  teste).
- Arquivos em `dados/utilizacoes/mantis/pdf/` (sobrescritos a cada
  geração).
- Retomada: se a rodada já tem um documento que começa com
  `PDF Utilização <Tit.|Dep.> <RP|RC> - <matrícula>`, ele não é anexado de
  novo.

### Marcadores (`tags.py`)

Prefixo de todos os nomes: `Script v2 - `.

| Marcador | Significado |
|---|---|
| `0 - Processo VELHO` | Processo VELHO, não processado (TODO: fluxo próprio). Sem o `1` |
| `1 - Tratado pelo Script` | Processo tratado pelo script (todos, exceto o VELHO). Adicionado se faltar, e o fluxo começa do início |
| `1.1 - Período Variável p/ Dependentes` | Memo da APIS tem período específico para dependentes |
| `1.2.1 - Mat. N Encontradas Base APIS` | Matrícula não encontrada na base APIS (renomeado de `... Base Geral`) |
| `1.5 - Aguarda APIS: Sem Memo p/ GEACS` | Estado (parada): memo à APIS (sem memorando para a GEACS) no bloco |
| `1.5 - Aguarda APIS: Formato Inválido` | Estado (parada): memo à APIS (formato inválido) no bloco |
| `1.6 - Avaliado Uso Rede Própria DISA` | Estado: base APIS e base DISA consultadas |
| `1.6.1 - Aguarda APIS: Matrículas` | Estado (parada): memo à APIS (matrículas não encontradas) no bloco, depois do `1.2.1` |
| `1.6.2 - Base DISA: Usou RP` / `1.6.2 - Base DISA: Não Usou RP` | Par (informativo): alguém tem ou não SIM na base DISA |
| `1.7 - Aguarda APIS: Período Deps` | Estado (parada): memo à APIS (período dos dependentes) no bloco, depois do `1.1` |
| `1.8 - Avaliado Uso Rede Própria MANTIS` | Estado: MANTIS consultado |
| `1.8.2 - MANTIS: Usou RP` / `1.8.2 - MANTIS: Não Usou RP` | Par (informativo): alguém tem ou não atendimento na rede própria do MANTIS |
| `1.9 - Aguarda DISA: Validar (Consta)` | Estado (parada): relatórios RP e memo à DISA (validar e complementar) no bloco |
| `1.9 - Aguarda DISA: Validar (N Consta)` | Estado (parada): relatórios RP e memo à DISA (validar, não consta) no bloco |
| `1.9 - Aguarda DISA: Relatório` | Estado (parada): memo à DISA (relatório) no bloco |
| `1.10 - Concluído: Memo DEPROC` | Estado (conclusão): relatórios RC e memo DEPROC no bloco |
| `1.2 - Avaliado Se Usou Rede Própria`, `1.4 - Memo Não Usou Rede no Bloco` | Versão anterior / correção. Não são mais adicionados nem consultados |
| `1.2.2 - Mat. N Encontradas Base DISA` | Versão anterior. Não é mais adicionado; tolerado com qualquer estado exceto `1.5` |
| `1.3 - Memos DISA e DEPROC no Bloco` | Versão anterior. **Identifica o processo VELHO** |
| `1.3 - Memo DEPROC no Bloco` | Versão anterior: concluído (só DEPROC). Não é reprocessado |
| `1.8.1 - Memo DISA Validar Usos MANTIS`, `1.9 - Memo DISA Uso Rede Própria` | Versão anterior: tratados como parada. Não são mais adicionados |
| `1.10 - Concluído: Memos DISA e DEPROC` | Versão anterior: concluído. Não é mais adicionado |
| `1.11 - VELHO Concluído: Memo DISA`, `1.11 - VELHO Concluído: Memo DEPROC` | Versão anterior (VELHO). Não são mais adicionados |
| `2 - Processo VELHO` e `2.x` (antigos) | Ignorados: o processo sem `1` recebe `1` e segue o fluxo do início |
| `PLANILHADO`, `UTILIZAÇÃO INSERIDA` (sem prefixo) | Manuais; não interferem |
| `MANUAL`, `ASSINADO` (sem prefixo) | Manuais; tiram o processo VELHO do escopo |

- Numeração: o número após `1.` é a ordem de inserção. **Mesmo número =
  alternativas** (o processo recebe um ou outro).
- **Marcadores de estado** (`TAGS_ESTADO_NOVO`: parada, retomada e
  conclusão): o processo tem no máximo um. Ao adicionar um estado,
  `adicionar_tag` remove o anterior (primeiro adiciona, depois remove).
  Mais de um estado no processo é erro (a remoção falhou): remova
  manualmente o(s) anterior(es).
- **Pares** (`TAGS_DUPLA_DISA`, `TAGS_DUPLA_MANTIS`): no máximo um de cada.
  São reavaliados a cada passagem; se a base mudou, `adicionar_tag` troca o
  marcador do par.
- Nomes: parada = `Aguarda <unidade>: <motivo>`; conclusão = `Concluído:
  <memos no bloco>`; retomada = `Avaliado ...`.
- **Conferência** (`conferir_marcadores`): no início e no fim de **toda**
  passagem, o script confere se a combinação de marcadores é possível no
  fluxo. Se não for, levanta `MarcadoresInconsistentes` (nenhuma ação no
  SEI quando é no início), `prox_acao` = Verificar marcadores
  inconsistentes, e a coluna `erro` lista todos os problemas. Regras:
  - no máximo um marcador de estado e um de cada par;
  - estado ou informativo (`1.1`, `1.2.1`, `1.2.2`, pares) exige o `1`;
  - informativo só com os estados que vêm depois dele (sem estado, não há
    regra): `1.2.2` com qualquer estado exceto `1.5`; `1.2.1` com `1.6`,
    `1.8` (falhou antes do memo) ou `1.6.1`; `1.1` com `1.6` ou `1.7`;
    `1.6.2 Usou` com `1.6`, `1.7`, `1.8`, `1.9 Validar (Consta)` ou `1.9
    Relatório`; `1.6.2 Não Usou` com `1.6`, `1.7`, `1.8`, `1.9 Validar (N
    Consta)` ou `1.10`; `1.8.2 Usou` com `1.8` ou os dois `1.9 Validar`;
    `1.8.2 Não Usou` com `1.8`, `1.9 Relatório` ou `1.10`;
  - `1.6.1` exige `1.2.1`; `1.7` exige `1.1`; cada `1.9 - Aguarda DISA`
    exige o seu par DISA e MANTIS; `1.11` exige `1.3 Memos DISA e DEPROC`;
  - VELHO (`0` ou `1.3 Memos DISA e DEPROC`) não tem `1.9` nem `1.10`;
  - os dois `1.3` juntos, ou `1.3 Memo DEPROC` (concluído na versão
    anterior) com estado do fluxo atual, são inconsistentes.

  Ao mudar o fluxo, ajuste as regras em `tags.py` (há testes em
  `tests/test_tags.py`).
- Os demais se acumulam: `0`, `1`, informativos (`1.1`, `1.2.1`), versão
  anterior (`1.2`, `1.2.2`, `1.3`, `1.4`) e manuais.
- **TODO**: `remover_marcador(driver, marcador)` ainda não existe na
  `sei_automacao` (`sei_automacao.processo`). Até existir, `tags.py` usa um
  placeholder (`REMOCAO_DE_MARCADOR_DISPONIVEL = False`) e o `main.py` não
  inicia.
- O SEI limita o nome do marcador a **50 caracteres** (há teste).
- **TODO**: editar no SEI os marcadores renomeados e cadastrar os novos
  (lista em [Pontos a validar](#pontos-a-validar-no-ambiente-real)) antes
  de rodar. Sem eles, `garantir_marcadores_no_sei` para o processo antes
  do memo, e os processos já marcados com o nome antigo não são
  reconhecidos.
- Os nomes em `tags.py` precisam ser **idênticos** aos cadastrados no SEI.
  Para renomear, edite o marcador existente no SEI (não crie outro) e
  atualize `tags.py` antes da próxima execução; senão os processos já
  marcados deixam de ser reconhecidos.

### Invariantes (não quebrar)

- O marcador de cada memo é adicionado **somente depois** que o memo está
  no bloco. Os relatórios em PDF entram antes do memo que os cita. Na
  retomada, as etapas até o estado atual (`1.6`, `1.8`) são puladas.
  Os marcadores que registram uma pesquisa (`1.2.1`, `1.6`, `1.6.2`, `1.8`,
  `1.8.2`, `1.1`) entram antes dos memos.
- Memos com texto pendente (`TEXTO_DEFINIDO = False`) levantam
  `TextoMemoPendente` antes de qualquer ação no SEI: os memos são montados
  antes de anexar relatórios, e nenhum memo com placeholder é criado. O
  mesmo vale para bloco não configurado (`None`): `ErroAvaliacao` antes de
  qualquer documento.
- O VELHO é separado **antes de qualquer memo**: nenhum memo do fluxo atual
  é criado em processo VELHO.
- Quem vai para a DISA **não** vai para a DEPROC. Cada memo à DISA valida a
  sua combinação base DISA × MANTIS (`ValueError` se não bater).
- O memo à APIS de matrículas só existe se alguma matrícula **não foi
  encontrada na base APIS**.
- Todos os memos são identificados **pelo assunto** (`PADRAO_ASSUNTO_*` em
  cada memorando; **não altere os assuntos** depois de criar memos), só na
  rodada. `incluir_memo(..., padrao_assunto=)` procura o memo antes de
  criar: se já existir sem o marcador, é **retomada**: o memo não é
  recriado e só o marcador é adicionado (coluna `<memo>_na_arvore`).
- Os três assuntos dos memos à DISA são diferentes entre si (nenhum contém
  outro) e do memo DISA da versão anterior ("Levantamento de atendimentos
  da rede própria..."), que está nos processos VELHOS.
- Blocos de assinatura:
  - `7697744` (`BLOCO_MEMO_DEPROC`): memo DEPROC;
  - `BLOCO_MEMO_DISA_VALIDAR_CONSTA`, `BLOCO_MEMO_DISA_VALIDAR_NAO_CONSTA`,
    `BLOCO_MEMO_DISA_RELATORIO`: memos à DISA (**TODO**: hoje `None`; o
    processo para com erro antes de criar documentos);
  - `7730344`: memo à APIS (sem memorando);
  - `7730341`: memo à APIS (formato inválido);
  - `7730905`: memo à APIS (período dos dependentes);
  - `7711907` (`BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS`): memo à APIS
    (matrículas). Se a constante for `None`, o processo para com erro
    antes de criar o memo.
- Signatária: Bruna Miiller Lavarini, Gerência de Auditoria e Contas da
  Saúde.

---

## Fluxo do processo

### Como ler

- No diagrama, cada coluna é uma **função**, lidas da esquerda para a
  direita (1 `main`, 2 `_tratar`, 3 `processar_novo`, 4
  `_avaliar_mantis_e_criar_docs`). Em cada coluna o caminho principal
  desce reto e os desvios saem para a direita e terminam ali. Caixas azuis
  são funções chamadas (o que fazem e o que chamam); caixas laranja (▶)
  levam a outra coluna. Caixas azul-escuras são as **variações do fluxo**
  (os quatro casos base DISA × MANTIS). A coluna da direita detalha as
  funções usadas em vários pontos (`_separar_velho`, `adicionar_tag`,
  `incluir_memo`, `incluir_relatorios` etc.). Verde: marcador adicionado;
  laranja tracejado: marcador removido; roxo: memo ou PDF; vermelho: erro.
- Um processo avança **ao longo de várias execuções**. Os marcadores do SEI
  guardam o estado: cada execução lê os marcadores, decide o que falta e
  continua dali.
- As perguntas de cada seção estão **na ordem em que o código as avalia**;
  vale a primeira que for verdadeira.
- **➕ `X`** indica o ponto exato em que o marcador `X` é adicionado
  (sempre via `tags.adicionar_tag`). Cada ➕ de estado ou de par remove o
  anterior do grupo (↻).
- Todo processo termina com uma `prox_acao` (valor de `ProxAcao`) ou com
  erro (`registrar_erro`). Em ambos os casos o registro vira uma linha da
  planilha de controle e o loop segue para o próximo processo.

### Ciclo de vida dos marcadores

`→` troca o estado e `+` acumula. Entre colchetes, opcional.

| Caminho | Sequência de marcadores | No SEI ao final |
|---|---|---|
| DISA sim, MANTIS sim | `1` + `1.6.2 Usou` + `1.6` → `1.8.2 Usou` + `1.8` → `1.9 Validar (Consta)` | `1`, `1.6.2 Usou`, `1.8.2 Usou`, `1.9 Validar (Consta)` |
| DISA não, MANTIS sim | `1` + `1.6.2 Não Usou` + `1.6` → `1.8.2 Usou` + `1.8` → `1.9 Validar (N Consta)` | `1`, `1.6.2 Não Usou`, `1.8.2 Usou`, `1.9 Validar (N Consta)` |
| DISA sim, MANTIS não | `1` + `1.6.2 Usou` + `1.6` → `1.8.2 Não Usou` + `1.8` → `1.9 Relatório` | `1`, `1.6.2 Usou`, `1.8.2 Não Usou`, `1.9 Relatório` |
| DISA não, MANTIS não | `1` + `1.6.2 Não Usou` + `1.6` → `1.8.2 Não Usou` + `1.8` → `1.10 Concluído: Memo DEPROC` | `1`, `1.6.2 Não Usou`, `1.8.2 Não Usou`, `1.10 Concluído: Memo DEPROC` |
| Parado pelo memo da APIS | `1` + `1.5` (um dos dois) | `1`, `1.5` |
| Parado pela base APIS | `1` + `1.2.1` + `1.6.1` | `1`, `1.2.1`, `1.6.1` |
| Parado pelo período dos dependentes | `1` + `1.6.2` + `1.6` + `1.1` → `1.7` | `1`, `1.6.2`, `1.1`, `1.7` |
| VELHO | `0` (+ o que já tinha) | `0`, … |

### 1. Script principal (`main.py`)

**Início**

1. Sem `remover_marcador` na `sei_automacao`, para aqui (TODO em
   [Marcadores](#marcadores-tagspy)).
2. Lê `dados/inputs/processos_nao_processados.xlsx` (aba
   `processos_reais`, coluna `num_sei`).
3. Carrega a base DISA, a base APIS e as bases do MANTIS.
4. Faz login no SEI.

**Para cada processo**

1. Abre o processo, lista a árvore e lê os marcadores **do SEI** (tudo
   fica no registro).
2. Roteamento (`_tratar`). **Nenhum marcador é adicionado aqui**, exceto o
   `1` e o `0` (em `_separar_velho`):

| # | Pergunta | Se sim |
|---|---|---|
| 1 | Marcadores inconsistentes (`conferir_marcadores`, [regras](#marcadores-tagspy))? | Erro, antes de qualquer ação. `prox_acao` = Verificar marcadores inconsistentes (corrigir no SEI) |
| 2 | VELHO pelos marcadores (`0` ou `1.3 Memos DISA e DEPROC`)? | `_separar_velho`: com `MANUAL`/`ASSINADO`, `prox_acao` = Fora do escopo; senão **➕ `0`** (se faltar), `prox_acao` = VELHO: não processado. **TODO**: fluxo do VELHO |
| 3 | Estado de parada (`1.5`, `1.6.1`, `1.7`, `1.9 - Aguarda DISA`; versão anterior: `1.8.1`, `1.9 Memo DISA`)? | Erro: processo parado. `prox_acao` = Aguardar resposta ao memo enviado. **TODO**: processamento depois da resposta |
| 4 | Estado de conclusão (`1.10`)? | Concluído. `prox_acao` = assinar os memos correspondentes e encaminhar |
| 5 | Sem estado com `1.3 Memo DEPROC`? | Concluído na versão anterior. `prox_acao` = Assinar memo DEPROC e encaminhar |
| 6 | VELHO pelos memos da GEACS (`encontrar_memos_velho`, [regra](#processo-velho))? | `_separar_velho` (como no 2). Par sem data legível: erro, sem ação |
| 7 | **Não** tem `1`? | **➕ `1`** e [seção 2](#2-fluxo-processar_novo) do início (inclusive com documento da GEACS ou com o antigo `2`) |
| — | (nenhuma das anteriores) | [Seção 2](#2-fluxo-processar_novo), do início ou retomando (`1.6`, `1.8`) |

Depois do roteamento (sem erro), os marcadores são conferidos de novo
(`conferir_marcadores`); se a passagem deixou uma combinação impossível,
o processo termina com o mesmo erro.

**Fim**: atualiza a planilha de controle geral e grava o resumo no log
([Saídas](#saídas)).

### 2. Fluxo (`processar_novo`)

Na retomada, as etapas até o estado atual são puladas (`_etapa_feita`): o
estado não é adicionado de novo. As pesquisas (base APIS, base DISA,
MANTIS) são refeitas a cada passagem; os informativos (`1.1`, `1.2.1`)
usam `adicionar_tag_se_ausente`, e os pares só são adicionados se faltarem
(se a base mudou, o par é trocado).

Cada memo é criado, inserido no bloco e só então recebe o seu marcador.
Antes de criar, `incluir_memo` procura o memo pelo assunto entre os memos
da GEACS da rodada: se já existe, não recria e só adiciona o marcador.
Antes de cada grupo de marcadores, `garantir_marcadores_no_sei`.

1. `obter_dados_ui` lê **todos os memorandos da APIS-Utilização**, mantém
   os destinados à GEACS (coluna `memos_apis_geacs_sei`) e usa o
   **último**. Os documentos depois dele são a rodada.
   - **Nenhum?** Cria `MemoApisSemMemo` (bloco `7730344`), **➕ `1.5 -
     Aguarda APIS: Sem Memo p/ GEACS`**, `prox_acao` = Assinar memo à APIS (sem
     memorando para a GEACS) e encaminhar. Fim.
2. `validar_template` e `extrair_dados_ui`: nome e matrícula do titular,
   período do titular, matrículas dos dependentes e se há período variável
   para dependentes.
   - **Formato inválido** (qualquer modelo diferente do novo_novo)? Cria
     `MemoApisFormatoInvalido` (bloco `7730341`), **➕ `1.5 - Aguarda APIS:
     Formato Inválido`**, `prox_acao` = Assinar memo à APIS (formato do
     memorando inválido) e encaminhar. Motivo na coluna
     `motivo_formato_invalido`. Fim.
3. `verificar_base_apis`: procura titular e dependentes **só na base
   APIS** (matrícula em formato inválido: erro).
   - **Faltou matrícula?** **➕ `1.2.1 - Mat. N Encontradas Base APIS`**,
     memo à APIS (`incluir_memo_apis_mat_nao_encontradas`; bloco
     `7711907`), **➕ `1.6.1 - Aguarda APIS: Matrículas`**, `prox_acao` =
     Assinar memo à APIS (matrículas não encontradas) e encaminhar. Fim.
   - **Encontrou todas, mas o processo tem `1.2.1`** (base corrigida)?
     Erro, sem ação: remover o marcador no SEI para reprocessar.
4. `avaliar_uso_rede_propria_disa`: uso da rede própria na base DISA (fora
   dela = não usou).
   - **➕ `1.6.2 - Base DISA: Usou RP`** (alguém com SIM) ou **➕ `1.6.2 -
     Base DISA: Não Usou RP`**.
   - **➕ `1.6 - Avaliado Uso Rede Própria DISA`** (se o estado ainda não
     passou dele).
5. **Há período variável para dependentes?** Sim: **➕ `1.1`**,
   `MemoApisPeriodoDependentes` (bloco `7730905`), **➕ `1.7 - Aguarda APIS:
   Período Deps`**, `prox_acao` = Assinar memo à APIS (período dos
   dependentes) e encaminhar. Fim.
6. `avaliar_uso_rede_propria_mantis` (período do titular; rede própria e
   rede credenciada, registradas na planilha de controle; colunas
   `caso_disa_mantis` e `mats_uso_mantis_alem_disa`). O memo do caso
   ([tabela](#decisão-base-disa--mantis)) é montado (texto pendente ou
   bloco `None` param aqui).
   - **➕ `1.8.2 - MANTIS: Usou RP`** ou **➕ `1.8.2 - MANTIS: Não Usou RP`**.
   - **➕ `1.8 - Avaliado Uso Rede Própria MANTIS`** (se o estado ainda não
     passou dele).
7. **Base DISA × MANTIS** (rede própria, processo inteiro):
   - **DISA sim, MANTIS sim**: relatórios RP, `MemoDisaValidarConsta`,
     **➕ `1.9 - Aguarda DISA: Validar (Consta)`**; `prox_acao` = Assinar
     memo à DISA (validar e complementar) e encaminhar. Fim;
   - **DISA não, MANTIS sim**: relatórios RP, `MemoDisaValidarNaoConsta`,
     **➕ `1.9 - Aguarda DISA: Validar (N Consta)`**; `prox_acao` = Assinar
     memo à DISA (validar; não consta na base DISA) e encaminhar. Fim;
   - **DISA sim, MANTIS não**: `MemoDisaRelatorio` (sem PDF), **➕ `1.9 -
     Aguarda DISA: Relatório`**; `prox_acao` = Assinar memo à DISA
     (relatório da rede própria) e encaminhar. Fim;
   - **DISA não, MANTIS não**: relatórios RC (se alguém usou a rede
     credenciada) e `MemoDeproc` (todos os beneficiários; cita a rede
     credenciada; bloco `7697744`), **➕ `1.10 - Concluído: Memo DEPROC`**;
     `prox_acao` = Assinar memo DEPROC e encaminhar.

Em todos os finais com memo, o script relê a árvore para obter o número
SEI dos memos criados (colunas `<memo>_sei`; falha só gera log). Os três
memos à DISA usam as mesmas colunas `memo_disa_*`.

Se o script falhar entre criar um relatório ou memo e adicionar o
marcador, a próxima execução retoma do estado: o relatório (pelo nome) e
o memo (pelo assunto) já na rodada não são recriados. Se falhar entre
adicionar o estado novo e remover o anterior, a próxima execução encontra
dois estados (erro da conferência, pergunta 1 da seção 1).

---

## Saídas

### Planilha de controle geral

`dados/controle/controle_geral_de_processos.xlsx`, gravada por
`PlanilhaControleGeral`: lida uma vez no início da execução e regravada
**depois de cada processo** (`registrar`), para que uma interrupção não
perca os processos já tratados.

- Aba `processos`: **uma linha por processo**, com a última passagem pelo
  fluxo. As colunas que o script grava são sobrescritas (o processo é
  reavaliado a cada passagem); as que ele não grava (ex.: colunas antigas
  do script de correção, `titular_nao_encontrado`, `deps_nao_encontrados`
  e `memo_deproc_credenciada_*`) e `primeira_passagem` são mantidas.
- Aba `historico`: **uma linha por passagem**, acrescentada a cada
  execução.
- Primeiras colunas: `num_processo`, `primeira_passagem`,
  `ultima_passagem` (data e hora em que o processo passou pelo fluxo),
  `script` (`main`; `correcao_rede_propria` nas passagens antigas),
  `data_execucao` (identifica a execução), `fluxo`, `prox_acao`,
  `tipo_erro`, `erro`.
- Cada linha vem de `RegistroBase.to_dict()`: todos os campos do registro,
  exceto os de `_CAMPOS_INTERNOS`, mais `marcadores_finais` e uma coluna
  `tag_*` por marcador (o processo terminou a passagem com ele).
  **Não renomeie as colunas existentes** (por isso as da base APIS
  continuam com `base_geral`).
- Rastreabilidade: `velho`, `memos_velho_sei`, `memo_apis_sei`,
  `memos_apis_geacs_sei`, `modelo_memo_apis`, `motivo_formato_invalido`,
  `memo_apis_sem_memo_sei`, `memo_apis_formato_invalido_sei`,
  `memo_apis_periodo_deps_sei`, `memo_disa_sei`, `memo_deproc_sei`,
  `relatorios_incluidos`, `relatorios_na_arvore`, `marcadores_sei` (lidos
  no início), `marcadores_adicionados`, `marcadores_removidos` e
  `marcadores_finais`.
- Base DISA: `tit_usou`, `deps_que_usaram`, `deps_que_nao_usaram`.
- MANTIS: `tit_usou_mantis_rede_propria`,
  `tit_valor_total_uso_mantis_rede_propria`,
  `deps_que_usaram_mantis_rede_propria`,
  `deps_valor_total_uso_mantis_rede_propria`, as mesmas para
  `rede_credenciada`, `mats_uso_mantis_alem_disa` e `caso_disa_mantis`.
- `tem_periodo_var_deps` (sim/não).
- Matrículas não encontradas na base APIS:
  `titular_nao_encontrado_base_geral` e `deps_nao_encontrados_base_geral`.
- Formatação: cabeçalho congelado e com filtro; linha com erro em vermelho
  claro; matrículas não encontradas em amarelo. Se a formatação falhar, a
  aba fica salva sem ela.
- Backup: uma vez por execução, antes da primeira gravação, a planilha
  anterior é copiada para
  `dados/controle/backup/controle_geral_de_processos_<data>.xlsx` (são
  mantidos os 30 mais recentes).
- Se não for possível gravar a planilha (ex.: aberta no Excel), aquela
  gravação vai para `controle_geral_de_processos_<data>_NAO_INCORPORADO.xlsx`;
  a gravação seguinte tenta de novo a planilha geral, com tudo (o log diz
  quando o arquivo à parte pode ser apagado). Se não for possível **ler**
  a planilha no início, a execução inteira vai para o arquivo à parte e
  **não** entra na planilha geral; confira e incorpore manualmente.

### Logs

- `logs/<data>_execucao.log`, com resumo final.

---

## Pontos a validar no ambiente real

- **TODO**: implementar `remover_marcador(driver, marcador)` na
  `sei_automacao` (`sei_automacao.processo`). Até lá o `main.py` não roda.
- **TODO**: no SEI (Gerenciar Marcador), **editar** os marcadores
  renomeados, antes da próxima execução:
  - `1 - Processo NOVO` → `1 - Tratado pelo Script`;
  - `1.2.1 - Mat. N Encontradas Base Geral` → `1.2.1 - Mat. N Encontradas
    Base APIS`;
  - `1.5 - Memo APIS Sem Memo p/ GEACS` → `1.5 - Aguarda APIS: Sem Memo p/
    GEACS`;
  - `1.5 - Memo APIS Formato Inválido` → `1.5 - Aguarda APIS: Formato
    Inválido`;
  - `1.6.1 - Memo APIS Mat. N Encontradas` → `1.6.1 - Aguarda APIS:
    Matrículas`;
  - `1.7 - Memo APIS Período Dependentes` → `1.7 - Aguarda APIS: Período
    Deps`;
  - `1.10 - Memo DEPROC Coparticipação` → `1.10 - Concluído: Memo DEPROC`.

  E **cadastrar** `0 - Processo VELHO`, `1.6.2 - Base DISA: Usou RP`,
  `1.6.2 - Base DISA: Não Usou RP`, `1.8.2 - MANTIS: Usou RP`, `1.8.2 -
  MANTIS: Não Usou RP`, `1.9 - Aguarda DISA: Validar (Consta)`, `1.9 -
  Aguarda DISA: Validar (N Consta)` e `1.9 - Aguarda DISA: Relatório`.
  Todos com o prefixo `Script v2 - `, idênticos aos de `tags.py`.
- **TODO**: blocos dos três memos à DISA (`BLOCO_MEMO_DISA_*` em
  `constantes.py`, hoje `None`).
- **TODO**: revisar os rascunhos dos memos à DISA (`MemoDisa.py`: validar e
  complementar, validar não consta, relatório) e confirmar os três
  assuntos **antes** de criar o primeiro memo; depois trocar
  `TEXTO_DEFINIDO` para `True`. Conferir o parágrafo da rede credenciada no
  `MemoDeproc` (`_par_rede_credenciada`).
- **TODO**: textos e assuntos dos memos `MemoApisSemMemo` (modelo Despacho
  2, SEI 150644870; avaliar criar como Despacho), `MemoApisFormatoInvalido`
  (modelo Memorando 2019, SEI 150646384) e `MemoApisPeriodoDependentes`.
  Depois trocar `TEXTO_DEFINIDO` para `True`. Defina os assuntos **antes**
  de criar o primeiro memo: depois, o assunto não pode mudar.
- **TODO**: fluxo do processo VELHO (`main._separar_velho`).
- **TODO**: confirmar que o pedido de "atualização do levantamento de
  utilização" é o que distingue o modelo novo_novo do novo_velho
  (`_PADRAO_ATUALIZACAO_LEVANTAMENTO` em `extrator_dados_ui.py`).
- **TODO**: confirmar o DV das matrículas nas bases do MANTIS e usar as
  planilhas completas. As planilhas de exemplo atuais ainda têm as colunas
  antigas (`MATRICULA_BENEFICIARIO`, `DAT_ATENDIMENTO`, `VAL_PAGAR`) e não
  carregam.
- **TODO**: processamento dos processos parados (`1.5`, `1.6.1`, `1.7`,
  `1.9 - Aguarda DISA`; versão anterior `1.8.1` e `1.9 Memo DISA`) depois
  da resposta da APIS/DISA.
- Confirmar que o texto dos memorandos da GEACS (`obter_conteudo_doc`) traz
  a linha "Para: ..." e a data "Belo Horizonte, <dia> de <mês> de <ano>."
  (a identificação do VELHO depende disso). A busca lê todos os memos da
  GEACS de cada processo que vai para `processar_novo`.
- Confirmar que o nome do documento externo na árvore é `PDF <número>`
  (a retomada dos relatórios e `espera_documento_aparecer_arvore` dependem
  disso) e que o número cabe no campo do SEI.
- Confirmar que `obter_conteudo_doc` devolve a linha de **assunto** do memo.
  A retomada de todos os memos depende disso. A retomada também supõe que
  o memo encontrado já está no bloco (o log pede para conferir).
- Confirmar que `listar_documentos_arvore` logo após criar os memos traz
  os memos novos no fim da árvore, na ordem de criação. Os números SEI dos
  memos dependem disso.
- Confirmar que a leitura da lista de marcadores ("Gerenciar Marcador",
  opções `#selMarcador label.dd-option-text`) traz todos os marcadores da
  unidade e sai da tela sem salvar.
- Processos que receberam a cadeia de estados antiga (por exemplo `1.6` e
  `1.8`, ou `1.9` e `1.10 Memo DEPROC Coparticipação`, nas execuções de teste de outubro
  de 2026) caem na conferência dos marcadores (mais de um estado). Deixe só o
  estado atual. Os que ficaram com `1.10 - Concluído: Memos DISA e DEPROC`
  continuam como concluídos (versão anterior), com memo DEPROC no bloco.
- Processos da versão anterior com `1.2.1`/`1.2.2` e sem estado são
  reprocessados do início: se a matrícula ainda falta na base APIS, recebem
  o memo à APIS; se agora está na base, param pedindo para remover o
  `1.2.1`.
- A planilha de controle, os backups, os PDFs (`dados/utilizacoes`) e os
  logs têm nomes e matrículas (LGPD). Restrinja o acesso a essas pastas.
