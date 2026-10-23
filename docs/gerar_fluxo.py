"""Gera docs/fluxo.drawio: uma aba com o fluxo completo.

Uma coluna por função, lidas da esquerda para a direita (1 → 4); a coluna
da direita detalha as funções chamadas em vários pontos. Em cada coluna o
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
        P('remover_marcador existe<br>na sei_automacao?', [E('<b>SystemExit</b>: execução não iniciada<br>(TODO na sei_automacao)')], rotulo='Não', segue='Sim'),
        F('carregar_bases() · carregar_bases_mantis()', 'Lê processos_nao_processados.xlsx, a base DISA, a base APIS e o MANTIS (rede própria e credenciada)'),
        F('PlanilhaControleGeral() · abrir_sei()', 'Lê a planilha de controle e faz login no SEI'),
        S('<b>Para cada processo</b>'),
        F('_processar_linha()', 'Abre o processo e lê a árvore e os marcadores do SEI', chama='acessar_processo, registrar_arvore, registrar_tags'),
        IR('_tratar() — coluna 2'),
        F('conferir_marcadores()', 'De novo, no fim da passagem (se não houve erro)'),
        E('<b>Erro levantado em qualquer coluna?</b><br><font face="Courier New">registrar_erro()</font>: tipo_erro, erro e prox_acao = Verificar erro (ou a já definida). Inesperado: + traceback'),
        F('controle.registrar()', 'Regrava a planilha de controle (abas processos e historico) depois de cada processo'),
        P('Há mais processos?', [IR('volta a "Para cada processo"')]),
        F('log_resumo()', 'Fecha o navegador e loga o resumo'),
        T('Fim'),
    ],
)
# O erro não encerra a execução: a passagem segue para a planilha
col_main.itens[9].ligar = lambda prox, no=col_main.itens[9]: _seta(no, prox, '', ABAIXO)

col_tratar = Coluna(
    '2 · _tratar()',
    'Separa o processo VELHO e roteia pelos marcadores lidos do SEI. Só adiciona o marcador 1 (e o 0, em _separar_velho); o resto é decidido em processar_novo()',
    [
        F(
            'conferir_marcadores()',
            'A combinação de marcadores é possível no fluxo?<br>'
            '• no máximo um marcador de estado (★)<br>'
            '• no máximo um de cada par: 1.6.2 - Base DISA: Usou RP / 1.6.2 - Base DISA: Não Usou RP, 1.8.2 - MANTIS: Usou RP / 1.8.2 - MANTIS: Não Usou RP e '
            '1.8.3 - MANTIS: Usou RC / 1.8.3 - MANTIS: Não Usou RC<br>'
            '• informativo só com estado compatível<br>'
            '• 1.6.1 - Aguarda APIS: Matrículas exige 1.2.1 - Mat. N Encontradas Base APIS<br>'
            '• 1.7 - Aguarda APIS: Período Deps exige 1.1 - Período Variável p/ Dependentes<br>'
            '• cada 1.9 - Aguarda DISA exige o seu par: Validar (Consta) = DISA e MANTIS Usou RP; Validar (N Consta) = DISA Não Usou e MANTIS Usou RP; '
            'Relat. s/ MANTIS = DISA Usou e MANTIS Não Usou RP<br>'
            '• 1.10 - Aguarda APIS: Sem Uso exige 1.6.2 - Base DISA: Não Usou RP, 1.8.2 - MANTIS: Não Usou RP e 1.8.3 - MANTIS: Não Usou RC<br>'
            '• VELHO (0 - Processo VELHO ou 1.3 - Memos DISA e DEPROC no Bloco) sem memos à DISA ou à DEPROC do fluxo atual (1.9, 1.10)…',
        ),
        P('Marcadores<br>inconsistentes?', [E('<b>MarcadoresInconsistentes</b>: nada é feito no SEI<br>prox_acao = Verificar marcadores (corrigir no SEI)')]),
        P(
            '<b>VELHO</b> pelos marcadores?<br>0 - Processo VELHO ou<br>1.3 - Memos DISA e DEPROC no Bloco',
            [IR('_separar_velho()<br><span style="font-weight:normal">à direita</span>')],
            largura=LARGURA_PRINCIPAL,
        ),
        S('<font face="Courier New">estado_atual()</font>: marcador de estado do processo'),
        P(
            'Estado de parada?<br>1.5 - Aguarda APIS: Sem Memo p/ GEACS<br>1.5 - Aguarda APIS: Formato Inválido<br>'
            '1.6.1 - Aguarda APIS: Matrículas<br>1.7 - Aguarda APIS: Período Deps<br>1.9 - Aguarda DISA: Validar (Consta)<br>'
            '1.9 - Aguarda DISA: Validar (N Consta)<br>1.9 - Aguarda DISA: Relat. s/ MANTIS<br>1.10 - Aguarda APIS: Sem Uso<br>'
            'versão anterior: 1.8.1 - Memo DISA Validar Usos MANTIS, 1.9 - Memo DISA Uso Rede Própria',
            [E('<b>Erro</b>: parado aguardando resposta ao memo<br>prox_acao = Aguardar resposta ao memo enviado')],
            largura=LARGURA_PRINCIPAL,
        ),
        P(
            'Estado de conclusão?<br>1.10 - Concluído: Memo DEPROC<br>versão anterior: 1.10 - Concluído: Memos DISA e DEPROC',
            [T('<b>Concluído</b>, prox_acao:<br>1.10 - Concluído: Memo DEPROC → assinar DEPROC<br>1.10 - Concluído: Memos DISA e DEPROC → assinar os dois')],
            largura=LARGURA_PRINCIPAL,
        ),
        P('NOVO sem estado com<br>1.3 - Memo DEPROC no Bloco?', [T('Concluído na versão anterior<br>prox_acao = Assinar memo DEPROC')]),
        F(
            'encontrar_memos_velho()',
            'Lê <b>todos os memorandos da GEACS</b> e procura dois seguidos: "Para: IPSEMG/DISA-UTI-INDEV" e depois "Para: IPSEMG/DEPROC", '
            'os dois datados ("Belo Horizonte, 18 de setembro de 2026.") antes de 01/10/2026',
        ),
        P('Par sem data<br>legível?', [E('<b>ErroAvaliacao</b>: não dá para saber se é VELHO; nada é feito no SEI')]),
        P('<b>VELHO</b> pelos memos<br>da GEACS?', [IR('_separar_velho()<br><span style="font-weight:normal">à direita</span>')]),
        P('Sem o marcador<br><b>1 - Tratado pelo Script</b>?', [M('1 - Tratado pelo Script'), IR('processar_novo() do início — coluna 3')]),
        IR('processar_novo() — coluna 3<br><span style="font-weight:normal">do início ou retomando de 1.6 - Avaliado Uso Rede Própria DISA ou 1.8 - Avaliado Uso Rede Própria MANTIS</span>'),
    ],
)

col_processar = Coluna(
    '3 · processar_novo()',
    'Memo da APIS, base APIS e base DISA, e as paradas com memo à APIS. Na retomada, as etapas já feitas são puladas (_etapa_feita)',
    [
        F('obter_dados_ui()', 'Usa o <b>último</b> memo da APIS destinado à GEACS; os documentos depois dele são a rodada', chama='obter_memos_apis_para_geacs, validar_template, extrair_dados_ui'),
        P(
            'Nenhum memo da APIS<br>para a GEACS?',
            [
                F('_parar_sem_memo_apis()', chama='_parar_com_memo'),
                MEMO('MemoApisSemMemo', 7730344),
                M('1.5 - Aguarda APIS: Sem Memo p/ GEACS'),
                R('estado anterior (se houver)'),
                T('prox_acao = Assinar memo à APIS (sem memorando)'),
            ],
        ),
        P(
            'Formato inválido?<br>(não é novo_novo)',
            [
                F('_parar_formato_invalido()', chama='_parar_com_memo'),
                MEMO('MemoApisFormatoInvalido', 7730341),
                M('1.5 - Aguarda APIS: Formato Inválido'),
                R('estado anterior (se houver)'),
                T('prox_acao = Assinar memo à APIS (formato inválido)'),
            ],
        ),
        F('verificar_base_apis()', 'A existência das matrículas é conferida <b>só na base APIS</b> (a base DISA é feita a partir dela)'),
        P('Matrícula em<br>formato inválido?', [E('<b>ErroAvaliacao</b>')]),
        P(
            'Faltou matrícula<br>na base APIS?',
            [
                F('_parar_nao_encontradas_base_apis()', chama='garantir_marcadores_no_sei, incluir_memo_apis_mat_nao_encontradas'),
                M('1.2.1 - Mat. N Encontradas Base APIS'),
                MEMO('MemoApisMatNaoEncontradas', 7711907),
                M('1.6.1 - Aguarda APIS: Matrículas'),
                R('estado anterior (se houver)'),
                T('prox_acao = Assinar memo à APIS (matrículas não encontradas)'),
            ],
        ),
        P(
            'Tem 1.2.1 - Mat. N Encontradas Base APIS?<br>(base corrigida)',
            [R('1.2.1 - Mat. N Encontradas Base APIS<br><span style="font-weight:normal">remove e segue o fluxo (abaixo)</span>')],
            largura=LARGURA_PRINCIPAL,
        ),
        F('_avaliar_disa()', 'Uso da rede própria na base DISA. Fora da base DISA = não usou', chama='avaliar_uso_rede_propria_disa, registrar_uso, garantir_marcadores_no_sei'),
        P('Resposta inválida<br>na base DISA?', [E('<b>ErroAvaliacao</b>')]),
        Casos(
            'Alguém usou a rede própria<br>segundo a <b>base DISA</b>?',
            [
                ('Sim', [M('1.6.2 - Base DISA: Usou RP')]),
                ('Não', [M('1.6.2 - Base DISA: Não Usou RP')]),
            ],
            M('1.6 - Avaliado Uso Rede Própria DISA<br><span style="font-weight:normal">pulado na retomada; remove o estado anterior</span>'),
        ),
        P(
            'Período variável<br>para dependentes?',
            [
                F('_parar_periodo_variavel()', chama='_parar_com_memo'),
                M('1.1 - Período Variável p/ Dependentes'),
                MEMO('MemoApisPeriodoDependentes', 7730905),
                M('1.7 - Aguarda APIS: Período Deps'),
                R('1.6 - Avaliado Uso Rede Própria DISA'),
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
        F('avaliar_uso_rede_propria_mantis()', 'Atendimentos no período do titular, nas duas redes', chama='interpretar_periodo'),
        P('Período ou data<br>de atendimento<br>inválidos?', [E('<b>ErroAvaliacao</b>')]),
        F('_registrar_uso_mantis() · usos_mantis_alem_disa()', 'Planilha: uso nas duas redes, caso_disa_mantis e mats_uso_mantis_alem_disa (RP no MANTIS e fora da base DISA)'),
        S('Escolhe o memo pelo caso (abaixo) e o monta <b>antes de qualquer ação no SEI</b>'),
        P('Texto do memo<br>pendente?', [E('<b>TextoMemoPendente</b><br>nada é criado no SEI')]),
        P('Bloco do memo (DISA ou<br>APIS sem uso) não<br>configurado (None)?', [E('<b>ErroAvaliacao</b><br>nada é criado no SEI')]),
        F('garantir_marcadores_no_sei()', 'Os marcadores que serão adicionados existem no SEI?'),
        Casos(
            'Alguém usou a <b>rede própria</b><br>segundo o <b>MANTIS</b>?',
            [
                ('Sim', [M('1.8.2 - MANTIS: Usou RP')]),
                ('Não', [M('1.8.2 - MANTIS: Não Usou RP')]),
            ],
            S('Mesma pergunta para a rede credenciada'),
        ),
        Casos(
            'Alguém usou a <b>rede credenciada</b><br>segundo o <b>MANTIS</b>?',
            [
                ('Sim', [M('1.8.3 - MANTIS: Usou RC')]),
                ('Não', [M('1.8.3 - MANTIS: Não Usou RC')]),
            ],
            M('1.8 - Avaliado Uso Rede Própria MANTIS<br><span style="font-weight:normal">pulado na retomada; remove 1.6 - Avaliado Uso Rede Própria DISA</span>'),
        ),
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
                        M('1.9 - Aguarda DISA: Validar (Consta)'),
                        R('1.8 - Avaliado Uso Rede Própria MANTIS'),
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
                        M('1.9 - Aguarda DISA: Validar (N Consta)'),
                        R('1.8 - Avaliado Uso Rede Própria MANTIS'),
                        T('prox_acao = Assinar memo à DISA (validar; não consta)<br><b>sem DEPROC</b>'),
                    ],
                ),
                (
                    'DISA sim × RP não',
                    [
                        CASO('DISA sim × MANTIS RP não', 'sem MANTIS: solicita relatório à DISA'),
                        PDF('PDF Utilização Tit./Dep. <b>RC</b><br>(só de quem usou)'),
                        MEMO('MemoDisaSemMantisSolicitaRelatorio', 'BLOCO_MEMO_DISA_SEM_MANTIS_RELATORIO (TODO)'),
                        M('1.9 - Aguarda DISA: Relat. s/ MANTIS'),
                        R('1.8 - Avaliado Uso Rede Própria MANTIS'),
                        T('prox_acao = Assinar memo à DISA (sem MANTIS: solicita relatório)<br><b>sem DEPROC</b>'),
                    ],
                ),
                (
                    'DISA não × RP não × RC sim',
                    [
                        CASO('DISA não × MANTIS RP não × MANTIS RC sim', 'só DEPROC'),
                        PDF('PDF Utilização Tit./Dep. <b>RC</b><br>(só de quem usou)'),
                        MEMO('MemoDeproc', 7697744),
                        M('1.10 - Concluído: Memo DEPROC'),
                        R('1.8 - Avaliado Uso Rede Própria MANTIS'),
                        T('prox_acao = Assinar memo DEPROC'),
                    ],
                ),
                (
                    'DISA não × RP não × RC não',
                    [
                        CASO('DISA não × MANTIS RP não × MANTIS RC não', 'nenhum uso: avisa a APIS'),
                        S('Sem relatório para anexar'),
                        MEMO('MemoApisSemUso</b> (TODO: texto)<b>', 'BLOCO_MEMO_APIS_SEM_USO (TODO)'),
                        M('1.10 - Aguarda APIS: Sem Uso'),
                        R('1.8 - Avaliado Uso Rede Própria MANTIS'),
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
            P('Tem MANUAL<br>ou ASSINADO?', [T('prox_acao = Fora do escopo (tratado manualmente)')]),
            F('garantir_marcadores_no_sei()'),
            M('0 - Processo VELHO<br><span style="font-weight:normal">se ainda não tiver</span>'),
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
                'É de um grupo de<br>alternativos? (estado ★<br>ou par 1.6.2 / 1.8.2 / 1.8.3)',
                [F('remover_tag()', 'Remove o outro do grupo (cada ➖ do diagrama)', chama='remover_marcador')],
            ),
        ],
        cor='aux',
    ),
    Coluna(
        'adicionar_tag_se_ausente()',
        'Retomada: 0 - Processo VELHO, 1.1 - Período Variável p/ Dependentes e 1.2.1 - Mat. N Encontradas Base APIS não são adicionados de novo',
        [P('Já tem o marcador?', [S('Não faz nada')]), F('adicionar_tag()')],
        cor='aux',
    ),
    Coluna(
        'incluir_memo()',
        'Cada 📄 do diagrama. Retomada: procura o memo pelo assunto na rodada',
        [
            F('encontrar_memo_geacs_por_assunto()'),
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
    '<b>Marcadores</b> (prefixo "Script v2 - "; ★ = estado: no máximo um; ◆ = par: no máximo um de cada)<br>'
    '0 - Processo VELHO<br>'
    '1 - Tratado pelo Script<br>'
    '1.1 - Período Variável p/ Dependentes<br>'
    '1.2.1 - Mat. N Encontradas Base APIS<br>'
    '★ 1.5 - Aguarda APIS: Sem Memo p/ GEACS<br>'
    '★ 1.5 - Aguarda APIS: Formato Inválido<br>'
    '★ 1.6 - Avaliado Uso Rede Própria DISA<br>'
    '★ 1.6.1 - Aguarda APIS: Matrículas<br>'
    '◆ 1.6.2 - Base DISA: Usou RP<br>'
    '◆ 1.6.2 - Base DISA: Não Usou RP<br>'
    '★ 1.7 - Aguarda APIS: Período Deps<br>'
    '★ 1.8 - Avaliado Uso Rede Própria MANTIS<br>'
    '◆ 1.8.2 - MANTIS: Usou RP<br>'
    '◆ 1.8.2 - MANTIS: Não Usou RP<br>'
    '◆ 1.8.3 - MANTIS: Usou RC<br>'
    '◆ 1.8.3 - MANTIS: Não Usou RC<br>'
    '★ 1.9 - Aguarda DISA: Validar (Consta)<br>'
    '★ 1.9 - Aguarda DISA: Validar (N Consta)<br>'
    '★ 1.9 - Aguarda DISA: Relat. s/ MANTIS<br>'
    '★ 1.10 - Concluído: Memo DEPROC<br>'
    '★ 1.10 - Aguarda APIS: Sem Uso<br>'
    '<i>Versão anterior:<br>'
    '1.2 - Avaliado Se Usou Rede Própria<br>'
    '1.2.2 - Mat. N Encontradas Base DISA<br>'
    '1.3 - Memos DISA e DEPROC no Bloco (= VELHO)<br>'
    '1.3 - Memo DEPROC no Bloco<br>'
    '1.4 - Memo Não Usou Rede no Bloco<br>'
    '★ 1.8.1 - Memo DISA Validar Usos MANTIS<br>'
    '★ 1.9 - Memo DISA Uso Rede Própria<br>'
    '★ 1.10 - Concluído: Memos DISA e DEPROC<br>'
    '★ 1.11 - VELHO Concluído: Memo DISA<br>'
    '★ 1.11 - VELHO Concluído: Memo DEPROC</i>',
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
    '• remover_marcador na sei_automacao (sem ele o main não inicia)<br>'
    '• no SEI: editar os marcadores renomeados (1 - Tratado pelo Script, 1.5 - Aguarda APIS: Sem Memo p/ GEACS, 1.5 - Aguarda APIS: Formato Inválido, '
    '1.6.1 - Aguarda APIS: Matrículas, 1.7 - Aguarda APIS: Período Deps, 1.10 - Concluído: Memo DEPROC, 1.2.1 - Mat. N Encontradas Base APIS) '
    'e cadastrar 0 - Processo VELHO, os seis 1.6.2 / 1.8.2 / 1.8.3, os três 1.9 - Aguarda DISA e 1.10 - Aguarda APIS: Sem Uso<br>'
    '• blocos dos três memos à DISA e do memo à APIS sem uso (constantes = None)<br>'
    '• revisar os textos e assuntos dos memos com TEXTO_DEFINIDO = False<br>'
    '• fluxo do processo VELHO<br>'
    '• tratar a resposta dos processos parados (APIS e DISA)',
    largura=460,
)

# --- montagem -----------------------------------------------------------------

celulas = [
    f'<mxCell id="{_novo_id()}" value="{escape("Fluxo do script SEI - Utilização Indevida (v2)")}" '
    'style="text;html=1;align=left;verticalAlign=middle;fontSize=26;fontStyle=1;" vertex="1" parent="1">'
    '<mxGeometry x="40" y="20" width="900" height="44" as="geometry"/></mxCell>',
    f'<mxCell id="{_novo_id()}" value="{escape("Leia as colunas da esquerda para a direita. Em cada coluna o caminho principal desce reto; os desvios saem para a direita.")}" '
    'style="text;html=1;align=left;verticalAlign=middle;fontSize=14;" vertex="1" parent="1">'
    '<mxGeometry x="40" y="68" width="1200" height="28" as="geometry"/></mxCell>',
]

# Legenda em uma linha
x, y_legenda = 40, 110
for item in legenda:
    _ajustar(item, 180)
    item.emitir(celulas, '1', x, y_legenda + (90 - item.h) / 2)
    x += item.w + 30
pendencias.emitir(celulas, '1', x + 30, y_legenda - 10)

y_colunas = y_legenda + 160
x = 40
for coluna in [col_main, col_tratar, col_processar, col_mantis]:
    coluna.emitir(celulas, x, y_colunas)
    x += coluna.w + 60

x_aux, y = x + 40, y_colunas
celulas.append(
    f'<mxCell id="{_novo_id()}" value="Funções usadas em vários pontos" style="text;html=1;align=left;verticalAlign=middle;fontSize=18;fontStyle=1;" vertex="1" parent="1">'
    f'<mxGeometry x="{x_aux}" y="{y - 40}" width="500" height="34" as="geometry"/></mxCell>'
)
marcadores.emitir(celulas, '1', x_aux, y)
y += marcadores.h + 40
for coluna in aux:
    coluna.emitir(celulas, x_aux, y)
    y += coluna.h + 40

colunas = [col_main, col_tratar, col_processar, col_mantis, *aux]
largura_total = x_aux + max(c.w for c in aux) + 40
altura_total = max(y, *(y_colunas + c.h for c in colunas)) + 40
xml = (
    '<mxfile host="app.diagrams.net" type="device">'
    '<diagram id="fluxo-completo" name="Fluxo completo">'
    '<mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
    f'pageWidth="{largura_total:.0f}" pageHeight="{altura_total:.0f}" math="0" shadow="0">'
    '<root><mxCell id="0"/><mxCell id="1" parent="0"/>' + ''.join(celulas) + ''.join(_setas) + '</root></mxGraphModel></diagram></mxfile>\n'
)
with open(SAIDA, 'w', encoding='utf-8') as f:
    f.write(xml)
print(f'{len(celulas)} células, {len(_setas)} setas, página {largura_total:.0f} x {altura_total:.0f}')
