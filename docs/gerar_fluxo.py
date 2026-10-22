"""Gera docs/fluxo.drawio: uma aba com o fluxo completo.

Molduras = funções (aninhadas = funções chamadas). Dentro de cada moldura,
os passos na ordem de execução; os desvios de cada pergunta ficam à direita.
"""

import math
import re
import sys
from html import escape

# Uso: python docs/gerar_fluxo.py docs/fluxo.drawio
SAIDA = sys.argv[1]

# --- estilos ------------------------------------------------------------------

ESTILOS = {
    'terminal': 'rounded=1;arcSize=50;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;fontSize=12;',
    'step': 'rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#666666;fontSize=12;',
    'func': 'rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=12;align=center;',
    'goto': 'shape=process;whiteSpace=wrap;html=1;backgroundOutline=1;size=0.05;fillColor=#ffe6cc;strokeColor=#d79b00;fontSize=12;',
    'decision': 'rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;fontSize=12;',
    'marker': 'shape=hexagon;perimeter=hexagonPerimeter2;size=0.06;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;strokeWidth=2;fontStyle=1;fontSize=12;',
    'removed': 'shape=hexagon;perimeter=hexagonPerimeter2;size=0.06;whiteSpace=wrap;html=1;fillColor=#fff4e5;strokeColor=#d79b00;strokeWidth=2;dashed=1;fontStyle=1;fontSize=12;fontColor=#8a5a00;',
    'memo': 'rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;strokeWidth=2;fontSize=12;',
    'pdf': 'shape=document;boundedLbl=1;size=0.15;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;strokeWidth=2;fontSize=12;',
    'error': 'rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;strokeWidth=2;fontSize=12;',
    'note': 'shape=note;size=14;whiteSpace=wrap;html=1;align=left;verticalAlign=top;spacing=8;fillColor=#fffde7;strokeColor=#c9b458;fontSize=12;',
}
ESTILO_MOLDURA = {
    0: 'swimlane;html=1;whiteSpace=wrap;fontSize=13;rounded=1;arcSize=1;collapsible=0;container=1;strokeWidth=2;fillColor=#bac8d3;strokeColor=#23445d;swimlaneFillColor=#f7f9fb;',
    1: 'swimlane;html=1;whiteSpace=wrap;fontSize=13;rounded=1;arcSize=1;collapsible=0;container=1;strokeWidth=2;fillColor=#dae8fc;strokeColor=#6c8ebf;swimlaneFillColor=#ffffff;',
    'aux': 'swimlane;html=1;whiteSpace=wrap;fontSize=13;rounded=1;arcSize=1;collapsible=0;container=1;strokeWidth=2;fillColor=#ffe6cc;strokeColor=#d79b00;swimlaneFillColor=#fffaf3;',
}
LARGURA = {'terminal': 280, 'step': 320, 'func': 340, 'goto': 320, 'decision': 300, 'marker': 340, 'removed': 340, 'memo': 340, 'pdf': 340, 'error': 320, 'note': 340}
ESTILO_SETA = 'edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;strokeColor=#555555;fontSize=11;'
ESTILO_SETA_ERRO = 'edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;strokeColor=#b85450;dashed=1;fontSize=11;fontColor=#b85450;'

PAD, GAP, VGAP, BGAP = 24, 70, 34, 40

_ids = iter(range(10, 10**6))


def _novo_id() -> str:
    return f'c{next(_ids)}'


def _linhas(texto: str, largura: int, fator: float = 1.0) -> int:
    util = max(40, (largura - 20) * fator)
    total = 0
    for parte in re.split(r'<br\s*/?>', texto):
        limpo = re.sub(r'<[^>]+>', '', parte)
        limpo = limpo.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        total += max(1, math.ceil(len(limpo) * 6.8 / util))
    return total


# --- elementos ----------------------------------------------------------------


class No:
    def __init__(self, tipo, texto, chave=None, largura=None):
        self.tipo, self.texto, self.chave = tipo, texto, chave
        self.id = _novo_id()
        self.w = largura or LARGURA[tipo]
        if tipo == 'decision':
            self.h = max(80, _linhas(texto, self.w, 0.55) * 16 + 50)
        elif tipo in {'marker', 'removed'}:
            self.h = max(44, _linhas(texto, self.w, 0.9) * 16 + 18)
        elif tipo == 'pdf':
            self.h = max(50, _linhas(texto, self.w) * 16 + 30)
        else:
            self.h = max(40, _linhas(texto, self.w) * 16 + 18)

    def emitir(self, saida, pai, x, y):
        self.x, self.y = x, y
        saida.append(
            f'<mxCell id="{self.id}" value="{escape(self.texto)}" style="{ESTILOS[self.tipo]}" vertex="1" parent="{pai}">'
            f'<mxGeometry x="{x:.0f}" y="{y:.0f}" width="{self.w:.0f}" height="{self.h:.0f}" as="geometry"/></mxCell>'
        )


class Ramo:
    def __init__(self, rotulo, itens, volta=False, ir_para=None):
        self.rotulo, self.itens, self.volta, self.ir_para = rotulo, itens, volta, ir_para
        self.w = max(i.w for i in itens)
        self.h = sum(i.h for i in itens) + VGAP * (len(itens) - 1)


class Pergunta(No):
    def __init__(self, texto, ramos, segue='Não', largura=None):
        super().__init__('decision', texto, largura=largura)
        self.ramos, self.segue = ramos, segue
        self.lateral_w = sum(r.w for r in ramos) + BGAP * (len(ramos) - 1)
        self.topo_ramos = self.h / 2 + 30
        self.linha_h = max(self.h, self.topo_ramos + max(r.h for r in ramos))


class Moldura:
    def __init__(self, nome, descricao, itens, nivel=1, chave=None):
        self.nome, self.descricao, self.itens, self.nivel, self.chave = nome, descricao, itens, nivel, chave
        self.id = _novo_id()
        self.tipo = 'frame'
        self.col_w = max(i.w for i in itens)
        self.lateral_w = max((i.lateral_w for i in itens if isinstance(i, Pergunta)), default=0)
        interno = self.col_w + (GAP + self.lateral_w if self.lateral_w else 0)
        self.w = max(interno + 2 * PAD, 380)
        self.cabecalho = 30 + _linhas(descricao, self.w, 1.05) * 16 if descricao else 34
        alturas = [i.linha_h if isinstance(i, Pergunta) else i.h for i in itens]
        self.h = self.cabecalho + PAD + sum(alturas) + VGAP * (len(itens) - 1) + PAD

    @property
    def valor(self):
        nome = f'<font face="Courier New" style="font-size:14px"><b>{escape(self.nome)}</b></font>'
        if self.descricao:
            return f'{nome}<br><span style="font-size:11px;font-weight:normal">{self.descricao}</span>'
        return nome

    def emitir(self, saida, pai, x, y):
        self.x, self.y = x, y
        estilo = ESTILO_MOLDURA[self.nivel] + f'startSize={self.cabecalho:.0f};verticalAlign=top;'
        saida.append(
            f'<mxCell id="{self.id}" value="{escape(self.valor)}" style="{estilo}" vertex="1" parent="{pai}">'
            f'<mxGeometry x="{x:.0f}" y="{y:.0f}" width="{self.w:.0f}" height="{self.h:.0f}" as="geometry"/></mxCell>'
        )
        cy = self.cabecalho + PAD
        for item in self.itens:
            ix = PAD + (self.col_w - item.w) / 2
            item.emitir(saida, self.id, ix, cy)
            if isinstance(item, Pergunta):
                rx = PAD + self.col_w + GAP
                for ramo in item.ramos:
                    ry = cy + item.topo_ramos
                    for sub in ramo.itens:
                        sub.emitir(saida, self.id, rx + (ramo.w - sub.w) / 2, ry)
                        ry += sub.h + VGAP
                    rx += ramo.w + BGAP
                cy += item.linha_h + VGAP
            else:
                cy += item.h + VGAP


def T(t, **k):
    return No('terminal', t, **k)


def S(t, **k):
    return No('step', t, **k)


def F(nome, descricao='', **k):
    texto = f'<font face="Courier New"><b>{escape(nome)}</b></font>'
    return No('func', texto + (f'<br>{descricao}' if descricao else ''), **k)


def G(t, **k):
    return No('goto', t, **k)


def M(t, **k):
    return No('marker', t, **k)


def R(t, **k):
    return No('removed', t, **k)


def MEMO(t, **k):
    return No('memo', '📄 ' + t, **k)


def PDF(t, **k):
    return No('pdf', t, **k)


def E(t, **k):
    return No('error', t, **k)


def N(t, **k):
    return No('note', t, **k)


def D(t, ramos, segue='Não', **k):
    return Pergunta(t, ramos, segue, **k)


def B(rotulo, itens, volta=False, ir_para=None):
    return Ramo(rotulo, itens, volta, ir_para)


def FR(nome, descricao, itens, nivel=1, chave=None):
    return Moldura(nome, descricao, itens, nivel, chave)


# --- setas --------------------------------------------------------------------

_setas = []
_chaves = {}


def _seta(origem, destino, rotulo='', estilo_extra=''):
    erro = getattr(destino, 'tipo', '') == 'error'
    estilo = (ESTILO_SETA_ERRO if erro else ESTILO_SETA) + estilo_extra
    _setas.append(
        f'<mxCell id="{_novo_id()}" value="{escape(rotulo)}" style="{estilo}" edge="1" parent="1" source="{origem.id}" target="{destino.id}"><mxGeometry relative="1" as="geometry"/></mxCell>'
    )


def _registrar_chaves(item):
    if getattr(item, 'chave', None):
        _chaves[item.chave] = item
    for sub in getattr(item, 'itens', []):
        _registrar_chaves(sub)
    for ramo in getattr(item, 'ramos', []):
        for sub in ramo.itens:
            _registrar_chaves(sub)


def _ligar(moldura):
    itens = moldura.itens
    for i, item in enumerate(itens):
        prox = itens[i + 1] if i + 1 < len(itens) else None
        if isinstance(item, Moldura):
            _ligar(item)
        if prox is not None:
            rotulo = item.segue if isinstance(item, Pergunta) else ''
            if not (isinstance(item, Pergunta) and item.segue is None):
                _seta(item, prox, rotulo or '', 'exitX=0.5;exitY=1;entryX=0.5;entryY=0;')
        if isinstance(item, Pergunta):
            for ramo in item.ramos:
                _seta(item, ramo.itens[0], ramo.rotulo, 'exitX=1;exitY=0.5;entryX=0.5;entryY=0;')
                for a, b in zip(ramo.itens, ramo.itens[1:]):
                    _seta(a, b, '', 'exitX=0.5;exitY=1;entryX=0.5;entryY=0;')
                for sub in ramo.itens:
                    if isinstance(sub, Moldura):
                        _ligar(sub)
                if ramo.volta and prox is not None:
                    _seta(ramo.itens[-1], prox, '', 'exitX=0.5;exitY=1;entryX=1;entryY=0.5;dashed=1;')
                if ramo.ir_para:
                    _ir.append((ramo.itens[-1], ramo.ir_para))


_ir = []

# --- conteúdo -----------------------------------------------------------------

avaliar_disa = FR(
    '_avaliar_disa()',
    'Consulta a base geral e a base DISA e adiciona os marcadores da avaliação',
    [
        FR(
            'avaliar_uso_rede_propria_disa()',
            'Procura titular e dependentes nas duas bases. Fora da base DISA = não usou',
            [
                F('_preparar_matriculas()', 'Normaliza as matrículas (sem hífen, ponto, barra, espaço e zeros à esquerda)'),
                D('Sem titular ou matrícula<br>em formato inválido?', [B('Sim', [E('<b>ErroAvaliacao</b>')])]),
                F('_nao_encontradas()', 'Quem falta na base geral e quem falta na base DISA'),
                F('_consultar_disa()', 'Quem usou e quem não usou a rede própria segundo a base DISA'),
                D('Resposta inválida<br>na base DISA?', [B('Sim', [E('<b>ErroAvaliacao</b>')])]),
            ],
        ),
        F('registrar_uso()', 'Colunas tit_usou, deps_que_usaram, deps_que_nao_usaram (e as de matrículas não encontradas)'),
        G('<b>garantir_marcadores_no_sei()</b><br>1.2.2, 1.6 e, se faltou na base geral, 1.2.1 e 1.6.1'),
        D('Faltou matrícula<br>na base DISA?', [B('Sim', [G('<b>adicionar_tag_se_ausente()</b>'), M('➕ 1.2.2 - Mat. N Encontradas Base DISA<br>(informativo; conta como não uso)')], volta=True)]),
        D(
            'Etapa 1.6 ainda não feita?<br>(_etapa_feita)',
            [B('Sim', [G('<b>adicionar_tag()</b>'), M('➕ 1.6 - Avaliado Uso Rede Própria DISA'), R('➖ remove o estado anterior (se houver)')], volta=True)],
            segue='Não (retomada)',
        ),
    ],
)

avaliar_mantis = FR(
    '_avaliar_mantis_e_criar_docs()',
    'MANTIS, relatórios em PDF e memos DISA/DEPROC. O memo à DISA depende só do uso da rede própria no MANTIS (a base DISA não decide)',
    [
        FR(
            'avaliar_uso_rede_propria_mantis()',
            'Uso das duas redes no período de apuração do titular (titular e dependentes)',
            [
                F('interpretar_periodo()', 'Converte o período do titular em intervalos de datas'),
                D('Período não reconhecido,<br>data inválida ou<br>início depois do fim?', [B('Sim', [E('<b>ErroAvaliacao</b>')])]),
                F('_consultar() → _no_periodo()', 'Atendimentos no período, por rede (própria e credenciada), com os detalhes para os PDFs'),
                D('Atendimento sem<br>data válida?', [B('Sim', [E('<b>ErroAvaliacao</b>')])]),
            ],
        ),
        F('_registrar_uso_mantis()', 'Colunas de uso e valores do MANTIS (rede própria e credenciada)'),
        F('usos_mantis_alem_disa()', 'Quem usou no MANTIS e não consta na base DISA (coluna mats_uso_mantis_alem_disa; citado no memo à DISA)'),
        S('usou_rede_propria = alguém usou a rede própria no MANTIS <b>ou</b> o processo já tem 1.9'),
        S('Monta os memos <b>antes de qualquer ação no SEI</b>:<br>MemoDisa (uso RP no MANTIS e 1.9 não feito)<br>MemoDeproc (fluxo normal)<br>MemoDeprocRedeCredenciada (VELHO sem uso RP)'),
        D('Texto do memo pendente?<br>(TEXTO_DEFINIDO = False)', [B('Sim', [E('<b>TextoMemoPendente</b><br>nenhum relatório nem memo criado')])]),
        G('<b>garantir_marcadores_no_sei()</b><br>1.8, [1.9] e o marcador de conclusão'),
        D(
            'Etapa 1.8 ainda não feita?<br>(_etapa_feita)',
            [B('Sim', [G('<b>adicionar_tag()</b>'), M('➕ 1.8 - Avaliado Uso Rede Própria MANTIS'), R('➖ 1.6 - Avaliado Uso Rede Própria DISA')], volta=True)],
            segue='Não (retomada)',
        ),
        D(
            'Há memo à DISA a criar?<br>(uso RP no MANTIS<br>e ainda sem 1.9)',
            [
                B(
                    'Sim',
                    [
                        G('<b>incluir_relatorios()</b> — Rede Própria'),
                        PDF('📎 PDF Utilização Tit. / Dep. RP<br>(titular e/ou dependentes com atendimento)'),
                        G('<b>incluir_relatorios()</b> — Rede Credenciada<br><b>só VELHO</b>'),
                        PDF('📎 PDF Utilização Tit. / Dep. RC (só VELHO)'),
                        G('<b>incluir_memo()</b>'),
                        MEMO('MemoDisa: validar os atendimentos da rede própria (indica quem consta ou não na base DISA)<br>bloco 7697744'),
                        G('<b>adicionar_tag()</b> — só fluxo normal'),
                        M('➕ 1.9 - Memo DISA Uso Rede Própria'),
                        R('➖ 1.8 - Avaliado Uso Rede Própria MANTIS'),
                    ],
                    volta=True,
                )
            ],
        ),
        D(
            'Há memo DEPROC a criar?<br>(normal: sempre;<br>VELHO: só sem uso RP)',
            [
                B(
                    'Sim',
                    [
                        G('<b>incluir_relatorios()</b> — Rede Credenciada'),
                        PDF('📎 PDF Utilização Tit. / Dep. RC<br>(só de quem usou; se ninguém usou, o memo diz isso)'),
                        G('<b>incluir_memo()</b>'),
                        MEMO('Normal: MemoDeproc (todos os beneficiários; cita a rede credenciada)<br>VELHO: MemoDeprocRedeCredenciada (complementar)<br>bloco 7697744'),
                    ],
                    volta=True,
                )
            ],
        ),
        D(
            'Qual conclusão?<br>(adicionar_tag)',
            [
                B(
                    'Normal, com<br>memo DISA',
                    [M('➕ 1.10 - Memos DISA e DEPROC no Bloco', largura=230), R('➖ 1.9', largura=230), T('prox_acao = Assinar memos DISA e DEPROC e encaminhar', largura=230)],
                    volta=True,
                ),
                B(
                    'Normal, sem<br>memo DISA',
                    [M('➕ 1.10 - Memo DEPROC Coparticipação', largura=230), R('➖ 1.8', largura=230), T('prox_acao = Assinar memo DEPROC e encaminhar', largura=230)],
                    volta=True,
                ),
                B(
                    'VELHO com<br>uso RP',
                    [M('➕ 1.11 - VELHO Memo DISA no Bloco', largura=230), R('➖ 1.8', largura=230), T('prox_acao = VELHO: assinar memo DISA (sem DEPROC)', largura=230)],
                    volta=True,
                ),
                B(
                    'VELHO sem<br>uso RP',
                    [M('➕ 1.11 - VELHO Memo DEPROC no Bloco', largura=230), R('➖ 1.8', largura=230), T('prox_acao = VELHO: assinar memo DEPROC (rede credenciada)', largura=230)],
                    volta=True,
                ),
            ],
            segue=None,
        ),
        G('<b>_finalizar()</b> → registrar_numeros_memos()'),
    ],
)

obter_dados = FR(
    'obter_dados_ui()',
    'Lê o último memo da APIS destinado à GEACS e extrai as instruções',
    [
        F('obter_memos_apis_para_geacs()', 'Lê todos os memorandos da APIS (ler_texto_doc) e mantém os destinados à GEACS (eh_destinado_geacs). Coluna memos_apis_geacs_sei'),
        D('Nenhum memo para<br>a GEACS?', [B('Sim', [E('levanta <b>MemoApisNaoEncontrado</b>')])]),
        S('Usa o <b>último</b>. registro.docs_rodada = documentos depois dele (onde memos e PDFs já criados são procurados)'),
        F('validar_template()', 'Só o modelo novo_novo: Nome completo, Matrícula, Período do titular <b>e</b> "atualização do levantamento de utilização"'),
        D('Formato inválido?<br>(novo_velho, velho<br>ou faltam campos)', [B('Sim', [E('levanta <b>FormatoMemorandoInvalido</b><br>prox_acao = Verificar formato do memo')])]),
        F('extrair_dados_ui()', 'DadosUI: nome, matrícula e período do titular, matrículas dos dependentes e se há período variável para dependentes'),
    ],
)

processar = FR(
    'processar_novo()',
    'Fluxo de todos os processos (normal e VELHO = registro.velho). Do início ou retomando pelo estado 1.6, 1.8 ou 1.9 (_etapa_feita pula as etapas já feitas)',
    [
        N('Erros levantados aqui (vermelho) sobem para <b>_processar_linha()</b>, que chama <b>registrar_erro()</b> e segue para o próximo processo'),
        obter_dados,
        D(
            'MemoApisNaoEncontrado?',
            [
                B(
                    'Sim',
                    [
                        F('_parar_sem_memo_apis()', 'Monta MemoApisSemMemo'),
                        G('<b>_parar_com_memo()</b>'),
                        MEMO('MemoApisSemMemo<br>bloco 7730344'),
                        M('➕ 1.5 - Memo APIS Sem Memo p/ GEACS'),
                        R('➖ estado anterior (se houver)'),
                        T('prox_acao = Assinar memo à APIS (sem memorando para a GEACS)'),
                    ],
                )
            ],
        ),
        D(
            'FormatoMemorandoInvalido?',
            [
                B(
                    'Sim',
                    [
                        F('_parar_formato_invalido()', 'Preenche motivo_formato_invalido e monta MemoApisFormatoInvalido'),
                        G('<b>_parar_com_memo()</b>'),
                        MEMO('MemoApisFormatoInvalido<br>bloco 7730341'),
                        M('➕ 1.5 - Memo APIS Formato Inválido'),
                        R('➖ estado anterior (se houver)'),
                        T('prox_acao = Assinar memo à APIS (formato do memorando inválido)'),
                    ],
                )
            ],
        ),
        avaliar_disa,
        D('VELHO e alguém com SIM<br>na base DISA?', [B('Sim', [T('VELHO aguarda a DISA (sem erro e sem marcador; reavaliado a cada execução)<br>prox_acao = VELHO: aguardar retorno da DISA')])]),
        D(
            'Faltou matrícula<br>na base geral?',
            [
                B(
                    'Sim',
                    [
                        F('_parar_nao_encontradas_base_geral()'),
                        G('<b>adicionar_tag_se_ausente()</b>'),
                        M('➕ 1.2.1 - Mat. N Encontradas Base Geral'),
                        F('incluir_memo_apis_mat_nao_encontradas()', 'Erro se BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS = None; chama incluir_memo()'),
                        MEMO('MemoApisMatNaoEncontradas<br>bloco 7711907'),
                        M('➕ 1.6.1 - Memo APIS Mat. N Encontradas'),
                        R('➖ 1.6 - Avaliado Uso Rede Própria DISA'),
                        G('<b>_finalizar()</b>'),
                        T('prox_acao = Assinar memo à APIS (matrículas não encontradas)'),
                    ],
                )
            ],
        ),
        D(
            'Período variável<br>para dependentes?',
            [
                B(
                    'Sim',
                    [
                        F('_parar_periodo_variavel()', 'Monta MemoApisPeriodoDependentes'),
                        G('<b>_parar_com_memo()</b>'),
                        M('➕ 1.1 - Período Variável p/ Dependentes<br>(antes do memo)'),
                        MEMO('MemoApisPeriodoDependentes<br>bloco 7730905'),
                        M('➕ 1.7 - Memo APIS Período Dependentes'),
                        R('➖ 1.6 - Avaliado Uso Rede Própria DISA'),
                        T('prox_acao = Assinar memo à APIS (período dos dependentes)'),
                    ],
                )
            ],
        ),
        avaliar_mantis,
        T('Volta para _processar_linha()'),
    ],
    chave='processar_novo',
)

tratar = FR(
    '_tratar()',
    'Roteamento pelos marcadores lidos do SEI: parado, concluído ou segue para processar_novo(). Só adiciona o marcador 1',
    [
        D(
            'Não tem<br><b>1 - Processo NOVO</b>?<br>(inclusive com documento da GEACS<br>ou com o antigo 2 - Processo VELHO)',
            [B('Sim', [G('<b>adicionar_tag()</b>'), M('➕ 1 - Processo NOVO'), S('processar_novo() do início')], ir_para='processar_novo')],
            largura=340,
        ),
        S('registro.velho = tem <b>1.3 - Memos DISA e DEPROC no Bloco</b> (enviado à DISA e à DEPROC antes da avaliação)'),
        F('estado_atual()', 'Marcador de estado do processo (TAGS_ESTADO_NOVO) ou nenhum'),
        D('Mais de um marcador<br>de estado?', [B('Sim', [E('<b>ErroAvaliacao</b><br>remover manualmente o(s) anterior(es) no SEI')])]),
        D(
            'Estado de parada?<br>1.5 (dois), 1.6.1, 1.7, 1.8.1',
            [B('Sim', [E('<b>ErroAvaliacao</b>: parado aguardando resposta<br>prox_acao = Aguardar resposta ao memo enviado<br>(TODO: tratar a resposta)')])],
        ),
        D(
            'Estado de conclusão?<br>1.10 (dois), 1.11 (dois)',
            [
                B(
                    'Sim',
                    [
                        T(
                            'Concluído. prox_acao:<br>1.10 DISA e DEPROC → Assinar memos DISA e DEPROC<br>1.10 DEPROC → Assinar memo DEPROC'
                            '<br>1.11 VELHO DISA → VELHO: assinar memo DISA<br>1.11 VELHO DEPROC → VELHO: assinar memo DEPROC',
                            largura=340,
                        )
                    ],
                )
            ],
        ),
        D('VELHO com MANUAL<br>ou ASSINADO?', [B('Sim', [T('prox_acao = Fora do escopo (tratado manualmente)')])]),
        D('NOVO sem estado com<br>1.3 - Memo DEPROC no Bloco?', [B('Sim', [T('Concluído na versão anterior<br>prox_acao = Assinar memo DEPROC e encaminhar')])]),
        D('NOVO sem estado com<br>1.2.1 ou 1.2.2?', [B('Sim', [E('<b>ErroAvaliacao</b>: parado pela versão anterior<br>prox_acao = Verificar matrículas não encontradas')])]),
        S('Do início (sem estado) ou retomada (estado 1.6, 1.8 ou 1.9)'),
        processar,
    ],
)

processar_linha = FR(
    '_processar_linha()',
    'Uma passagem do processo: lê a árvore e os marcadores e chama o roteamento. Captura todos os erros: um erro nunca interrompe os demais processos',
    [
        F('acessar_processo()', 'Abre o processo no SEI'),
        F('listar_documentos_arvore() → registrar_arvore()', 'Árvore, documentos e memos da GEACS; docs_rodada = toda a árvore até achar o memo da APIS'),
        F('listar_marcadores() → registrar_tags()', 'marcadores_sei (lidos do SEI) e marcadores_atuais'),
        tratar,
        D(
            'Alguma exceção?',
            [
                B(
                    'ErroAvaliacao,<br>FormatoMemorandoInvalido,<br>TextoMemoPendente',
                    [E('<b>registrar_erro()</b><br>tipo_erro e erro (uma frase); prox_acao = Verificar erro, salvo a já definida (ex.: Aguardar resposta). Sem traceback')],
                    volta=True,
                ),
                B('Outra exceção', [E('<b>registrar_erro()</b> + logger.exception<br>(traceback completo no log)')], volta=True),
            ],
        ),
        T('Devolve o registro (uma linha da planilha de controle)'),
    ],
)

loop = S('<b>Para cada processo</b><br>(contexto_processo: número do processo em cada linha do log)', chave='loop')
principal = FR(
    'main()',
    'Script principal: carrega as bases, faz login e processa cada processo da planilha de entrada',
    [
        T('Início'),
        S('Cria as pastas e configura o log (configurar_logging)'),
        D('remover_marcador existe<br>na sei_automacao?<br>(REMOCAO_DE_MARCADOR_DISPONIVEL)', [B('Não', [E('<b>SystemExit</b><br>execução não iniciada (TODO na sei_automacao)')])], segue='Sim'),
        S('Lê <i>processos_nao_processados.xlsx</i><br>(aba processos_reais, coluna num_sei)'),
        F('carregar_bases()', 'Base DISA (UTILIZOU A REDE PRÓPRIA?) e base geral (todas as matrículas; DV retirado dos dependentes)'),
        F('carregar_bases_mantis()', 'MANTIS rede própria e credenciada: atendimentos por matrícula (data, valor, prestador, procedimento)'),
        F('PlanilhaControleGeral()', 'Lê a planilha de controle geral uma vez'),
        F('abrir_sei()', 'Abre o navegador e faz login (credenciais do .env)'),
        loop,
        processar_linha,
        F('controle.registrar()', 'Regrava a planilha de controle (abas processos e historico) depois de cada processo; backup antes da 1ª gravação'),
        F('log_fim_processo()', 'Loga FIM ou FIM COM ERRO e a duração'),
        D('Há mais processos?', [B('Sim', [S('Próximo processo')], ir_para='loop')]),
        F('log_resumo()', 'finally: fecha o navegador e loga o resumo (quantidade por prox_acao e erros)'),
        T('Fim'),
    ],
    nivel=0,
)

# Funções chamadas em vários pontos (laranja = referência)
auxiliares = [
    FR(
        'adicionar_tag()',
        'Única forma de adicionar marcador. Se for marcador de estado, remove o estado anterior (primeiro adiciona, depois remove)',
        [
            F('adicionar_marcador()', 'sei_automacao: adiciona o marcador no SEI'),
            M('➕ marcador (coluna marcadores_adicionados)'),
            D(
                'É marcador de estado?<br>(TAGS_ESTADO_NOVO)',
                [
                    B(
                        'Sim',
                        [
                            F('remover_tag() → remover_marcador()', 'Para cada outro estado presente. Placeholder: NotImplementedError enquanto a sei_automacao não tiver remover_marcador'),
                            R('➖ estado anterior<br>(coluna marcadores_removidos)'),
                        ],
                        volta=True,
                    )
                ],
            ),
            T('Fim'),
        ],
        nivel='aux',
    ),
    FR(
        'adicionar_tag_se_ausente()',
        'Para os informativos (1.1, 1.2.1, 1.2.2) na retomada',
        [D('Já tem o marcador?', [B('Sim', [S('Não faz nada (log de retomada)')])]), G('<b>adicionar_tag()</b>')],
        nivel='aux',
    ),
    FR(
        '_parar_com_memo()',
        'Memos à APIS que param o processo até a resposta',
        [
            G('<b>garantir_marcadores_no_sei()</b><br>tag_antes e marcador da parada'),
            G('<b>adicionar_tag_se_ausente()</b>'),
            M('➕ tag_antes, se houver (ex.: 1.1)'),
            G('<b>incluir_memo()</b>'),
            MEMO('memo da parada no bloco'),
            G('<b>adicionar_tag()</b>'),
            M('➕ marcador da parada (1.5 ou 1.7)'),
            R('➖ estado anterior'),
            G('<b>_finalizar()</b>'),
        ],
        nivel='aux',
    ),
    FR(
        'incluir_memo()',
        'Cria o memo e insere no bloco. Antes, procura pelo assunto só nos memos da GEACS da rodada (retomada sem duplicar)',
        [
            F('encontrar_memo_geacs_por_assunto()', 'Só se houver memo da GEACS na rodada: lê os memos (do mais recente ao mais antigo) e compara com PADRAO_ASSUNTO_*'),
            D('Memo já existe?', [B('Sim', [T('Retomada: não recria<br>(&lt;memo&gt;_na_arvore e &lt;memo&gt;_sei); quem chamou só adiciona o marcador')])]),
            MEMO('incluir_doc_sei_memo(): cria o memo<br>(&lt;memo&gt;_criado)'),
            MEMO('inserir_bloco_ass(bloco)<br>(&lt;memo&gt;_inserido_bloco)'),
        ],
        nivel='aux',
    ),
    FR(
        'incluir_relatorios() → _incluir()',
        'Um PDF para o titular e outro para os dependentes, só de quem tem atendimento na rede',
        [
            D('Titular / dependentes com<br>atendimento na rede?', [B('Não', [S('Nada a anexar')])], segue='Sim'),
            F('encontrar_doc_por_nome()', 'Procura na rodada "PDF Utilização Tit.|Dep. RP|RC - &lt;matrícula&gt;"'),
            D('Já anexado?', [B('Sim', [T('Retomada: não anexa de novo (relatorios_na_arvore)')])]),
            F('transformar_xls_em_pdf()', 'Gera o PDF (ReportLab) em dados/utilizacoes/mantis/pdf'),
            PDF('📎 incluir_doc_externo(): tipo PDF, Nato-digital, Restrito<br>"Utilização Tit. RP - &lt;matrícula&gt; - &lt;data_hora&gt;"<br>(relatorios_incluidos)'),
        ],
        nivel='aux',
    ),
    FR(
        'garantir_marcadores_no_sei()',
        'Chamada antes de criar memos e relatórios: os marcadores que serão adicionados existem no SEI?',
        [
            D('Lista não lida ou<br>falta algum nome?', [B('Sim', [F('_ler_marcadores_da_unidade()', 'Tela Gerenciar Marcador, sem salvar (uma vez por execução; relê se faltar)')], volta=True)]),
            D('Falta marcador<br>no SEI?', [B('Sim', [E('<b>ErroAvaliacao</b><br>marcador não cadastrado; nenhum memo criado')])]),
            T('Fim'),
        ],
        nivel='aux',
    ),
    FR(
        '_finalizar() → registrar_numeros_memos()',
        'Define a prox_acao e obtém o número SEI dos memos criados na passagem',
        [
            S('registro.prox_acao = ...'),
            F('memos_geacs_novos()', 'Relê a árvore: memos da GEACS que não estavam no início, na ordem de criação'),
            D('Falhou ou quantidade<br>diferente?', [B('Sim', [S('Só log (não afeta o processo)')])]),
            S('Preenche &lt;memo&gt;_sei'),
        ],
        nivel='aux',
    ),
]

legenda = FR(
    'Legenda',
    '',
    [
        FR('função()', 'Moldura: função; molduras aninhadas = funções chamadas por ela', [S('passos na ordem de execução; desvios à direita')]),
        F('função()', 'Função chamada (o que ela faz)'),
        G('<b>função()</b> detalhada na coluna da direita'),
        D('Pergunta', [B('Sim', [S('desvio')])]),
        M('➕ Marcador adicionado'),
        R('➖ Marcador removido'),
        MEMO('Memo criado e inserido no bloco'),
        PDF('📎 Relatório PDF anexado (documento externo)'),
        E('<b>Erro</b> (processo termina com registrar_erro)'),
        T('Início / fim / prox_acao'),
        N('Seta tracejada: volta ao fluxo principal. Seta vermelha: leva a erro'),
    ],
    nivel='aux',
)

notas = N(
    '<b>Pendências (TODO)</b><br>'
    '• remover_marcador na sei_automacao (sem ele o main não inicia)<br>'
    '• cadastrar no SEI: 1.10 Memos DISA e DEPROC, 1.11 VELHO Memo DISA, 1.11 VELHO Memo DEPROC<br>'
    '• revisar textos: MemoDisa, MemoDeprocRedeCredenciada, memos à APIS (TEXTO_DEFINIDO)<br>'
    '• tratar a resposta dos processos parados e dos VELHOS que aguardam a DISA<br>'
    '• pesquisa da utilização indevida em si',
    largura=420,
)

# --- montagem -----------------------------------------------------------------

celulas = []
titulo_id = _novo_id()
celulas.append(
    f'<mxCell id="{titulo_id}" value="{escape("Fluxo completo — script-sei-utilizacao-indevida-v2 (main.py)")}" '
    'style="text;html=1;align=left;verticalAlign=middle;fontSize=24;fontStyle=1;" vertex="1" parent="1">'
    '<mxGeometry x="40" y="20" width="900" height="40" as="geometry"/></mxCell>'
)
principal.emitir(celulas, '1', 40, 80)

x_aux = 40 + principal.w + 160
y = 80
sub_id = _novo_id()
celulas.append(
    f'<mxCell id="{sub_id}" value="Funções chamadas em vários pontos" style="text;html=1;align=left;verticalAlign=middle;fontSize=18;fontStyle=1;" vertex="1" parent="1">'
    f'<mxGeometry x="{x_aux}" y="40" width="600" height="34" as="geometry"/></mxCell>'
)
for bloco in [legenda, notas, *auxiliares]:
    bloco.emitir(celulas, '1', x_aux, y)
    y += bloco.h + 60

for raiz in [principal, legenda, *auxiliares]:
    _registrar_chaves(raiz)
    _ligar(raiz)
for origem, chave in _ir:
    destino = _chaves[chave]
    _seta(origem, destino, '', 'exitX=0.5;exitY=1;entryX=1;entryY=0.05;dashed=1;' if chave == 'processar_novo' else 'exitX=1;exitY=0.5;entryX=1;entryY=0.5;dashed=1;')

largura_total = x_aux + max(b.w for b in [legenda, *auxiliares]) + 80
altura_total = max(80 + principal.h, y) + 80
xml = (
    '<mxfile host="app.diagrams.net" type="device">'
    f'<diagram id="fluxo-completo" name="Fluxo completo">'
    f'<mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
    f'pageWidth="{largura_total:.0f}" pageHeight="{altura_total:.0f}" math="0" shadow="0">'
    '<root><mxCell id="0"/><mxCell id="1" parent="0"/>' + ''.join(celulas) + ''.join(_setas) + '</root></mxGraphModel></diagram></mxfile>\n'
)
with open(SAIDA, 'w', encoding='utf-8') as f:
    f.write(xml)
print(f'{len(celulas)} células, {len(_setas)} setas, página {largura_total:.0f} x {altura_total:.0f}')
