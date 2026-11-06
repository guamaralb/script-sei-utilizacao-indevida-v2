# Script SEI - Utilização Indevida (v2)

Automação Selenium no SEI-MG (IPSEMG) que prepara a apuração de utilização
indevida da assistência à saúde:

- separa os processos VELHOS (não processados; fluxo a definir);
- lê o último memorando da APIS destinado à GEACS;
- confere as matrículas na base APIS e compara o uso da rede própria na
  base DISA e no MANTIS (e, no MANTIS, o da rede credenciada);
- anexa os relatórios do MANTIS em PDF (rede própria e credenciada, de quem
  usou) e gera **um** memorando: à DISA (um por caso da comparação), à
  DEPROC ou, sem uso em nenhuma base, à APIS.

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
  (base DISA e MANTIS) e alguém usou a rede credenciada. Processo enviado à
  DISA não vai para a DEPROC.
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
| `main.py` | Script principal: separação do VELHO (`_separar_velho`) e roteamento pelos marcadores (`_tratar`) |
| `processar_novo.py` | Fluxo dos processos não VELHOS (com retomada pelo marcador de estado); `obter_dados_ui()` lê o último memo da APIS destinado à GEACS; `_avaliar_mantis_e_criar_docs()` compara base DISA × MANTIS e escolhe o memo |
| `relatorios_mantis.py` | `incluir_relatorios()`: gera os PDFs do MANTIS (titular e dependentes) e os anexa como documento externo, com retomada pelo nome na árvore |
| `transformar_xls_em_pdf.py` | Monta o PDF do relatório de utilização (ReportLab) |
| `memos_sei.py` | `incluir_memo()` (procura o memo pelo assunto na rodada, ou cria e insere no bloco) e `registrar_numeros_memos()` (número SEI dos memos criados) |
| `sessao_sei.py` | `abrir_sei()`: navegador e login (credenciais do `.env`) |
| `rede_propria.py` | Carga da base DISA e da base APIS, normalização de matrícula, `verificar_base_apis()` (existência), `avaliar_uso_rede_propria_disa()` (uso), `ErroAvaliacao` |
| `mantis.py` | Carga das bases do MANTIS (rede própria e credenciada, com os atendimentos), interpretação do período de apuração, `avaliar_uso_rede_propria_mantis()` e `usos_mantis_alem_disa()` |
| `docs_processo.py` | Filtros da árvore, memos da APIS destinados à GEACS, busca de memos da GEACS pelo assunto e de documentos pelo nome, `encontrar_memos_velho()` (memos DISA → DEPROC antigos) |
| `extrator_dados_ui.py` | Extrai as instruções do texto do memo da APIS: o modelo com período por dependente (procurado primeiro, pela linha do período do dependente; duplas matrícula + período) e o "novo_novo"; os outros são formato inválido |
| `matriculas_nao_encontradas.py` | Memo à APIS de matrículas não encontradas na base APIS (`incluir_memo_apis_mat_nao_encontradas`) |
| `tags.py` | Todos os marcadores, grupos de estado e pares, `registrar_tags()`, `adicionar_tag()` (troca o estado ou o par), `adicionar_tag_se_ausente()`, `remover_tag()`, `tem_tag()`, `estado_atual()`, `eh_velho_pelos_marcadores()` e `conferir_marcadores()` |
| `marcadores_disponiveis.py` | `garantir_marcadores_no_sei()`: confere, antes de criar memos, se os marcadores existem no SEI |
| `constantes.py` | Unidades, blocos, signatária, caminhos fixos, data de corte do VELHO |
| `log_config.py` | Logging: processo atual em cada linha e resumo final |
| `Registro.py` | Uma passagem de um processo (`RegistroBase`, `RegistroMain`, `RegistroAlt1`): árvore, rodada, marcadores e resultado; `ProxAcao` e `registrar_erro()` |
| `planilha_controle.py` | `PlanilhaControleGeral`: atualiza e formata a planilha de controle geral a cada processo, com backup |
| `memorandos/` | `DadosUI`, `DocArvore` (item da árvore: memo da APIS), `UsoRede` (`UsoRedeBeneficiarios`), `MemoDisa` (`MemoDisaValidarConsta`, `MemoDisaValidarNaoConsta`, `MemoDisaSemMantisSolicitaRelatorio`), `MemoDeproc`, `MemoApisSemUso`, `MemoApisMatNaoEncontradas`, `MemoApisSemMemo`, `MemoApisFormatoInvalido`, `MemoApisPeriodoDependentes` (ver `TextoPendente`), `MemoApisComTodasAsInformacoes` (retorno final à APIS, com tabelas; ainda fora do fluxo) |
| `main_alt_1.py` | Fluxo alternativo ALT 1 (`poetry run task run_alt_1`): loop dos processos e registro na planilha de controle ([seção](#fluxo-alternativo-alt-1)) |
| `planilhas_alt_1.py` | ALT 1: encontra as planilhas na árvore, baixa, lê (`ler_planilha`), gera o PDF e o insere (`inserir_pdfs_das_planilhas`; `inserir_pdfs` e `deixar_aguardando_fluxo_normal` são usados também pelo fluxo PDF) |
| `main_fluxo_pdf.py` | Fluxo PDF (`poetry run task run_pdf`): usa o loop `executar` do `main_alt_1.py` ([seção](#fluxo-pdf)) |
| `planilhas_fluxo_pdf.py` | Fluxo PDF: acha os arquivos do processo em `dados/fluxo_pdf/planilhas`, o documento na árvore e insere os PDFs (`inserir_pdfs_da_pasta`) |
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
- Testes com **pytest** (`poetry run task test`). **Atenção:** com
  `SEI_TESTE_REAL` e `SEI_TESTE_REAL_<MEMO>` em `'1'` no `.env`, a suíte cria
  memos no SEI real (`tests/test_memos_sei_real.py`). O main não tem efeito
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
- Além do modelo com período por dependente (abaixo), só o modelo
  **novo_novo** é válido (exemplo: Memorando
  IPSEMG/APIS-UTILIZAÇÃO nº 2627/2026). Ele tem os campos `Nome completo`,
  `Matrícula`, `Período de apuração do titular` e `Matrícula dos
  dependentes` **e** o pedido de "atualização do levantamento de
  utilização". Sem esse pedido é o modelo novo_velho; com "Segurado(a)", o
  velho. Os dois são formato inválido.
- **Modelo com período por dependente** (`periodo_por_dependente`): cada
  dependente tem o seu período de apuração. Os campos do titular são os do
  novo_novo e cada dependente tem uma dupla de linhas, nesta ordem:

  ```
  Matrícula do dependente: XXXXXXX
  Período de apuração do dependente: DD/MM/AAAA a DD/MM/AAAA.
  ```

  É procurado **antes** do novo_novo: o memo é deste modelo se tiver alguma
  linha `Período de apuração do dependente:`. Um resumo (`Matrículas dos
  dependentes: 555; 666`) é ignorado: os dependentes são os das duplas. O
  pedido de "atualização do levantamento" não é exigido. São formato
  inválido: faltar campo do titular; linha de matrícula ou de período fora
  de dupla; mais de uma matrícula na linha; período sem número par de datas
  `DD/MM/AAAA` (não vazio) ou que `interpretar_periodo` recuse; e dependente
  com dois períodos. Vários intervalos são aceitos na mesma linha. Os
  períodos ficam em `DadosUI.periodos_por_dependente` (matrícula normalizada →
  período), os dependentes vão para as bases APIS, DISA e MANTIS como nos
  outros modelos, e o MANTIS usa o período de cada um. O fluxo **não** para
  pelo período variável (sem `1.1` e `1.7`). É por este modelo que passa o
  memorando corrigido pedido no `MemoApisPeriodoDependentes`.
- Nas matrículas do memo, titular e dependentes, o DV é opcional: junto ou
  separado (`1289612 / 8`, `1289612-8`) são aceitos.
- O último memo da APIS destinado à GEACS fica em `registro.memo_apis`
  (`DocArvore`: `numero_sei`, `nome_arvore` e `unidade`, como na árvore) e
  é passado a **todos** os memorandos (`memo_apis=`), exceto o
  `MemoApisSemMemo` (não há memo da APIS).
- Nos memorandos, o titular aparece só pelas **iniciais**
  (`DadosUI.nome_titular_iniciais`: `José da Silva` → `J.S.`, sem "de",
  "da", "do", "das", "dos", "e"). O nome completo fica nos PDFs do MANTIS
  e na planilha de controle.
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
- **DV** (último dígito): base APIS com DV; MANTIS sem DV (conferido nas
  planilhas: todas as matrículas batem sem o DV); memorandos com ou sem,
  tanto titular quanto dependentes. O tamanho não diz qual é o caso, pois há
  matrículas com menos dígitos. Por isso `verificar_base_apis` procura a
  matrícula do memo na base APIS com e sem DV:
  - achou uma: dali em diante o titular fica **com DV** (base DISA) e o
    dependente **sem DV** (base DISA e MANTIS);
  - não achou: matrícula não encontrada, inclusive com DV errado (`1.2.1`);
  - achou mais de uma: `ErroAvaliacao`, sem ação no SEI (hoje não acontece
    na base APIS).
  Os períodos por dependente passam pela mesma conversão
  (`periodos_dos_dependentes`).
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
    variável para antes do MANTIS). Exceção: no modelo com período por
    dependente, cada dependente usa o seu (`periodos_por_dependente`; quem
    não está nele usa o do titular). Titular e dependentes são avaliados.
  - Formatos de período aceitos: `01/08/2023 a 12/06/2024`,
    `09/2023 a 06/2024` e `02 a 06/2024`, com vários intervalos (entre
    parênteses ou não). Qualquer outro número no texto, data inválida ou
    início depois do fim: `ErroAvaliacao`.
  - Atendimento sem data válida de uma matrícula consultada:
    `ErroAvaliacao`. Sem valor: conta como 0.

### Decisão base DISA × MANTIS

Pelo **processo inteiro**: DISA = alguém tem SIM na base DISA; MANTIS RP /
RC = alguém tem atendimento na rede própria / credenciada do MANTIS no
período. Cada um tem um par de marcadores (`1.6.2`, `1.8.2` e `1.8.3`,
"Usou" / "Não Usou").

| Base DISA | MANTIS RP | MANTIS RC | Ação | Memo (bloco) | Marcador |
|---|---|---|---|---|---|
| sim | sim | qualquer | Memo à DISA para **validar e complementar** com os dados dela | `MemoDisaValidarConsta` (`BLOCO_MEMO_DISA_VALIDAR_CONSTA`) | `1.9 - Aguarda DISA: Validar (Consta)` |
| não | sim | qualquer | Memo à DISA para **validar**, informando que não consta na planilha | `MemoDisaValidarNaoConsta` (`BLOCO_MEMO_DISA_VALIDAR_NAO_CONSTA`) | `1.9 - Aguarda DISA: Validar (N Consta)` |
| sim | não | qualquer | Sem MANTIS: memo à DISA **solicitando o relatório** com os dados dela | `MemoDisaSemMantisSolicitaRelatorio` (`BLOCO_MEMO_DISA_SEM_MANTIS_RELATORIO`) | `1.9 - Aguarda DISA: Relat. s/ MANTIS` |
| não | não | sim | Memo DEPROC | `MemoDeproc` (`7697744`) | `1.10 - Concluído: Memo DEPROC` |
| não | não | não | **Nenhum uso**: memo à APIS (sem DEPROC) | `MemoApisSemUso` (`BLOCO_MEMO_APIS_SEM_USO`) | `1.10 - Aguarda APIS: Sem Uso` |

- Em **todos** os casos, os relatórios RP e RC em PDF de quem usou são
  anexados antes do memo (sem atendimento, nada é anexado).
- Processo enviado à DISA **não** vai para a DEPROC (nem memo DEPROC). O
  memo à DISA e o memo à APIS (nenhum uso) são **paradas** (aguardam o
  retorno).
- Os memos à DISA (destinatário Felippe Gonçalves Declie Fagioli, Diretor
  de Saúde) citam o memo da APIS pela árvore, sem o ano (`identificar_doc`:
  "Memorando IPSEMG/APIS-UTILIZAÇÃO nº 2627 (150644870)"). Os dois de
  validação citam também os relatórios RP pelo número SEI ("no documento
  X" / "nos documentos X e Y"); o memo é montado antes dos relatórios só
  para conferência (`_RELATORIOS_A_ANEXAR`) e de novo depois, com os
  números (`_escolher_memo`).
- A coluna `mats_uso_mantis_alem_disa` lista quem usou no MANTIS e não
  consta na base DISA; `caso_disa_mantis` diz o caso
  ("DISA sim, MANTIS RP não, MANTIS RC sim").

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
- `incluir_relatorios` devolve o número SEI dos PDFs (o anexado agora é
  procurado pelo nome, relendo a árvore; não achou: `ErroAvaliacao`, e a
  próxima execução o encontra pela retomada).

### Marcadores (`tags.py`)

Prefixo de todos os nomes: `Script v2 - `. Exceção: os marcadores velhos `1.2`,
`1.2.2`, `1.3` e `1.4` usam `Script v2v - `, de propósito, para sinalizar que
são velhos.

| Marcador | Significado |
|---|---|
| `0 - Processo VELHO` | Processo VELHO, não processado (TODO: fluxo próprio). Sem o `1` |
| `1 - Tratado pelo Script` | Processo tratado pelo script (todos, exceto o VELHO). Adicionado se faltar, e o fluxo começa do início |
| `1.0 - Aguarda Script: Fluxo Normal` | Estado (entrada): PDFs inseridos pelo [fluxo ALT 1](#fluxo-alternativo-alt-1). O fluxo normal trata o processo do início e o próximo estado o substitui. Sai também se o processo for VELHO |
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
| `1.8.3 - MANTIS: Usou RC` / `1.8.3 - MANTIS: Não Usou RC` | Par (informativo): alguém tem ou não atendimento na rede credenciada do MANTIS |
| `1.9 - Aguarda DISA: Validar (Consta)` | Estado (parada): relatórios e memo à DISA (validar e complementar) no bloco |
| `1.9 - Aguarda DISA: Validar (N Consta)` | Estado (parada): relatórios e memo à DISA (validar, não consta) no bloco |
| `1.9 - Aguarda DISA: Relat. s/ MANTIS` | Estado (parada): memo à DISA (sem MANTIS, solicita relatório) no bloco |
| `1.10 - Concluído: Memo DEPROC` | Estado (conclusão): relatórios RC e memo DEPROC no bloco |
| `1.10 - Aguarda APIS: Sem Uso` | Estado (parada): memo à APIS (nenhum uso em nenhuma base) no bloco |
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
- **Marcadores de estado** (`TAGS_ESTADO_NOVO`: entrada, parada, retomada
  e conclusão): o processo tem no máximo um. Ao adicionar um estado,
  `adicionar_tag` remove o anterior (primeiro adiciona, depois remove).
  Mais de um estado no processo é erro (a remoção falhou): remova
  manualmente o(s) anterior(es).
- **Pares** (`TAGS_DUPLA_DISA`, `TAGS_DUPLA_MANTIS`, `TAGS_DUPLA_MANTIS_RC`):
  no máximo um de cada.
  São reavaliados a cada passagem; se a base mudou, `adicionar_tag` troca o
  marcador do par.
- Nomes: parada = `Aguarda <unidade>: <motivo>`; conclusão = `Concluído:
  <memos no bloco>`; retomada = `Avaliado ...`; entrada = `Aguarda Script:
  <motivo>`.
- **Conferência** (`conferir_marcadores`): no início e no fim de **toda**
  passagem, o script confere se a combinação de marcadores é possível no
  fluxo. Se não for, levanta `MarcadoresInconsistentes` (nenhuma ação no
  SEI quando é no início), `prox_acao` = Verificar marcadores
  inconsistentes, e a coluna `erro` lista todos os problemas. Regras:
  - no máximo um marcador de estado e um de cada par;
  - estado ou informativo (`1.1`, `1.2.1`, `1.2.2`, pares) exige o `1`;
  - informativo só com os estados que vêm depois dele (sem estado ou com
    `1.0`, não há regra): `1.2.2` com qualquer estado exceto `1.5`; `1.2.1` com `1.6`,
    `1.8` (falhou antes do memo) ou `1.6.1`; `1.1` com `1.6` ou `1.7`;
    `1.6.2 Usou` com `1.6`, `1.7`, `1.8`, `1.9 Validar (Consta)` ou `1.9
    Relat. s/ MANTIS`; `1.6.2 Não Usou` com `1.6`, `1.7`, `1.8`, `1.9
    Validar (N Consta)` ou um dos `1.10`; `1.8.2 Usou` com `1.8` ou os dois
    `1.9 Validar`; `1.8.2 Não Usou` com `1.8`, `1.9 Relat. s/ MANTIS` ou um
    dos `1.10`; `1.8.3 Usou` com `1.8`, qualquer `1.9 - Aguarda DISA` ou
    `1.10 Concluído: Memo DEPROC`; `1.8.3 Não Usou` com `1.8`, qualquer `1.9
    - Aguarda DISA` ou `1.10 Aguarda APIS: Sem Uso`;
  - `1.6.1` exige `1.2.1`; `1.7` exige `1.1`; cada `1.9 - Aguarda DISA`
    exige o seu par DISA e MANTIS RP; `1.10 - Aguarda APIS: Sem Uso` exige
    os três "Não Usou"; `1.11` exige `1.3 Memos DISA e DEPROC`;
  - VELHO (`0` ou `1.3 Memos DISA e DEPROC`) não tem `1.9` nem os `1.10`;
  - os dois `1.3` juntos, ou `1.3 Memo DEPROC` (concluído na versão
    anterior) com estado do fluxo atual, são inconsistentes.

  Ao mudar o fluxo, ajuste as regras em `tags.py` (há testes em
  `tests/test_tags.py`).
- Os demais se acumulam: `0`, `1`, informativos (`1.1`, `1.2.1`), versão
  anterior (`1.2`, `1.2.2`, `1.3`, `1.4`) e manuais. Exceção: o `1.2.1` é
  removido quando as matrículas passam a constar na base APIS.
- A remoção usa `remover_marcador(driver, [marcador])` da `sei_automacao`
  (`sei_automacao.processo`; recebe uma lista). Se o marcador não estiver
  no processo, a biblioteca não faz nada.
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
- Os relatórios RP e RC de quem usou entram em **todos** os casos, antes do
  memo. O memo à APIS (nenhum uso) só existe sem uso na base DISA, no MANTIS
  RP e no MANTIS RC.
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
    `BLOCO_MEMO_DISA_SEM_MANTIS_RELATORIO`: memos à DISA, e
    `BLOCO_MEMO_APIS_SEM_USO`: memo à APIS (nenhum uso) (**TODO**: hoje
    `None`; o processo para com erro antes de criar documentos);
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
| DISA sim, RP sim | `1` + `1.6.2 Usou` + `1.6` → `1.8.2 Usou` + `1.8.3` + `1.8` → `1.9 Validar (Consta)` | `1`, `1.6.2 Usou`, `1.8.2 Usou`, `1.8.3`, `1.9 Validar (Consta)` |
| DISA não, RP sim | `1` + `1.6.2 Não Usou` + `1.6` → `1.8.2 Usou` + `1.8.3` + `1.8` → `1.9 Validar (N Consta)` | `1`, `1.6.2 Não Usou`, `1.8.2 Usou`, `1.8.3`, `1.9 Validar (N Consta)` |
| DISA sim, RP não | `1` + `1.6.2 Usou` + `1.6` → `1.8.2 Não Usou` + `1.8.3` + `1.8` → `1.9 Relat. s/ MANTIS` | `1`, `1.6.2 Usou`, `1.8.2 Não Usou`, `1.8.3`, `1.9 Relat. s/ MANTIS` |
| DISA não, RP não, RC sim | `1` + `1.6.2 Não Usou` + `1.6` → `1.8.2 Não Usou` + `1.8.3 Usou` + `1.8` → `1.10 Concluído: Memo DEPROC` | `1`, `1.6.2 Não Usou`, `1.8.2 Não Usou`, `1.8.3 Usou`, `1.10 Concluído: Memo DEPROC` |
| DISA não, RP não, RC não | `1` + `1.6.2 Não Usou` + `1.6` → `1.8.2 Não Usou` + `1.8.3 Não Usou` + `1.8` → `1.10 Aguarda APIS: Sem Uso` | `1`, `1.6.2 Não Usou`, `1.8.2 Não Usou`, `1.8.3 Não Usou`, `1.10 Aguarda APIS: Sem Uso` |
| Vindo do fluxo ALT 1 | `1` + `1.0` → (um dos caminhos acima ou abaixo, do início) | como no caminho seguido |
| Parado pelo memo da APIS | `1` + `1.5` (um dos dois) | `1`, `1.5` |
| Parado pela base APIS | `1` + `1.2.1` + `1.6.1` | `1`, `1.2.1`, `1.6.1` |
| Parado pelo período dos dependentes | `1` + `1.6.2` + `1.6` + `1.1` → `1.7` | `1`, `1.6.2`, `1.1`, `1.7` |
| VELHO | `0` (+ o que já tinha; o `1.0` sai) | `0`, … |

### 1. Script principal (`main.py`)

**Início**

1. Lê `dados/inputs/processos_nao_processados.xlsx` (aba
   `fluxo`, coluna `num_sei`).
2. Carrega a base DISA, a base APIS e as bases do MANTIS.
3. Faz login no SEI.

**Para cada processo**

1. Abre o processo, lista a árvore e lê os marcadores **do SEI** (tudo
   fica no registro).
2. Roteamento (`_tratar`). **Nenhum marcador é adicionado aqui**, exceto o
   `1` e o `0` (em `_separar_velho`):

| # | Pergunta | Se sim |
|---|---|---|
| 1 | Marcadores inconsistentes (`conferir_marcadores`, [regras](#marcadores-tagspy))? | Erro, antes de qualquer ação. `prox_acao` = Verificar marcadores inconsistentes (corrigir no SEI) |
| 2 | VELHO pelos marcadores (`0` ou `1.3 Memos DISA e DEPROC`)? | `_separar_velho`: com `MANUAL`/`ASSINADO`, `prox_acao` = Fora do escopo; senão **➕ `0`** (se faltar), `prox_acao` = VELHO: não processado. Nos dois casos, **➖ `1.0`** (se tiver). **TODO**: fluxo do VELHO |
| 3 | Estado de parada (`1.5`, `1.6.1`, `1.7`, `1.9 - Aguarda DISA`, `1.10 - Aguarda APIS: Sem Uso`; versão anterior: `1.8.1`, `1.9 Memo DISA`)? | Erro: processo parado. `prox_acao` = Aguardar resposta ao memo enviado. **TODO**: processamento depois da resposta |
| 4 | Estado de conclusão (`1.10`)? | Concluído. `prox_acao` = assinar os memos correspondentes e encaminhar |
| 5 | Sem estado com `1.3 Memo DEPROC`? | Concluído na versão anterior. `prox_acao` = Assinar memo DEPROC e encaminhar |
| 6 | VELHO pelos memos da GEACS (`encontrar_memos_velho`, [regra](#processo-velho))? | `_separar_velho` (como no 2). Par sem data legível: erro, sem ação |
| 7 | **Não** tem `1`? | **➕ `1`** e [seção 2](#2-fluxo-processar_novo) do início (inclusive com documento da GEACS ou com o antigo `2`) |
| — | (nenhuma das anteriores) | [Seção 2](#2-fluxo-processar_novo), do início (sem estado ou com `1.0`, vindo do ALT 1) ou retomando (`1.6`, `1.8`) |

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
   para dependentes. Primeiro procura o modelo com período por dependente
   (linha `Período de apuração do dependente:`): se for ele, os períodos
   de cada dependente são extraídos e não há período variável. Senão,
   analisa como novo_novo.
   - **Formato inválido** (modelo com período por dependente incompleto ou
     qualquer outro modelo diferente do novo_novo)? Cria
     `MemoApisFormatoInvalido` (bloco `7730341`), **➕ `1.5 - Aguarda APIS:
     Formato Inválido`**, `prox_acao` = Assinar memo à APIS (formato do
     memorando inválido) e encaminhar. Motivo na coluna
     `motivo_formato_invalido`. Fim.
3. `verificar_base_apis`: procura titular e dependentes **só na base
   APIS**, com ou sem DV (matrícula em formato inválido ou ambígua: erro).
   - **Faltou matrícula?** **➕ `1.2.1 - Mat. N Encontradas Base APIS`**,
     memo à APIS (`incluir_memo_apis_mat_nao_encontradas`; bloco
     `7711907`), **➕ `1.6.1 - Aguarda APIS: Matrículas`**, `prox_acao` =
     Assinar memo à APIS (matrículas não encontradas) e encaminhar. Fim.
   - **Encontrou todas, mas o processo tem `1.2.1`** (base corrigida)?
     **➖ `1.2.1`** (`remover_tag`) e o fluxo segue.
4. `avaliar_uso_rede_propria_disa`: uso da rede própria na base DISA (fora
   dela = não usou).
   - **➕ `1.6.2 - Base DISA: Usou RP`** (alguém com SIM) ou **➕ `1.6.2 -
     Base DISA: Não Usou RP`**.
   - **➕ `1.6 - Avaliado Uso Rede Própria DISA`** (se o estado ainda não
     passou dele).
5. **Há período variável para dependentes?** (nunca no modelo com período
   por dependente) Sim: **➕ `1.1`**,
   `MemoApisPeriodoDependentes` (bloco `7730905`), **➕ `1.7 - Aguarda APIS:
   Período Deps`**, `prox_acao` = Assinar memo à APIS (período dos
   dependentes) e encaminhar. Fim.
6. `avaliar_uso_rede_propria_mantis` (período do titular ou, no modelo com
   período por dependente, o de cada dependente; rede própria e
   rede credenciada, registradas na planilha de controle; colunas
   `caso_disa_mantis` e `mats_uso_mantis_alem_disa`). O memo do caso
   ([tabela](#decisão-base-disa--mantis)) é montado (texto pendente ou
   bloco `None` param aqui).
   - **➕ `1.8.2 - MANTIS: Usou RP`** ou **➕ `1.8.2 - MANTIS: Não Usou RP`**.
   - **➕ `1.8.3 - MANTIS: Usou RC`** ou **➕ `1.8.3 - MANTIS: Não Usou RC`**.
   - **➕ `1.8 - Avaliado Uso Rede Própria MANTIS`** (se o estado ainda não
     passou dele).
7. Relatórios RP e RC em PDF de quem usou (em todos os casos; sem
   atendimento, nada é anexado). O número SEI dos RP vai para os memos à
   DISA de validação, e o dos RC, para o memo DEPROC.
8. **Base DISA × MANTIS** (processo inteiro):
   - **DISA sim, MANTIS RP sim**: `MemoDisaValidarConsta`, **➕ `1.9 -
     Aguarda DISA: Validar (Consta)`**; `prox_acao` = Assinar memo à DISA
     (validar e complementar) e encaminhar. Fim;
   - **DISA não, MANTIS RP sim**: `MemoDisaValidarNaoConsta`, **➕ `1.9 -
     Aguarda DISA: Validar (N Consta)`**; `prox_acao` = Assinar memo à DISA
     (validar; não consta na base DISA) e encaminhar. Fim;
   - **DISA sim, MANTIS RP não**: `MemoDisaSemMantisSolicitaRelatorio`,
     **➕ `1.9 - Aguarda DISA: Relat. s/ MANTIS`**; `prox_acao` = Assinar
     memo à DISA (sem MANTIS: solicita relatório) e encaminhar. Fim;
   - **DISA não, MANTIS RP não, MANTIS RC sim**: `MemoDeproc` (todos os
     beneficiários; cita os relatórios RC; bloco `7697744`), **➕ `1.10 -
     Concluído: Memo DEPROC`**; `prox_acao` = Assinar memo DEPROC e
     encaminhar;
   - **DISA não, MANTIS RP não, MANTIS RC não** (nenhum uso):
     `MemoApisSemUso` (bloco `BLOCO_MEMO_APIS_SEM_USO`), **➕ `1.10 - Aguarda
     APIS: Sem Uso`**; `prox_acao` = Assinar memo à APIS (nenhum uso nas
     bases) e encaminhar. Fim.

Em todos os finais com memo, o script relê a árvore para obter o número
SEI dos memos criados (colunas `<memo>_sei`; falha só gera log). Os três
memos à DISA usam as mesmas colunas `memo_disa_*`.

Se o script falhar entre criar um relatório ou memo e adicionar o
marcador, a próxima execução retoma do estado: o relatório (pelo nome) e
o memo (pelo assunto) já na rodada não são recriados. Se falhar entre
adicionar o estado novo e remover o anterior, a próxima execução encontra
dois estados (erro da conferência, pergunta 1 da seção 1).

---

## Fluxo alternativo ALT 1

`poetry run task run_alt_1` (`main_alt_1.py`). Insere nos processos o PDF
das planilhas de utilização e os deixa aguardando o fluxo normal: não avalia
bases e não cria memos. Lê a mesma aba `fluxo` de
`dados/inputs/processos_nao_processados.xlsx`.

Para cada processo:

1. Lê os marcadores, confere se o `1` e o `1.0` existem no SEI
   (`garantir_marcadores_no_sei`; faltando, nada é inserido) e lista a
   árvore.
2. Procura as planilhas pelas três primeiras palavras do nome na árvore:
   `Planilha Utilização Titular`, `Planilha Utilização Dependentes` e
   `Anexo RELAÇÃO ATENDIMENTO`. Os nomes são digitados à mão: acentos,
   maiúsculas e preposições são ignorados, `Tit.` e `Dep.` valem como
   `Titular` e `Dependentes`, e cada palavra é comparada com
   similaridade de 80% (`Anexo RELACAO ANTENDIMENTOS` é aceito; `Anexo RELAÇÃO
   PAGAMENTO`, não).
   - **Nenhuma?** `prox_acao` = ALT 1: nenhuma planilha no processo
     (verificar), sem marcador. Fim.
3. Para cada planilha cujo PDF ainda não está na árvore:
   - abre o documento, o que inicia o download, para
     `dados/fluxo_alt_1/planilhas_baixadas/<nº SEI>_<nome original>`;
   - lê a primeira aba; titular em `NOME_BENEFICIARIO` e
     `MATRICULA_BENEFICIARIO` (valor único). A linha `TOTAL` do Anexo é
     removida. `DAT_ATENDIMENTO` é data do Excel ou texto `DD/MM/AAAA`; sem
     data válida, com coluna faltando ou sem atendimentos: `ErroAvaliacao`.
     Sem valor: conta como 0. Só `.xlsx`;
   - gera o PDF (`transformar_xls_em_pdf`), em
     `dados/fluxo_alt_1/pdfs/<nº SEI da planilha>/`, no layout dos relatórios do
     MANTIS (o de dependentes não tem `PROCEDIMENTO`). O Anexo tem modelo
     próprio, baseado no de dependentes: título `Relatório de Utilização Por
     Beneficiário(s)`, sem a linha do titular no cabeçalho, com as colunas
     `MATRICULA BENEFICIARIO` e `NOME BENEFICIARIO`, e aceita vários
     beneficiários;
   - insere o documento externo (`anexar_pdf`): tipo `PDF`, número
     `Utilização <Tit.|Dep.> - <matrícula do titular> - SEI <nº SEI da
     planilha>`, Nato-digital, Restrito, Informação Pessoal.
4. **Já tem estado** (exceto o `1.0`), é VELHO pelos marcadores ou tem `1.3
   Memo DEPROC`? Continua onde estava, sem marcador novo (adicionar o `1.0`
   apagaria o estado). `prox_acao` = ALT 1: PDFs inseridos; processo mantido
   no estado atual.
5. Senão: **➕ `1`** (se faltar), **➕ `1.0 - Aguarda Script: Fluxo Normal`**
   (se faltar), `prox_acao` = ALT 1: PDFs inseridos; aguarda o fluxo normal.

Depois, na execução do `main.py`, o processo com `1.0` segue a [seção
2](#2-fluxo-processar_novo) do início, e o próximo estado substitui o `1.0`.
A separação do VELHO vem antes: se os memos da GEACS identificarem o VELHO,
ele recebe o `0`, perde o `1.0` e não é processado. Os PDFs do ALT 1 ficam no
processo como histórico: o fluxo normal anexa os relatórios do MANTIS e os
memos citam só estes.

- Anexo: o PDF se chama `Utilização Ben. - <matrícula>` ou, com vários
  beneficiários, `Utilização Ben. - <primeira matrícula da planilha> e mais
  <quantidade das outras>`, sem o número SEI. Por isso
  ele é sempre baixado, e só depois procurado na árvore pelo nome exato; os
  Anexos vêm depois das planilhas de titular e dependentes. Dois Anexos do
  processo com o mesmo nome de PDF: `ErroAvaliacao`, antes de inserir qualquer
  Anexo. PDF de Anexo no modelo antigo (`Utilização Tit. - ... - SEI <nº do
  Anexo>`) não conta como pronto: o novo é inserido e o antigo vai para a
  coluna `pdfs_antigos_a_excluir` (o script não exclui; excluir no SEI).
- Retomada (titular e dependentes): o número SEI da planilha está no nome do PDF. Procura em toda a
  árvore (não há rodada); PDF já presente não é baixado nem inserido de novo.
  Um erro para o processo, com o que já foi inserido mantido; a próxima
  execução continua da planilha que falhou.
- Planilha de controle: `script` = `alt_1`, `fluxo` = `ALT 1 - SOMENTE
  INSERIR PDF`, colunas `planilhas_sei`, `pdfs_incluidos`, `pdfs_na_arvore` e `pdfs_antigos_a_excluir`.
  Na aba `processos`, a linha do processo fica com a última passagem
  (`fluxo` e `prox_acao` do ALT 1), mas as colunas de resultado do fluxo
  principal não são gravadas (`_CAMPOS_SO_FLUXO_PRINCIPAL`) e continuam lá.
- Log: `logs/<data>_execucao_alt_1.log`.

---

## Fluxo PDF

`poetry run task run_pdf` (`main_fluxo_pdf.py`). É o [ALT 1](#fluxo-alternativo-alt-1)
sem o download, para as planilhas que o Chrome não baixa: elas são colocadas à
mão em `dados/fluxo_pdf/planilhas`. Lê a mesma aba `fluxo` de
`dados/inputs/processos_nao_processados.xlsx`.

- Nome do arquivo: número do processo com `_` no lugar da barra, `-` e o nome
  do documento na árvore (`2010.01.0082953_2024-75-Anexo RELAÇÃO
  ATENDIMENTOS.xlsx`). Os `:Zone.Identifier` são ignorados.
- Para cada processo: lê os marcadores, confere se o `1` e o `1.0` existem no
  SEI e lista a árvore, como no ALT 1. Depois:
  1. **Nenhum arquivo do processo na pasta?** `prox_acao` = Fluxo PDF: nenhuma
     planilha na pasta (verificar), sem marcador. Fim.
  2. Confere todos os arquivos antes de inserir qualquer PDF. O nome precisa
     ser dos três padrões do ALT 1 (`Planilha Utilização Titular`, `Planilha
     Utilização Dependentes`, `Anexo RELAÇÃO ATENDIMENTO`, sem aceitar a
     falta do `Anexo`) e do documento na árvore (nome inteiro; acento, maiúsculas e
     espaços são ignorados). Fora do padrão, sem documento ou com dois
     documentos do mesmo nome: `ErroAvaliacao`, sem inserir nada.
  3. Insere os PDFs como no ALT 1: mesmo layout, mesmo nome (com o número SEI
     do documento da árvore), mesma retomada. Um PDF que o ALT 1 já inseriu não
     é duplicado. Arquivos em `dados/fluxo_pdf/pdf/<nº SEI da planilha>/`.
  4. Marcadores como nos passos 4 e 5 do ALT 1, com as `prox_acao` `Fluxo PDF:
     PDFs inseridos; ...`.
- Planilha de controle: `script` = `fluxo_pdf`, `fluxo` = `FLUXO PDF -
  PLANILHAS DA PASTA`, mesmas colunas e regras do ALT 1. Processo sem arquivo
  na pasta também atualiza `fluxo` e `prox_acao` da linha na aba `processos`.
- Log: `logs/<data>_execucao_fluxo_pdf.log`.

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
  `memos_apis_geacs_sei`, `modelo_memo_apis` (`periodo_por_dependente` ou
  `novo_novo`), `motivo_formato_invalido`,
  `memo_apis_sem_memo_sei`, `memo_apis_formato_invalido_sei`,
  `memo_apis_periodo_deps_sei`, `memo_apis_sem_uso_sei`, `memo_disa_sei`, `memo_deproc_sei`,
  `relatorios_incluidos`, `relatorios_na_arvore`, `marcadores_sei` (lidos
  no início), `marcadores_adicionados`, `marcadores_removidos` e
  `marcadores_finais`.
- Base DISA: `tit_usou`, `deps_que_usaram`, `deps_que_nao_usaram`.
- MANTIS: `tit_usou_mantis_rede_propria`,
  `tit_valor_total_uso_mantis_rede_propria`,
  `deps_que_usaram_mantis_rede_propria`,
  `deps_valor_total_uso_mantis_rede_propria`, as mesmas para
  `rede_credenciada`, `mats_uso_mantis_alem_disa` e `caso_disa_mantis`.
- `tem_periodo_var_deps` (sim/não) e `periodos_por_dependente` (modelo com
  período por dependente: `555: 01/2024 a 06/2024; ...`).
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

- Confirmar no SEI real a remoção de marcadores (`remover_marcador` da
  `sei_automacao`): troca de estado e de par e remoção do `1.2.1`.
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
  MANTIS: Não Usou RP`, `1.8.3 - MANTIS: Usou RC`, `1.8.3 - MANTIS: Não
  Usou RC`, `1.9 - Aguarda DISA: Validar (Consta)`, `1.9 - Aguarda DISA:
  Validar (N Consta)`, `1.9 - Aguarda DISA: Relat. s/ MANTIS` e `1.10 -
  Aguarda APIS: Sem Uso`.
  Todos com o prefixo `Script v2 - `, idênticos aos de `tags.py`.
- **TODO**: cadastrar no SEI o marcador `Script v2 - 1.0 - Aguarda Script:
  Fluxo Normal` antes de rodar o ALT 1 (sem ele, nenhum PDF é inserido).
- ALT 1: confirmar na primeira execução que abrir a planilha na árvore inicia
  o download sem pedir permissão do Chrome para vários downloads, que o PDF
  entra no fim da árvore e que o nome real dos documentos bate com o padrão.
- **TODO**: blocos dos três memos à DISA (`BLOCO_MEMO_DISA_*`) e do memo
  à APIS sem uso (`BLOCO_MEMO_APIS_SEM_USO`) em `constantes.py`, hoje
  `None`.
- **TODO**: o `MemoDeproc` tem duas versões. Só rede credenciada
  (`ASSUNTO_MEMO_DEPROC`): é a do fluxo atual. Duas redes
  (`ASSUNTO_MEMO_DEPROC_DUAS_REDES`, com `doc_relatorio_disa` e
  `doc_manifestacao_disa`): depende do processamento do retorno da DISA,
  ainda não implementado. Confirmar o assunto e o texto da versão só com a
  rede credenciada. `PADRAO_ASSUNTO_MEMO_DEPROC` aceita os dois assuntos e
  o anterior.
- **TODO**: `MemoApisComTodasAsInformacoes` depende do processamento do
  retorno da DISA e da DEPROC, ainda não implementado. Confirmar no SEI real
  que as tabelas são salvas (a `sei_automacao` não trata tabelas; o memo
  manda o HTML no formato do editor do SEI, fora do `<p>`).
- **TODO**: fluxo do processo VELHO (`main._separar_velho`).
- Confirmar com um memorando real que `obter_conteudo_doc` devolve as
  linhas `Matrícula do dependente` e `Período de apuração do dependente`
  separadas (o período é lido até o fim da linha).
- **TODO**: confirmar que o pedido de "atualização do levantamento de
  utilização" é o que distingue o modelo novo_novo do novo_velho
  (`_PADRAO_ATUALIZACAO_LEVANTAMENTO` em `extrator_dados_ui.py`).
- **TODO**: usar as planilhas completas do MANTIS. As planilhas de exemplo atuais ainda têm as colunas
  antigas (`MATRICULA_BENEFICIARIO`, `DAT_ATENDIMENTO`, `VAL_PAGAR`) e não
  carregam.
- **TODO**: processamento dos processos parados (`1.5`, `1.6.1`, `1.7`,
  `1.9 - Aguarda DISA`, `1.10 - Aguarda APIS: Sem Uso`; versão anterior
  `1.8.1` e `1.9 Memo DISA`) depois
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
  o memo à APIS; se agora está na base, o `1.2.1` é removido e o fluxo
  segue.
- A planilha de controle, os backups, os PDFs (`dados/utilizacoes`) e os
  logs têm nomes e matrículas (LGPD). Restrinja o acesso a essas pastas.
