"""Gera docs/fluxo.drawio: uma aba por fluxo (task do pyproject.toml).

- geacs_inicial (run_geacs_inicial): o fluxo completo, uma coluna por função,
  lidas da esquerda para a direita (1 → 4); a coluna da direita detalha as
  funções chamadas em vários pontos;
- geacs_resp_* (run_geacs_resp_apis / _disa / _deproc, TODO: não montados);
- geacs_adc_pdf_ant_aut, geacs_adc_pdf_ant_man, geacs_canc_memo_deproc_ant,
  geacs_verificar_marcadores;
- deproc_calcula_copa e deproc_excluir_docs (na unidade da DEPROC).
 Em cada coluna o
caminho principal desce reto; os desvios saem para a direita e terminam ali
(não voltam). Caixas laranja (▶) indicam a chamada de outra coluna.
"""

import math
import re
import sys
from html import escape

# Uso: python docs/gerar_fluxo.py docs/fluxo.drawio
SAIDA = sys.argv[1]

# --- estilos ------------------------------------------------------------------

_BASE = 'whiteSpace=wrap;html=1;fontSize=12;'
ESTILOS = {
    'terminal': 'rounded=1;arcSize=50;fillColor=#f5f5f5;strokeColor=#666666;' + _BASE,
    'step': 'rounded=1;fillColor=#ffffff;strokeColor=#999999;' + _BASE,
    'func': 'rounded=1;fillColor=#dae8fc;strokeColor=#6c8ebf;' + _BASE,
    'goto': 'rounded=1;fillColor=#ffe6cc;strokeColor=#d79b00;strokeWidth=2;fontStyle=1;' + _BASE,
    'decision': 'rhombus;fillColor=#fff2cc;strokeColor=#d6b656;' + _BASE,
    'marker': 'shape=hexagon;perimeter=hexagonPerimeter2;size=0.06;fillColor=#d5e8d4;strokeColor=#82b366;strokeWidth=2;fontStyle=1;' + _BASE,
    'removed': 'shape=hexagon;perimeter=hexagonPerimeter2;size=0.06;fillColor=#fff4e5;strokeColor=#d79b00;strokeWidth=2;dashed=1;fontColor=#8a5a00;' + _BASE,
    'memo': 'rounded=1;fillColor=#e1d5e7;strokeColor=#9673a6;strokeWidth=2;' + _BASE,
    'pdf': 'shape=document;boundedLbl=1;size=0.15;fillColor=#e1d5e7;strokeColor=#9673a6;strokeWidth=2;' + _BASE,
    'error': 'rounded=1;fillColor=#f8cecc;strokeColor=#b85450;strokeWidth=2;' + _BASE,
    'caso': 'rounded=1;fillColor=#1f4e79;strokeColor=#10314f;strokeWidth=2;fontColor=#ffffff;' + _BASE,
    'note': 'shape=note;size=14;align=left;verticalAlign=top;spacing=8;fillColor=#fffde7;strokeColor=#c9b458;' + _BASE,
}
ESTILO_COLUNA = 'swimlane;html=1;whiteSpace=wrap;fontSize=13;rounded=1;arcSize=1;collapsible=0;container=1;strokeWidth=2;verticalAlign=top;'
COR_COLUNA = {
    'fluxo': 'fillColor=#dae8fc;strokeColor=#6c8ebf;swimlaneFillColor=#fbfcfe;',
    'aux': 'fillColor=#ffe6cc;strokeColor=#d79b00;swimlaneFillColor=#fffaf3;',
}
ESTILO_SETA = 'edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;strokeColor=#555555;fontSize=11;fontStyle=1;'
ESTILO_SETA_ERRO = ESTILO_SETA.replace('#555555', '#b85450') + 'fontColor=#b85450;'

LARGURA_PRINCIPAL, LARGURA_LADO, LARGURA_CASO = 330, 270, 240
PAD, GAP, VGAP, GAP_CASO = 24, 70, 28, 26

_ids = iter(range(10, 10**6))
_setas: list[str] = []


def _novo_id() -> str:
    return f'c{next(_ids)}'


def _linhas(texto: str, largura: float, fator: float = 1.0) -> int:
    util = max(40, (largura - 24) * fator)
    total = 0
    for parte in re.split(r'<br\s*/?>', texto):
        limpo = re.sub(r'<[^>]+>', '', parte)
        limpo = limpo.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        total += max(1, math.ceil(len(limpo) * 6.9 / util))
    return total


def _seta(origem, destino, rotulo='', pontos=''):
    estilo = (ESTILO_SETA_ERRO if destino.tipo == 'error' else ESTILO_SETA) + pontos
    _setas.append(
        f'<mxCell id="{_novo_id()}" value="{escape(rotulo)}" style="{estilo}" edge="1" parent="1" source="{origem.id}" target="{destino.id}"><mxGeometry relative="1" as="geometry"/></mxCell>'
    )


ABAIXO = 'exitX=0.5;exitY=1;entryX=0.5;entryY=0;'
DIREITA = 'exitX=1;exitY=0.5;entryX=0;entryY=0.5;'

# --- elementos ----------------------------------------------------------------


class No:
    def __init__(self, tipo, texto, largura=None):
        self.tipo, self.texto = tipo, texto
        self.id = _novo_id()
        self.w = largura or LARGURA_PRINCIPAL
        if tipo == 'decision':
            self.h = max(90, _linhas(texto, self.w, 0.55) * 16 + 56)
        else:
            self.h = max(40, _linhas(texto, self.w, 0.9 if tipo in {'marker', 'removed'} else 1.0) * 16 + (30 if tipo == 'pdf' else 18))
        self.altura = self.h
        self.largura_total = self.w

    def emitir(self, saida, pai, x, y):
        saida.append(
            f'<mxCell id="{self.id}" value="{escape(self.texto)}" style="{ESTILOS[self.tipo]}" vertex="1" parent="{pai}">'
            f'<mxGeometry x="{x:.0f}" y="{y:.0f}" width="{self.w:.0f}" height="{self.h:.0f}" as="geometry"/></mxCell>'
        )

    def ligar(self, prox):
        if prox is not None and self.tipo not in {'terminal', 'error'}:
            _seta(self, prox, '', ABAIXO)


class Pergunta(No):
    """Losango no caminho principal; o desvio sai para a direita e termina."""

    def __init__(self, texto, lado, rotulo='Sim', segue='Não', largura=230):
        super().__init__('decision', texto, largura=largura)
        self.lado = [_ajustar(i, LARGURA_LADO) for i in lado]
        self.rotulo, self.segue = rotulo, segue
        self.altura = max(self.h, sum(i.h for i in self.lado) + VGAP * (len(self.lado) - 1))
        self.largura_total = LARGURA_PRINCIPAL + GAP + LARGURA_LADO

    def emitir(self, saida, pai, x, y):
        super().emitir(saida, pai, x + (LARGURA_PRINCIPAL - self.w) / 2, y)
        ly = y + max(0, (self.h - self.lado[0].h) / 2)
        for item in self.lado:
            item.emitir(saida, pai, x + LARGURA_PRINCIPAL + GAP, ly)
            ly += item.h + VGAP

    def ligar(self, prox):
        if prox is not None:
            _seta(self, prox, self.segue, ABAIXO)
        _seta(self, self.lado[0], self.rotulo, DIREITA)
        for a, b in zip(self.lado, self.lado[1:]):
            a.ligar(b)


class Casos(No):
    """Losango que abre caminhos lado a lado; todos terminam em `fim`."""

    def __init__(self, texto, caminhos, fim):
        super().__init__('decision', texto, largura=300)
        self.caminhos = [(rotulo, [_ajustar(i, LARGURA_CASO) for i in itens]) for rotulo, itens in caminhos]
        self.fim = fim
        alto = max(sum(i.h for i in itens) + VGAP * (len(itens) - 1) for _, itens in self.caminhos)
        self.largura_total = len(self.caminhos) * LARGURA_CASO + (len(self.caminhos) - 1) * GAP_CASO
        self.topo_caminhos = self.h + 60
        self.altura = self.topo_caminhos + alto + 60 + fim.h

    def emitir(self, saida, pai, x, y):
        centro = x + self.largura_total / 2
        super().emitir(saida, pai, centro - self.w / 2, y)
        for n, (_, itens) in enumerate(self.caminhos):
            cy = y + self.topo_caminhos
            for item in itens:
                item.emitir(saida, pai, x + n * (LARGURA_CASO + GAP_CASO), cy)
                cy += item.h + VGAP
        self.fim.emitir(saida, pai, centro - self.fim.w / 2, y + self.altura - self.fim.h)

    def ligar(self, prox):
        for rotulo, itens in self.caminhos:
            _seta(self, itens[0], rotulo, ABAIXO)
            for a, b in zip(itens, itens[1:]):
                a.ligar(b)
            _seta(itens[-1], self.fim, '', ABAIXO)
        self.fim.ligar(prox)


def _ajustar(item, largura):
    item.w = largura
    novo = No(item.tipo, item.texto, largura)
    item.h = item.altura = novo.h
    return item


class Coluna:
    def __init__(self, titulo, descricao, itens, cor='fluxo'):
        self.titulo, self.descricao, self.itens, self.cor = titulo, descricao, itens, cor
        self.id = _novo_id()
        self.interno = max(i.largura_total for i in itens)
        self.w = self.interno + 2 * PAD
        self.cabecalho = 34 + _linhas(descricao, self.w) * 16
        self.h = self.cabecalho + PAD + sum(i.altura for i in itens) + VGAP * (len(itens) - 1) + PAD

    def emitir(self, saida, x, y):
        valor = f'<b style="font-size:16px">{self.titulo}</b><br><span style="font-size:12px">{self.descricao}</span>'
        estilo = ESTILO_COLUNA + COR_COLUNA[self.cor] + f'startSize={self.cabecalho:.0f};'
        saida.append(
            f'<mxCell id="{self.id}" value="{escape(valor)}" style="{estilo}" vertex="1" parent="1">'
            f'<mxGeometry x="{x:.0f}" y="{y:.0f}" width="{self.w:.0f}" height="{self.h:.0f}" as="geometry"/></mxCell>'
        )
        cy = self.cabecalho + PAD
        for item in self.itens:
            # Itens simples centrados sob o losango do caminho principal
            ix = PAD + (self.interno - item.largura_total) / 2 if isinstance(item, Casos) else PAD + (LARGURA_PRINCIPAL - item.w) / 2 if not isinstance(item, Pergunta) else PAD
            item.emitir(saida, self.id, ix, cy)
            cy += item.altura + VGAP
        for item, prox in zip(self.itens, [*self.itens[1:], None]):
            item.ligar(prox)


def T(t):
    return No('terminal', t)


def S(t):
    return No('step', t)


def F(nome, descricao='', chama=''):
    texto = f'<font face="Courier New"><b>{escape(nome)}</b></font>'
    if descricao:
        texto += f'<br>{descricao}'
    if chama:
        texto += f'<br><font color="#555555" style="font-size:11px">chama: <font face="Courier New">{escape(chama)}</font></font>'
    return No('func', texto)


def IR(t):
    return No('goto', '▶ ' + t)


def M(t):
    return No('marker', '➕ ' + t)


def R(t):
    return No('removed', '➖ ' + t)


def MEMO(t, bloco):
    return No('memo', f'📄 <b>{t}</b><br>no bloco {bloco}')


def CASO(t, descricao):
    return No('caso', f'<b>{t}</b><br>{descricao}')


def PDF(t):
    return No('pdf', '📎 ' + t)


def E(t):
    return No('error', t)


def N(t, largura=None):
    return No('note', t, largura)


def P(texto, lado, rotulo='Sim', segue='Não', largura=230):
    return Pergunta(texto, lado, rotulo, segue, largura)


# --- conteúdo -----------------------------------------------------------------

col_main = Coluna(
    '1 · main() e _processar_linha()',
    'Carrega as bases, faz login e passa cada processo pelo fluxo. Um erro nunca interrompe os demais processos',
    [
        T('Início'),
        F('configurar_logging()', 'Cria as pastas e o log da execução'),
        F('carregar_bases() · carregar_bases_mantis()', 'Lê a aba geacs_inicial de processos_a_processar.xlsx, a base DISA, a base APIS e o MANTIS (rede própria e credenciada)'),
        F('PlanilhaControleGeral() · abrir_sei()', 'Lê a planilha de controle, faz login no SEI e troca para a unidade da GEACS (alterar_unidade_sei: trocar_unidade da sei_automacao)'),
        S('<b>Para cada processo</b>'),
        F('_processar_linha()', (
            'Abre o processo e lê os marcadores do SEI. Unidade sem acesso (UnidadeSemAcessoException): '
            'registrar_sem_acesso(), prox_acao = Verificar acesso da unidade ao processo, sem ação no SEI'
        ), chama='acessar_processo, registrar_tags'),
        F('tem_incluir_documento()', 'Sem o botão Incluir Documento = processo fechado no setor. Só registra: quem decide reabrir é _tratar() (coluna 2)'),
        F('registrar_arvore()', 'Lê a árvore do processo'),
        IR('_tratar() — coluna 2'),
        F('conferir_marcadores()', 'De novo, no fim da passagem (se não houve erro)'),
        E('<b>Erro levantado em qualquer coluna?</b><br><font face="Courier New">registrar_erro()</font>: tipo_erro, erro e prox_acao = Verificar erro (ou a já definida). Inesperado: + traceback e recarrega a página (tela presa não derruba os próximos processos)'),
        F('controle.registrar()', 'Regrava a planilha de controle (abas processos e historico) depois de cada processo'),
        P('Há mais processos?', [IR('volta a "Para cada processo"')]),
        F('log_resumo()', 'Fecha o navegador e loga o resumo'),
        T('Fim'),
    ],
)
# O erro não encerra a execução: a passagem segue para a planilha
col_main.itens[11].ligar = lambda prox, no=col_main.itens[11]: _seta(no, prox, '', ABAIXO)

col_tratar = Coluna(
    '2 · _tratar()',
    'Separa o processo VELHO e roteia pelos marcadores lidos do SEI. Só adiciona o marcador 01 (e o 00, em _separar_velho); o resto é decidido em processar_novo()',
    [
        F(
            'conferir_marcadores()',
            'A combinação de marcadores é possível no fluxo?<br>'
            '• no máximo um marcador de estado (★)<br>'
            '• informativo só com estado compatível<br>'
            '• 01.06.1 - No Bloco APIS: Matrículas exige 01.02.1 - Mat. N Encontradas Base APIS<br>'
            '• 01.07 - No Bloco APIS: Período Deps exige 01.01 - Período Variável p/ Dependentes<br>'
            '• os de uso da RP / RC (01.06.2, 01.08.2, 01.08.3, versão anterior) não são conferidos<br>'
            '• cada "Aguarda" manual (.1) segue a mesma regra do seu "No Bloco"<br>'
            '• VELHO (00 - Processo VELHO) sem memos à DISA ou à DEPROC do fluxo atual (01.09, 01.10)…',
        ),
        P('Marcadores<br>inconsistentes?', [E('<b>MarcadoresInconsistentes</b>: nada é feito no SEI<br>prox_acao = Verificar marcadores (corrigir no SEI)')]),
        P(
            '<b>VELHO</b> pelo marcador?<br>00 - Processo VELHO',
            [IR('_separar_velho()<br><span style="font-weight:normal">à direita</span>')],
            largura=LARGURA_PRINCIPAL,
        ),
        S('<font face="Courier New">estado_atual()</font>: marcador de estado do processo'),
        P(
            'Memo no bloco (aguarda assinatura)?<br>01.05 - No Bloco APIS: Sem Memo p/ GEACS<br>01.05 - No Bloco APIS: Formato Inválido<br>'
            '01.06.1 - No Bloco APIS: Matrículas<br>01.07 - No Bloco APIS: Período Deps<br>01.09 - No Bloco DISA: Validar (Consta)<br>'
            '01.09 - No Bloco DISA: Validar (N Consta)<br>01.09 - No Bloco DISA: Relat. s/ MANTIS<br>01.10 - No Bloco DEPROC: Coparticipação<br>'
            '01.10 - No Bloco APIS: Sem Uso',
            [T('prox_acao = Assinar o memo correspondente e encaminhar<br><span style="font-weight:normal">quem assina coloca o "Aguarda" (.1) e remove o "No Bloco"</span>')],
            largura=LARGURA_PRINCIPAL,
        ),
        P(
            'Estado de parada (memo assinado)?<br>01.05.1 - Aguarda APIS: Sem Memo p/ GEACS<br>01.05.1 - Aguarda APIS: Formato Inválido<br>'
            '01.06.1.1 - Aguarda APIS: Matrículas<br>01.07.1 - Aguarda APIS: Período Deps<br>01.09.1 - Aguarda DISA: Validar (Consta)<br>'
            '01.09.1 - Aguarda DISA: Validar (N Consta)<br>01.09.1 - Aguarda DISA: Relat. s/ MANTIS<br>01.10.1 - Aguarda DEPROC: Coparticipação<br>'
            '01.10.1 - Aguarda APIS: Sem Uso (todos manuais)<br>'
            'versão anterior: 01.08.1 - Memo DISA Validar Usos MANTIS, 01.09 - Memo DISA Uso Rede Própria',
            [E('<b>Erro</b>: parado aguardando resposta ao memo<br>prox_acao = Aguardar resposta ao memo enviado<br><span style="font-weight:normal">resposta: run_geacs_resp_apis / _disa / _deproc (TODO)</span>')],
            largura=LARGURA_PRINCIPAL,
        ),
        P(
            'Estado de conclusão?<br>versão anterior: 01.10 - Concluído: Memos DISA e DEPROC',
            [T('<b>Concluído</b>, prox_acao = assinar os memos DISA e DEPROC')],
            largura=LARGURA_PRINCIPAL,
        ),
        P(
            'Já tem 01 - Tratado pelo Script<br>(e não está no 01.00)?',
            [S('Não analisa os memos: não é VELHO')],
            rotulo='Sim (pula a análise)',
        ),
        F(
            'encontrar_memos_velho()',
            'Lê <b>todos os memorandos da GEACS</b> e procura algum com "Para: IPSEMG/DISA" e/ou "Para: IPSEMG/DEPROC" (qualquer grafia depois da sigla) '
            'datado ("Belo Horizonte, 18 de setembro de 2026.") antes de 15/10/2026',
        ),
        P('Nenhum antes da data e<br>algum sem data legível?', [E('<b>ErroAvaliacao</b>: não dá para saber se é VELHO; nada é feito no SEI')]),
        P('<b>VELHO</b> pelos memos<br>da GEACS?', [IR('_separar_velho()<br><span style="font-weight:normal">à direita</span>')]),
        P(
            'Processo <b>fechado</b> no setor?',
            [
                P(
                    'Com MANUAL ou sem<br>memo da APIS para a GEACS?',
                    [E('<b>ProcessoFechadoNoSetor</b>: não reabre, nada é feito no SEI<br>prox_acao = Verificar erro')],
                ),
                F('reabrir_processo_fechado()', 'Reabre o processo na unidade (continua aberto) e relê a árvore. Coluna processo_reaberto. Não reabriu: ProcessoFechadoNoSetor', chama='reabrir_processo, listar_documentos_arvore'),
            ],
        ),
        P('Sem o marcador<br><b>01 - Tratado pelo Script</b>?', [M('01 - Tratado pelo Script'), IR('processar_novo() do início — coluna 3')]),
        IR(
            'processar_novo() — coluna 3<br><span style="font-weight:normal">do início (sem estado ou com 01.00 - Aguarda Script: Fluxo Normal, que o fluxo ADC PDF ANT AUT deixa) '
            'ou retomando de 01.06 - Avaliado Uso Rede Própria DISA ou 01.08 - Avaliado Uso Rede Própria MANTIS</span>'
        ),
    ],
)

col_processar = Coluna(
    '3 · processar_novo()',
    'Memo da APIS, base APIS e base DISA, e as paradas com memo à APIS. Na retomada, as etapas já feitas são puladas (_etapa_feita)',
    [
        F(
            'obter_dados_ui()',
            'Usa o <b>último</b> memo da APIS destinado à GEACS; os documentos depois dele são a rodada. '
            'Procura <b>primeiro o modelo com período por dependente</b> (linha <i>Período de apuração do dependente:</i>; duplas matrícula + período) e, se não for ele, analisa como novo_novo',
            chama='obter_memos_apis_para_geacs, validar_template, extrair_dados_ui',
        ),
        P(
            'Nenhum memo da APIS<br>para a GEACS?',
            [
                F('_parar_sem_memo_apis()', chama='_parar_com_memo'),
                MEMO('MemoApisSemMemo', 7730344),
                M('01.05 - No Bloco APIS: Sem Memo p/ GEACS'),
                R('estado anterior (se houver)'),
                T('prox_acao = Assinar memo à APIS (sem memorando)'),
            ],
        ),
        P(
            'Formato inválido?<br>(período por dependente incompleto,<br>não é novo_novo ou período<br>do titular inválido)',
            [
                F('_parar_formato_invalido()', chama='_parar_com_memo'),
                MEMO('MemoApisFormatoInvalido', 7730341),
                M('01.05 - No Bloco APIS: Formato Inválido'),
                R('estado anterior (se houver)'),
                T('prox_acao = Assinar memo à APIS (formato inválido)'),
            ],
        ),
        F('verificar_base_apis()', 'A existência das matrículas é conferida <b>só na base APIS</b> (a base DISA é feita a partir dela). Do memo, vêm com ou sem DV; a base APIS diz qual é a matrícula'),
        P('Matrícula em<br>formato inválido?', [E('<b>ErroAvaliacao</b>')]),
        P(
            'Faltou matrícula<br>na base APIS?',
            [
                F('_parar_nao_encontradas_base_apis()', chama='garantir_marcadores_no_sei, incluir_memo_apis_mat_nao_encontradas'),
                M('01.02.1 - Mat. N Encontradas Base APIS'),
                MEMO('MemoApisMatNaoEncontradas', 7711907),
                M('01.06.1 - No Bloco APIS: Matrículas'),
                R('estado anterior (se houver)'),
                T('prox_acao = Assinar memo à APIS (matrículas não encontradas)'),
            ],
        ),
        P(
            'Tem 01.02.1 - Mat. N Encontradas Base APIS?<br>(base corrigida)',
            [R('01.02.1 - Mat. N Encontradas Base APIS<br><span style="font-weight:normal">remove e segue o fluxo (abaixo)</span>')],
            largura=LARGURA_PRINCIPAL,
        ),
        F('_avaliar_disa()', 'Uso da rede própria na base DISA. Fora da base DISA = não usou', chama='avaliar_uso_rede_propria_disa, registrar_uso, garantir_marcadores_no_sei'),
        P('Resposta inválida<br>na base DISA?', [E('<b>ErroAvaliacao</b>')]),
        S('Resultado da base DISA (alguém usou a rede própria?) só na planilha de controle: sem marcador'),
        M('01.06 - Avaliado Uso Rede Própria DISA<br><span style="font-weight:normal">pulado na retomada; remove o estado anterior</span>'),
        P(
            'Período variável<br>para dependentes?<br><span style="font-weight:normal">(nunca no modelo com período por dependente)</span>',
            [
                F('_parar_periodo_variavel()', chama='_parar_com_memo'),
                M('01.01 - Período Variável p/ Dependentes'),
                MEMO('MemoApisPeriodoDependentes', 7730905),
                M('01.07 - No Bloco APIS: Período Deps'),
                R('01.06 - Avaliado Uso Rede Própria DISA'),
                T('prox_acao = Assinar memo à APIS (período dos dependentes)'),
            ],
        ),
        IR('_avaliar_mantis_e_criar_docs() — coluna 4'),
    ],
)

col_mantis = Coluna(
    '4 · _avaliar_mantis_e_criar_docs()',
    'MANTIS e a comparação base DISA × MANTIS, pelo processo inteiro (alguém usou). O memo à DISA depende só da rede própria (RP); '
    'a rede credenciada (RC) só separa DEPROC de APIS quando ninguém usou a RP. Cada caso tem o seu memo e o seu bloco. '
    '<b>Os relatórios RP e RC de quem usou entram em todos os casos</b>; <b>quem vai para a DISA não vai para a DEPROC</b>',
    [
        F('avaliar_uso_rede_propria_mantis()', 'Atendimentos no período do titular (no modelo com período por dependente, no de cada dependente), nas duas redes', chama='interpretar_periodo'),
        P('Período ou data<br>de atendimento<br>inválidos?', [E('<b>ErroAvaliacao</b>')]),
        F('_registrar_uso_mantis() · usos_mantis_alem_disa()', 'Planilha: uso nas duas redes, caso_disa_mantis e mats_uso_mantis_alem_disa (RP no MANTIS e fora da base DISA)'),
        S('Escolhe o memo pelo caso (abaixo) e o monta <b>antes de qualquer ação no SEI</b>'),
        P('Texto do memo<br>pendente?', [E('<b>TextoMemoPendente</b><br>nada é criado no SEI')]),
        P('Bloco do memo (DISA ou<br>APIS sem uso) não<br>configurado (None)?', [E('<b>ErroAvaliacao</b><br>nada é criado no SEI')]),
        F('garantir_marcadores_no_sei()', 'Os marcadores que serão adicionados existem no SEI?'),
        S('Uso da rede própria e da credenciada no MANTIS só na planilha de controle: sem marcador'),
        M('01.08 - Avaliado Uso Rede Própria MANTIS<br><span style="font-weight:normal">pulado na retomada; remove 01.06 - Avaliado Uso Rede Própria DISA</span>'),
        Casos(
            '<b>Base DISA × MANTIS</b><br>(rede própria; rede credenciada<br>quando ninguém usou a própria)',
            [
                (
                    'DISA sim × RP sim',
                    [
                        CASO('DISA sim × MANTIS RP sim', 'validar e complementar'),
                        PDF('PDF Utilização Tit./Dep. <b>RP</b>'),
                        PDF('PDF Utilização Tit./Dep. <b>RC</b><br>(só de quem usou)'),
                        MEMO('MemoDisaValidarConsta', 'BLOCO_MEMO_DISA_VALIDAR_CONSTA (TODO)'),
                        M('01.09 - No Bloco DISA: Validar (Consta)'),
                        R('01.08 - Avaliado Uso Rede Própria MANTIS'),
                        T('prox_acao = Assinar memo à DISA (validar e complementar)<br><b>sem DEPROC</b>'),
                    ],
                ),
                (
                    'DISA não × RP sim',
                    [
                        CASO('DISA não × MANTIS RP sim', 'validar; não consta na planilha'),
                        PDF('PDF Utilização Tit./Dep. <b>RP</b>'),
                        PDF('PDF Utilização Tit./Dep. <b>RC</b><br>(só de quem usou)'),
                        MEMO('MemoDisaValidarNaoConsta', 'BLOCO_MEMO_DISA_VALIDAR_NAO_CONSTA (TODO)'),
                        M('01.09 - No Bloco DISA: Validar (N Consta)'),
                        R('01.08 - Avaliado Uso Rede Própria MANTIS'),
                        T('prox_acao = Assinar memo à DISA (validar; não consta)<br><b>sem DEPROC</b>'),
                    ],
                ),
                (
                    'DISA sim × RP não',
                    [
                        CASO('DISA sim × MANTIS RP não', 'sem MANTIS: solicita relatório à DISA'),
                        PDF('PDF Utilização Tit./Dep. <b>RC</b><br>(só de quem usou)'),
                        MEMO('MemoDisaSemMantisSolicitaRelatorio', 'BLOCO_MEMO_DISA_SEM_MANTIS_RELATORIO (TODO)'),
                        M('01.09 - No Bloco DISA: Relat. s/ MANTIS'),
                        R('01.08 - Avaliado Uso Rede Própria MANTIS'),
                        T('prox_acao = Assinar memo à DISA (sem MANTIS: solicita relatório)<br><b>sem DEPROC</b>'),
                    ],
                ),
                (
                    'DISA não × RP não × RC sim',
                    [
                        CASO('DISA não × MANTIS RP não × MANTIS RC sim', 'só DEPROC'),
                        PDF('PDF Utilização Tit./Dep. <b>RC</b><br>(só de quem usou)'),
                        MEMO('MemoDeproc', 7697744),
                        M('01.10 - No Bloco DEPROC: Coparticipação'),
                        R('01.08 - Avaliado Uso Rede Própria MANTIS'),
                        T('prox_acao = Assinar memo DEPROC'),
                    ],
                ),
                (
                    'DISA não × RP não × RC não',
                    [
                        CASO('DISA não × MANTIS RP não × MANTIS RC não', 'nenhum uso: avisa a APIS'),
                        S('Sem relatório para anexar'),
                        MEMO('MemoApisSemUso</b> (TODO: texto)<b>', 'BLOCO_MEMO_APIS_SEM_USO (TODO)'),
                        M('01.10 - No Bloco APIS: Sem Uso'),
                        R('01.08 - Avaliado Uso Rede Própria MANTIS'),
                        T('prox_acao = Assinar memo à APIS (nenhum uso nas bases)<br><b>sem DEPROC</b>'),
                    ],
                ),
            ],
            F('_finalizar()', 'Número SEI dos memos criados (registrar_numeros_memos)'),
        ),
        T('Volta para a coluna 1<br>(planilha de controle)'),
    ],
)

# Funções usadas em vários pontos
aux = [
    Coluna(
        '_separar_velho()',
        '<b>Processo VELHO</b> (enviado à DISA e à DEPROC antes da avaliação): marcado e <b>não processado</b>. TODO: definir o fluxo do VELHO',
        [
            P('Processo fechado<br>no setor?', [E('<b>ProcessoFechadoNoSetor</b>: não reabre, nada é feito no SEI')]),
            P('Tem MANUAL?', [R('01.00 - Aguarda Script: Fluxo Normal<br><span style="font-weight:normal">se tiver</span>'), T('prox_acao = Fora do escopo (tratado manualmente)')]),
            F('garantir_marcadores_no_sei()'),
            M('00 - Processo VELHO<br><span style="font-weight:normal">se ainda não tiver</span>'),
            R('01.00 - Aguarda Script: Fluxo Normal<br><span style="font-weight:normal">se tiver</span>'),
            T('prox_acao = VELHO: não processado (fluxo ainda não definido)'),
        ],
        cor='aux',
    ),
    Coluna(
        'adicionar_tag()',
        'Única forma de adicionar marcador (cada ➕ do diagrama)',
        [
            F('adicionar_marcador()', 'sei_automacao'),
            P(
                'É de um grupo de<br>alternativos? (estado ★)',
                [F('remover_tag()', 'Remove o outro do grupo (cada ➖ do diagrama)', chama='remover_marcador')],
            ),
        ],
        cor='aux',
    ),
    Coluna(
        'adicionar_tag_se_ausente()',
        'Retomada: 00 - Processo VELHO, 01.01 - Período Variável p/ Dependentes e 01.02.1 - Mat. N Encontradas Base APIS não são adicionados de novo',
        [P('Já tem o marcador?', [S('Não faz nada')]), F('adicionar_tag()')],
        cor='aux',
    ),
    Coluna(
        'incluir_memo()',
        'Cada 📄 do diagrama. Retomada: procura o memo pelo assunto na rodada',
        [
            F('encontrar_memo_por_assunto()'),
            P('Já existe?', [S('Não recria (coluna &lt;memo&gt;_na_arvore)')]),
            F('incluir_doc_sei_memo() · inserir_bloco_ass()', 'Cria o memo e insere no bloco'),
        ],
        cor='aux',
    ),
    Coluna(
        'incluir_relatorios()',
        'Cada 📎 do diagrama. Um PDF do titular e um dos dependentes, só de quem tem atendimento',
        [
            F('encontrar_doc_por_nome()', 'Procura na rodada "PDF Utilização Tit.|Dep. RP|RC - &lt;matrícula&gt;"'),
            P('Já anexado?', [S('Não anexa de novo')]),
            F('transformar_xls_em_pdf() · incluir_doc_externo()', 'Gera o PDF e anexa: tipo PDF, Nato-digital, Restrito'),
            F('numero_sei_por_nome()', 'Relê a árvore: o número SEI dos PDFs RP é citado no memo à DISA'),
        ],
        cor='aux',
    ),
    Coluna(
        'garantir_marcadores_no_sei()',
        'Antes de criar memos e relatórios',
        [
            F('_ler_marcadores_da_unidade()', 'Tela Gerenciar Marcador, sem salvar (uma vez por execução; relida uma vez se faltar algum nome)'),
            P('Falta marcador<br>no SEI?', [E('<b>ErroAvaliacao</b>: nada é criado')]),
        ],
        cor='aux',
    ),
    Coluna(
        '_parar_com_memo()',
        'Paradas com memo à APIS e à DISA: confere o bloco → [➕ marcador anterior] → 📄 memo → ➕ marcador da parada → _finalizar()',
        [F('garantir_marcadores_no_sei() · incluir_memo() · adicionar_tag()')],
        cor='aux',
    ),
]

marcadores = N(
    '<b>Marcadores</b> (prefixo "v2: "; os da versão anterior, "v2v: "; ★ = estado: no máximo um)<br>'
    '00 - Processo VELHO<br>'
    '01 - Tratado pelo Script<br>'
    '01.01 - Período Variável p/ Dependentes<br>'
    '01.02.1 - Mat. N Encontradas Base APIS<br>'
    '★ 01.00 - Aguarda Script: Fluxo Normal (adicionado pelo fluxo ADC PDF ANT AUT)<br>'
    '★ 01.05 - No Bloco APIS: Sem Memo p/ GEACS<br>'
    '★ 01.05 - No Bloco APIS: Formato Inválido<br>'
    '★ 01.06 - Avaliado Uso Rede Própria DISA<br>'
    '★ 01.06.1 - No Bloco APIS: Matrículas<br>'
    '★ 01.07 - No Bloco APIS: Período Deps<br>'
    '★ 01.08 - Avaliado Uso Rede Própria MANTIS<br>'
    '★ 01.09 - No Bloco DISA: Validar (Consta)<br>'
    '★ 01.09 - No Bloco DISA: Validar (N Consta)<br>'
    '★ 01.09 - No Bloco DISA: Relat. s/ MANTIS<br>'
    '★ 01.10 - No Bloco DEPROC: Coparticipação<br>'
    '★ 01.10 - No Bloco APIS: Sem Uso<br>'
    '<i>Manuais, depois da assinatura (quem coloca remove o "No Bloco"):</i><br>'
    '★ 01.05.1 - Aguarda APIS: Sem Memo p/ GEACS<br>'
    '★ 01.05.1 - Aguarda APIS: Formato Inválido<br>'
    '★ 01.06.1.1 - Aguarda APIS: Matrículas<br>'
    '★ 01.07.1 - Aguarda APIS: Período Deps<br>'
    '★ 01.09.1 - Aguarda DISA: Validar (Consta)<br>'
    '★ 01.09.1 - Aguarda DISA: Validar (N Consta)<br>'
    '★ 01.09.1 - Aguarda DISA: Relat. s/ MANTIS<br>'
    '★ 01.10.1 - Aguarda DEPROC: Coparticipação<br>'
    '★ 01.10.1 - Aguarda APIS: Sem Uso<br>'
    '<i>Versão anterior:<br>'
    '01.06.2 / 01.08.2 / 01.08.3 - Usou / Não Usou RP e RC (não são mais adicionados)<br>'
    '01.02 - Avaliado Se Usou Rede Própria<br>'
    '01.02.2 - Mat. N Encontradas Base DISA (não é mais conferido)<br>'
    '01.03 - Memos DISA e DEPROC no Bloco, 01.03 - Memo DEPROC no Bloco (não são mais lidos)<br>'
    '01.04 - Memo Não Usou Rede no Bloco<br>'
    '★ 01.08.1 - Memo DISA Validar Usos MANTIS<br>'
    '★ 01.09 - Memo DISA Uso Rede Própria<br>'
    '★ 01.10 - Concluído: Memos DISA e DEPROC<br>'
    '★ 01.11 - VELHO Concluído: Memo DISA<br>'
    '★ 01.11 - VELHO Concluído: Memo DEPROC</i>',
    largura=LARGURA_PRINCIPAL + 2 * PAD + GAP + LARGURA_LADO,
)

legenda = [
    F('função()', 'o que ela faz', chama='funções que ela chama'),
    IR('outra coluna'),
    No('decision', 'Pergunta<br>(Sim → direita)'),
    CASO('caso', 'variação do fluxo'),
    M('marcador adicionado'),
    R('marcador removido'),
    MEMO('Memo', '…'),
    PDF('relatório PDF anexado'),
    E('<b>Erro</b> (registrar_erro)'),
    T('fim / prox_acao'),
]

pendencias = N(
    '<b>Pendências (TODO)</b><br>'
    '• blocos dos três memos à DISA e do memo à APIS sem uso (constantes = None)<br>'
    '• revisar os textos e assuntos dos memos com TEXTO_DEFINIDO = False<br>'
    '• fluxo do processo VELHO<br>'
    '• montar os fluxos de resposta (abas geacs_resp_*)',
    largura=460,
)

# --- outros fluxos --------------------------------------------------------------


def col_loop(task, aba, unidade, carga, ir_texto, planilha):
    """Coluna 1 dos fluxos simples: main() e _processar_linha()."""
    return Coluna(
        '1 · main() e _processar_linha()',
        f'poetry run task {task}. Um erro nunca interrompe os demais processos',
        [
            T('Início'),
            F('configurar_logging() · ler_processos_a_processar()', f'Cria o log e lê a aba {aba} de processos_a_processar.xlsx{carga}'),
            F('PlanilhaControleGeral() · abrir_sei()', f'Lê a planilha de controle, faz login no SEI e troca para a unidade {unidade} (trocar_unidade)'),
            S('<b>Para cada processo</b>'),
            P(
                'acessar_processo():<br>unidade sem acesso?',
                [E('registrar_sem_acesso(): prox_acao = Verificar acesso da unidade ao processo, sem ação no SEI')],
            ),
            IR(ir_texto),
            E('<b>Erro levantado?</b><br><font face="Courier New">registrar_erro()</font>. Inesperado: + traceback e recarrega a página'),
            F('controle.registrar()', planilha),
            P('Navegador fechado?', [T('Para o loop (resumo e driver.quit() continuam)')]),
            P('Há mais processos?', [IR('volta a "Para cada processo"')]),
            F('log_resumo()', 'Fecha o navegador e loga o resumo'),
            T('Fim'),
        ],
    )


def _erro_segue(coluna, indice):
    """O erro não encerra a execução: a passagem segue para a planilha."""
    no = coluna.itens[indice]
    no.ligar = lambda prox, no=no: _seta(no, prox, '', ABAIXO)


def col_aguardando_fluxo_normal(nome):
    return Coluna(
        '3 · deixar_aguardando_fluxo_normal()',
        'Depois dos PDFs: o processo fica aguardando o fluxo inicial (run_geacs_inicial)',
        [
            P(
                'Já tem estado (exceto 01.00)<br>ou é VELHO pelo marcador (00)?',
                [T(f'Continua onde estava, sem marcador novo<br>prox_acao = {nome}: PDFs inseridos; processo mantido no estado atual')],
            ),
            M('01 - Tratado pelo Script<br><span style="font-weight:normal">se faltar</span>'),
            M('01.00 - Aguarda Script: Fluxo Normal<br><span style="font-weight:normal">se faltar</span>'),
            T(f'prox_acao = {nome}: PDFs inseridos; aguarda o fluxo normal'),
        ],
    )


def col_inserir_pdfs(titulo, descricao, antes):
    """Inserção dos PDFs, comum ao ADC PDF ANT AUT e ao ADC PDF ANT MAN."""
    return Coluna(
        titulo,
        descricao,
        [
            *antes,
            F('transformar_xls_em_pdf()', 'PDF no layout dos relatórios do MANTIS, com a linha TOTAL. Anexo: modelo próprio, vários beneficiários'),
            F(
                '_recarregar_processo() · _anexar_pdf_com_novas_tentativas()',
                'Documento externo PDF "Utilização Tit.|Dep. - &lt;matrícula&gt; - SEI &lt;nº da planilha&gt;" (Anexo: "Utilização Ben. - ..."), Nato-digital, Restrito. Até 3 tentativas; relê a árvore antes de repetir',
            ),
            IR('deixar_aguardando_fluxo_normal() — coluna 3'),
        ],
    )


# ADC PDF ANT AUT
col_adc_aut_loop = col_loop(
    'run_geacs_adc_pdf_ant_aut',
    'geacs_adc_pdf_ant_aut',
    'da GEACS',
    '',
    'inserir_pdfs_das_planilhas() — coluna 2',
    'Linha do processo: script, fluxo e prox_acao do ADC PDF ANT AUT; planilhas_sei, pdfs_incluidos, pdfs_na_arvore, pdfs_antigos_a_excluir, processo_reaberto. Os resultados do fluxo inicial ficam como estão',
)
_erro_segue(col_adc_aut_loop, 6)
col_adc_aut = col_inserir_pdfs(
    '2 · inserir_pdfs_das_planilhas()',
    'Baixa as planilhas antigas do SEI e insere o PDF de cada uma. Retomada pelo nº SEI da planilha no nome do PDF (toda a árvore)',
    [
        F('registrar_tags() · garantir_marcadores_no_sei()', 'Confere se o 01 e o 01.00 existem no SEI (faltando, nada é inserido) e lista a árvore'),
        F(
            'encontrar planilhas',
            'Três primeiras palavras do nome: Planilha Utilização Titular, Planilha Utilização Dependentes, Anexo RELAÇÃO ATENDIMENTO (sem acento, maiúsculas e preposições; Tit./Dep.; similaridade de 80%)',
        ),
        P('Nenhuma planilha?', [T('prox_acao = ADC PDF ANT AUT: nenhuma planilha no processo (verificar), sem marcador')]),
        P('Todos os PDFs já<br>estão na árvore?', [IR('deixar_aguardando_fluxo_normal() — coluna 3')]),
        P(
            'Sem Incluir Documento<br>(fechado no setor)?',
            [F('reabrir_processo_fechado()', 'reabrir_processo da sei_automacao (coluna processo_reaberto); o processo continua aberto. Não reabriu: ProcessoFechadoNoSetor')],
            rotulo='Sim (e segue)',
        ),
        S('<b>Para cada planilha sem PDF na árvore</b>'),
        F('baixar planilha', 'Abre o documento (inicia o download) para dados/geacs_adc_pdf_ant_aut/planilhas_baixadas/. Mais de 60 s (TIMEOUT_DOWNLOAD): erro; o temporário é descartado'),
        F(
            'ler_planilha()',
            'Uma aba só (contando as ocultas); Anexo com até 20 beneficiários; linha TOTAL removida; DAT_ATENDIMENTO válida. Senão: ErroAvaliacao, sem PDF',
        ),
    ],
)
col_adc_aut_fim = col_aguardando_fluxo_normal('ADC PDF ANT AUT')

# ADC PDF ANT MAN
col_adc_man_loop = col_loop(
    'run_geacs_adc_pdf_ant_man',
    'geacs_adc_pdf_ant_man',
    'da GEACS',
    '',
    'inserir_pdfs_da_pasta() — coluna 2',
    'Linha do processo: script, fluxo e prox_acao do ADC PDF ANT MAN; mesmas colunas do ADC PDF ANT AUT',
)
_erro_segue(col_adc_man_loop, 6)
col_adc_man = col_inserir_pdfs(
    '2 · inserir_pdfs_da_pasta()',
    'O ADC PDF ANT AUT sem o download: planilhas colocadas à mão em dados/geacs_adc_pdf_ant_man/planilhas',
    [
        F('registrar_tags() · garantir_marcadores_no_sei()', 'Confere se o 01 e o 01.00 existem no SEI e lista a árvore'),
        F('arquivos do processo na pasta', 'Nome: &lt;nº do processo com _ no lugar da barra&gt;-&lt;nome do documento na árvore&gt;.xlsx'),
        P('Nenhum arquivo<br>do processo?', [T('prox_acao = ADC PDF ANT MAN: nenhuma planilha na pasta (verificar), sem marcador')]),
        P(
            'Algum arquivo fora dos três padrões,<br>sem documento na árvore<br>ou com dois do mesmo nome?',
            [E('<b>ErroAvaliacao</b>: nenhum PDF inserido')],
        ),
        S('<b>Para cada arquivo sem PDF na árvore</b> (o que o ADC PDF ANT AUT já inseriu não é duplicado)'),
        F('ler_planilha()', 'Mesmas regras do ADC PDF ANT AUT'),
    ],
)
col_adc_man_fim = col_aguardando_fluxo_normal('ADC PDF ANT MAN')

# CANC MEMO DEPROC ANT
col_canc_loop = col_loop(
    'run_geacs_canc_memo_deproc_ant',
    'geacs_canc_memo_deproc_ant',
    'da GEACS',
    '',
    'cancelar_memos_deproc_antigos() — coluna 2',
    'Não altera a prox_acao: só script, ultima_passagem, data_execucao e as colunas canc_memo_deproc_ant_* (o erro vai para canc_memo_deproc_ant_tipo_erro / _erro)',
)
_erro_segue(col_canc_loop, 6)
col_canc = Coluna(
    '2 · cancelar_memos_deproc_antigos()',
    'Cancela todos os memos DEPROC antigos da GEACS, que serão ou já foram substituídos por uma nova versão. Não lê nem adiciona marcadores',
    [
        P('Sem Incluir Documento<br>(fechado no setor)?', [E('<b>ProcessoFechadoNoSetor</b>: não reabre, nada é cancelado')]),
        F('listar_documentos_arvore()', 'Todos os memorandos da GEACS - Utilização (toda a árvore, não só a rodada)'),
        S('<b>Para cada memorando da GEACS</b>: lê o texto (encontrar_memos_deproc_antigos)'),
        P(
            'Falta algum dos três trechos?<br>"Para: IPSEMG/DEPROC"<br>"Assunto: Levantamento de coparticipação - utilização indevida da assistência à saúde"<br>"levantamento dos valores de coparticipação referentes aos atendimentos efetivamente realizados"',
            [S('Não é o memo DEPROC antigo: ignorado')],
            rotulo='Sim (próximo memo)',
            largura=300,
        ),
        P('Sem data legível<br>("Belo Horizonte, 18 de<br>setembro de 2026.")?', [S('Não cancela: vai para canc_memo_deproc_ant_nao_cancelados (erro no fim)')], rotulo='Sim (próximo memo)'),
        P('Datado a partir de<br>15/10/2026?', [S('Não é antigo: ignorado')], rotulo='Sim (próximo memo)'),
        F('selecionar_doc() · cancelar_doc()', 'Motivo: "Documento será ou já foi substituído por uma nova versão"'),
        P(
            'Sem a opção<br>Cancelar Documento?',
            [S('Já cancelado, assinado ou sem permissão: vai para canc_memo_deproc_ant_nao_cancelados e segue para os outros')],
            rotulo='Sim (e segue)',
        ),
        P('Algum memo antigo<br>não cancelado?', [E('<b>ErroAvaliacao</b> (colunas canc_memo_deproc_ant_tipo_erro / _erro); os cancelados ficam registrados')]),
        T('canc_memo_deproc_ant_cancelado = sim se algum foi cancelado<br>canc_memo_deproc_ant_sei / _nome: os cancelados (nenhum memo antigo: não é erro)'),
    ],
)

# Fluxos de resposta
col_resp_loop = col_loop(
    'run_geacs_resp_apis / _disa / _deproc',
    'geacs_resp_apis / geacs_resp_disa / geacs_resp_deproc',
    'da GEACS',
    '',
    'processar_linha() — coluna 2',
    'Linha do processo: script (nome da aba), fluxo (RESP &lt;unidade&gt; - RESPOSTA DA &lt;unidade&gt;), prox_acao, erro e marcador_aguarda. Os resultados do fluxo inicial ficam como estão',
)
_erro_segue(col_resp_loop, 6)
col_resp = Coluna(
    '2 · processar_linha() (fluxo_resposta.py)',
    '<b>TODO: fluxos ainda não montados.</b> Base comum dos três; cada main_geacs_resp_*.py define os marcadores "Aguarda" e a função tratar_resposta()',
    [
        F('listar_marcadores() · registrar_tags()', 'Lê os marcadores do processo'),
        F('conferir_marcador_aguarda()', 'O estado atual precisa ser um dos "Aguarda" (manuais) do fluxo'),
        P(
            'Estado não é um "Aguarda"<br>do fluxo?',
            [E('<b>SemMarcadorAguarda</b>: não aguarda resposta desta unidade (ou o memo ainda não foi assinado). prox_acao = Verificar erro')],
        ),
        S('prox_acao = Aguardar resposta ao memo enviado (coluna marcador_aguarda)'),
        F('tratar_resposta()', '<b>TODO</b>: o que fazer com a resposta, por marcador (comentário em cada main_geacs_resp_*.py)'),
        E('<b>FluxoNaoMontado</b>: "Fluxo ... ainda não montado", sem nenhuma ação no SEI. A prox_acao continua Aguardar resposta ao memo enviado'),
    ],
)
nota_resp = N(
    '<b>Marcadores "Aguarda" de cada fluxo</b> (manuais: quem assina o memo coloca o "Aguarda" e remove o "No Bloco")<br><br>'
    '<b>run_geacs_resp_apis</b> (TAGS_AGUARDA_RESPOSTA_APIS)<br>'
    '01.05.1 - Aguarda APIS: Sem Memo p/ GEACS<br>'
    '01.05.1 - Aguarda APIS: Formato Inválido<br>'
    '01.06.1.1 - Aguarda APIS: Matrículas<br>'
    '01.07.1 - Aguarda APIS: Período Deps<br>'
    '01.10.1 - Aguarda APIS: Sem Uso<br><br>'
    '<b>run_geacs_resp_disa</b> (TAGS_AGUARDA_RESPOSTA_DISA)<br>'
    '01.09.1 - Aguarda DISA: Validar (Consta)<br>'
    '01.09.1 - Aguarda DISA: Validar (N Consta)<br>'
    '01.09.1 - Aguarda DISA: Relat. s/ MANTIS<br><br>'
    '<b>run_geacs_resp_deproc</b> (TAGS_AGUARDA_RESPOSTA_DEPROC)<br>'
    '01.10.1 - Aguarda DEPROC: Coparticipação',
    largura=420,
)

# DEPROC CALCULA COPA
col_copa_loop = col_loop(
    'run_deproc_calcula_copa',
    'deproc_calcula_copa',
    'da DEPROC',
    ' e a base DEPROC (Relatório Base 2 - MANTIS, aba Resultado, matrículas com DV)',
    'processar_deproc() — coluna 2',
    'Linha do processo: script, fluxo (DEPROC - COPARTICIPAÇÃO), prox_acao, erro, marcadores_deproc_* e tag_deproc_*. Os marcadores da GEACS e os resultados do fluxo inicial ficam como estão',
)
_erro_segue(col_copa_loop, 6)
col_copa = Coluna(
    '2 · processar_deproc()',
    'Na unidade da DEPROC: apura a coparticipação, anexa o relatório e cria o MemoGeacsCalculoCopa (da DEPROC à GEACS). Marcadores da DEPROC (mesmo prefixo "v2: ")',
    [
        F('registrar_tags() · conferir_marcadores_deproc()', 'No máximo um estado, e estado só com o 01. De novo no fim da passagem'),
        P('Marcadores<br>inconsistentes?', [E('<b>MarcadoresInconsistentes</b>: prox_acao = Verificar marcadores inconsistentes')]),
        P('Tem 01.02 - No Bloco GEACS:<br>Memo Cálculo COPA?', [T('Sem ler mais nada<br>prox_acao = DEPROC: assinar memo de resultado da coparticipação e encaminhar à GEACS')]),
        P(
            'Tem 01.02.1 - Encaminhado GEACS:<br>Memo Cálculo COPA (manual)?',
            [T('Concluído, sem ler mais nada<br>prox_acao = DEPROC: memo de resultado da coparticipação encaminhado à GEACS (concluído)')],
        ),
        P('Sem Incluir Documento?', [E('<b>ProcessoFechadoNoSetor</b>: não está aberto na DEPROC (não reabre)')]),
        F('garantir_marcadores_no_sei()', 'Os três que o script adiciona (TAGS_DEPROC): 01, 01.01 e 01.02'),
        F('listar_documentos_arvore() · obter_dados_ui()', 'Último memo da APIS destinado à GEACS (define a rodada). Sem memo ou formato inválido: erro'),
        F('_memo_deproc_assinado()', 'Memo DEPROC da GEACS na rodada (PADRAO_ASSUNTO_MEMO_DEPROC), assinado por Bruna Miiller Lavarini. Sem o memo ou sem a assinatura: erro'),
        F(
            'apurar_coparticipacao()',
            'Linhas com SEI = processo; confere as matrículas com o memo da APIS (MatriculasDivergentes); filtra pelo período de apuração. Nenhuma linha: erro',
        ),
        F(
            '_conferir_configuracao()',
            'Antes de qualquer documento: bloco BLOCO_MEMO_GEACS_CALCULO_COPA (7765003), signatário (Danúbia Lacerda Gomes de Oliveira) e texto do memo (TEXTO_DEFINIDO: TODO). Faltando: erro',
        ),
        M('01 - Tratado pelo Script<br><span style="font-weight:normal">se faltar</span>'),
        P(
            'Há atendimento<br>no período?',
            [
                PDF('PDF Coparticipação - &lt;matrícula&gt; - &lt;data&gt;<br><span style="font-weight:normal">extrato de utilização; retomada pelo nome na rodada</span>'),
                M('01.01 - Relatório Copart. Anexado'),
            ],
            rotulo='Sim (e segue)',
        ),
        MEMO('MemoGeacsCalculoCopa', '7765003 (BLOCO_MEMO_GEACS_CALCULO_COPA)'),
        M('01.02 - No Bloco GEACS: Memo Cálculo COPA<br><span style="font-weight:normal">↻ remove o 01.01</span>'),
        T('prox_acao = DEPROC: assinar memo de resultado da coparticipação e encaminhar à GEACS<br>Depois de assinar (manual): ➕ 01.02.1, ➖ 01.02'),
    ],
)

# DEPROC EXCLUIR DOCS
col_excluir_loop = col_loop(
    'run_deproc_excluir_docs',
    'deproc_excluir_docs',
    'da DEPROC',
    '',
    'excluir_docs_deproc() — coluna 2',
    'Não altera a prox_acao (nem fluxo, marcadores e erro dos outros fluxos): só script, ultima_passagem, data_execucao e a coluna deproc_excluir_docs (resultado em uma frase)',
)
_erro_segue(col_excluir_loop, 6)
col_excluir = Coluna(
    '2 · excluir_docs_deproc()',
    'Exclui todos os documentos da IPSEMG/DEPROC-Utilização do processo. Não lê nem adiciona marcadores',
    [
        P('Sem Incluir Documento<br>(fechado no setor)?', [E('<b>ProcessoFechadoNoSetor</b>: não reabre, nada é excluído')]),
        F('listar_documentos_arvore() · filtrar_docs_deproc()', 'Documentos da DEPROC (todos os tipos, não só memorandos)'),
        P('Nenhum documento<br>da DEPROC?', [T('deproc_excluir_docs = "nenhum documento da DEPROC"')]),
        S('<b>Para cada documento, do último para o primeiro</b> (um documento posterior pode citar o anterior)'),
        F('selecionar_doc() · excluir_doc()', 'sei_automacao.documento'),
        P(
            'Falhou?<br>(ex.: assinado)',
            [S('Anota como não excluído, recarrega a página e segue para o próximo. Navegador fechado: para o processo')],
            rotulo='Sim (e segue)',
        ),
        F(
            '_docs_deproc_restantes()',
            'A árvore demora a refletir a exclusão: reabre o processo e relê a árvore até os excluídos sumirem, por até 15 s (TEMPO_CONFERENCIA)',
        ),
        P('Algum documento da DEPROC<br>ainda na árvore?', [E('<b>ErroAvaliacao</b>: "Documento(s) da DEPROC não excluído(s): ..." (sai dos excluídos)')]),
        T('deproc_excluir_docs = "&lt;data&gt; | N excluído(s): &lt;nºs SEI&gt;"'),
    ],
)

# GEACS VERIFICAR MARCADORES
col_verif_loop = col_loop(
    'run_geacs_verificar_marcadores',
    'geacs_verificar_marcadores',
    'da GEACS',
    '',
    'verificar_marcadores() — coluna 2',
    'Não altera a prox_acao (nem fluxo e erro dos outros fluxos): só script, ultima_passagem, data_execucao e as colunas de marcadores',
)
_erro_segue(col_verif_loop, 6)
col_verif = Coluna(
    '2 · verificar_marcadores()',
    'Lê os marcadores do processo, sem nenhuma ação no SEI',
    [
        F('listar_marcadores() · registrar_tags()', 'Marcadores do processo no SEI'),
        F('colunas_tags() · demais_marcadores()', 'Uma coluna tag_* por marcador válido na GEACS (TAGS_VALIDOS_GEACS, 30). Os outros (v2v:, 01.06.2 / 01.08.2 / 01.08.3, manuais, antigos) vão juntos para demais_marcadores'),
        T('Planilha: tag_*, demais_marcadores e marcadores_finais (erro: verificar_marcadores_erro, e as colunas de marcadores ficam como estavam)'),
    ],
)

# --- montagem -----------------------------------------------------------------


def _texto(valor, x, y, largura, altura, tamanho, negrito=False):
    estilo = f'text;html=1;align=left;verticalAlign=middle;fontSize={tamanho};' + ('fontStyle=1;' if negrito else '')
    return (
        f'<mxCell id="{_novo_id()}" value="{escape(valor)}" style="{estilo}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{largura}" height="{altura}" as="geometry"/></mxCell>'
    )


def _cabecalho(celulas, titulo, subtitulo, nota=None):
    """Título, subtítulo, legenda em uma linha e a nota à direita. Devolve o y das colunas."""
    celulas.append(_texto(titulo, 40, 20, 1400, 44, 26, negrito=True))
    celulas.append(_texto(subtitulo, 40, 68, 1600, 28, 14))
    x, y_legenda = 40, 110
    for modelo in legenda:
        item = No(modelo.tipo, modelo.texto, 180)
        item.emitir(celulas, '1', x, y_legenda + (90 - item.h) / 2)
        x += item.w + 30
    altura_nota = 0
    if nota is not None:
        nota.emitir(celulas, '1', x + 30, y_legenda - 10)
        altura_nota = nota.h
    return y_legenda + max(160, altura_nota + 40)


def pagina(id_aba, nome, titulo, subtitulo, colunas, nota=None, laterais=(), titulo_laterais=''):
    """Uma aba do drawio: as colunas lado a lado e, à direita, as laterais
    (notas e colunas auxiliares) empilhadas."""
    _setas.clear()
    celulas: list[str] = []
    y_colunas = _cabecalho(celulas, titulo, subtitulo, nota)
    x = 40
    for coluna in colunas:
        coluna.emitir(celulas, x, y_colunas)
        x += coluna.w + 60
    y = y_colunas
    largura_total = x
    if laterais:
        x_lado = x + 40
        if titulo_laterais:
            celulas.append(_texto(titulo_laterais, x_lado, y - 40, 500, 34, 18, negrito=True))
        for item in laterais:
            if isinstance(item, Coluna):
                item.emitir(celulas, x_lado, y)
            else:
                item.emitir(celulas, '1', x_lado, y)
            y += item.h + 40
        largura_total = x_lado + max(item.w for item in laterais) + 40
    altura_total = max(y, *(y_colunas + c.h for c in colunas)) + 40
    return (
        f'<diagram id="{id_aba}" name="{escape(nome)}">'
        '<mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        f'pageWidth="{largura_total:.0f}" pageHeight="{altura_total:.0f}" math="0" shadow="0">'
        '<root><mxCell id="0"/><mxCell id="1" parent="0"/>' + ''.join(celulas) + ''.join(_setas) + '</root></mxGraphModel></diagram>'
    )


LEIA = 'Leia as colunas da esquerda para a direita. Em cada coluna o caminho principal desce reto; os desvios saem para a direita.'

abas = [
    pagina(
        'geacs-inicial',
        'geacs_inicial',
        'run_geacs_inicial · Fluxo inicial da GEACS (main_geacs_inicial.py)',
        f'Do memo da APIS aos memos à APIS, à DISA ou à DEPROC. Aba de entrada geacs_inicial. {LEIA}',
        [col_main, col_tratar, col_processar, col_mantis],
        nota=pendencias,
        laterais=[marcadores, *aux],
        titulo_laterais='Funções usadas em vários pontos',
    ),
    pagina(
        'geacs-resp',
        'geacs_resp_*',
        'run_geacs_resp_apis / _disa / _deproc · Respostas (TODO: não montados)',
        f'Processo parado com um "Aguarda" manual (memo assinado e encaminhado) depois da resposta da APIS, da DISA ou da DEPROC. {LEIA}',
        [col_resp_loop, col_resp],
        laterais=[nota_resp],
    ),
    pagina(
        'geacs-adc-pdf-ant-aut',
        'geacs_adc_pdf_ant_aut',
        'run_geacs_adc_pdf_ant_aut · PDF das planilhas antigas, automático (main_geacs_adc_pdf_ant_aut.py)',
        f'Baixa as planilhas de utilização do SEI, insere o PDF de cada uma e deixa o processo aguardando o fluxo inicial. Não avalia bases nem cria memos. {LEIA}',
        [col_adc_aut_loop, col_adc_aut, col_adc_aut_fim],
    ),
    pagina(
        'geacs-adc-pdf-ant-man',
        'geacs_adc_pdf_ant_man',
        'run_geacs_adc_pdf_ant_man · PDF das planilhas antigas, manual (main_geacs_adc_pdf_ant_man.py)',
        f'As planilhas que o Chrome não baixa, colocadas à mão em dados/geacs_adc_pdf_ant_man/planilhas. {LEIA}',
        [col_adc_man_loop, col_adc_man, col_adc_man_fim],
    ),
    pagina(
        'geacs-canc-memo-deproc-ant',
        'geacs_canc_memo_deproc_ant',
        'run_geacs_canc_memo_deproc_ant · Cancelar o memo DEPROC antigo (main_geacs_canc_memo_deproc_ant.py)',
        f'Na unidade da GEACS. Não altera a prox_acao. {LEIA}',
        [col_canc_loop, col_canc],
    ),
    pagina(
        'geacs-verificar-marcadores',
        'geacs_verificar_marcadores',
        'run_geacs_verificar_marcadores · Verificar os marcadores (main_geacs_verificar_marcadores.py)',
        f'Na unidade da GEACS. Não altera a prox_acao: atualiza só as colunas de marcadores (tag_* e demais_marcadores). {LEIA}',
        [col_verif_loop, col_verif],
    ),
    pagina(
        'deproc-calcula-copa',
        'deproc_calcula_copa',
        'run_deproc_calcula_copa · Cálculo da coparticipação na DEPROC (main_deproc_calcula_copa.py)',
        f'Na unidade da DEPROC, com os marcadores da DEPROC. {LEIA}',
        [col_copa_loop, col_copa],
    ),
    pagina(
        'deproc-excluir-docs',
        'deproc_excluir_docs',
        'run_deproc_excluir_docs · Excluir os documentos da DEPROC (main_deproc_excluir_docs.py)',
        f'Na unidade da DEPROC. Não altera a prox_acao (coluna própria deproc_excluir_docs). {LEIA}',
        [col_excluir_loop, col_excluir],
    ),
]

with open(SAIDA, 'w', encoding='utf-8') as f:
    f.write('<mxfile host="app.diagrams.net" type="device">' + ''.join(abas) + '</mxfile>\n')
print(f'{len(abas)} abas')
