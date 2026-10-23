"""SEI simulado em memória para os testes do fluxo.

Guarda a árvore (documentos e textos) e os marcadores de um processo e
substitui as funções da sei_automacao usadas pelo script.
"""

from dataclasses import replace
from datetime import date
from pathlib import Path

import docs_processo
import main
import memos_sei
import processar_novo
import relatorios_mantis
import tags
from constantes import UNIDADE_APIS, UNIDADE_GEACS
from mantis import Atendimento, BaseMantis, BasesMantis
from rede_propria import BasesUso

from script_sei_utilizacao_indevida_v2.memorandos import (
    MemoApisFormatoInvalido,
    MemoApisPeriodoDependentes,
    MemoApisSemMemo,
    MemoApisSemUso,
    MemoDisa,
)

# Modelo novo_novo (único aceito)
MEMO_APIS = """Memorando IPSEMG/APIS-UTILIZAÇÃO nº. 1/2026
Para: Bruna Miller Lavarini
solicita-se à Gerência de Auditoria e Contas da Saúde – GEACS atualização do levantamento de utilização da assistência à saúde
Nome completo: FULANO
Matrícula: 1234567 / 8
Período de apuração do titular: (01/2024 a 06/2024)
Matrícula dos dependentes: 555
{extra}
Documento assinado eletronicamente"""

# Mesmos campos, sem o pedido de atualização do levantamento
MEMO_APIS_NOVO_VELHO = MEMO_APIS.replace('atualização do levantamento', 'o levantamento')

TITULAR = '12345678'
DEPENDENTE = '555'

_VAZIA = BaseMantis('vazia', {}, {})
_ATENDIMENTO = Atendimento(date(2024, 3, 1), 10.0, prestador='HOSPITAL', procedimento='CONSULTA')
MANTIS_SEM_USO = BasesMantis(_VAZIA, _VAZIA)
# Dependente com atendimento na rede própria do MANTIS dentro do período
MANTIS_DEPENDENTE_USOU = BasesMantis(BaseMantis('rede própria', {}, {DEPENDENTE: (_ATENDIMENTO,)}), _VAZIA)
# Titular (sem DV no MANTIS) com atendimento na rede credenciada
MANTIS_CREDENCIADA_TITULAR_USOU = BasesMantis(_VAZIA, BaseMantis('rede credenciada', {TITULAR[:-1]: (_ATENDIMENTO,)}, {}))
MANTIS_DUAS_REDES = BasesMantis(MANTIS_DEPENDENTE_USOU.rede_propria, MANTIS_CREDENCIADA_TITULAR_USOU.rede_credenciada)


def bases(*, tit_usou=True, tit_na_disa=True, tit_na_apis=True) -> BasesUso:
    return BasesUso(
        titulares={TITULAR: tit_usou} if tit_na_disa else {},
        dependentes={DEPENDENTE: False},
        apis_titulares=frozenset({TITULAR} if tit_na_apis else set()),
        apis_dependentes=frozenset({DEPENDENTE}),
    )


def curto(tag: str) -> str:
    return tag.removeprefix('Script v2 - ')


class SEIFalso:
    def __init__(self):
        self.docs: list[dict] = []
        self.tags: list[str] = []
        self.textos: dict[str, str] = {}
        self._numero = 1000
        self.memos_passagem = 0
        # Falha ao criar o n-ésimo memo da passagem
        self.falhar_memo_n: int | None = None
        self.falhar_remocao = False

    # --- árvore -------------------------------------------------------------

    def novo_doc(self, nome: str, unidade: str, texto: str) -> str:
        self._numero += 1
        numero = str(self._numero)
        self.docs.append({'nome_arvore': nome, 'unidade': unidade, 'numero_sei': numero})
        self.textos[numero] = texto
        return numero

    def memo_apis(self, texto: str = MEMO_APIS, *, extra: str = '') -> str:
        return self.novo_doc('Memorando 7', UNIDADE_APIS, texto.format(extra=extra))

    def novo_processo(self, *, extra: str = '', com_memo_apis: bool = True) -> None:
        self.novo_doc('E-mail', UNIDADE_APIS, 'e-mail')
        if com_memo_apis:
            self.memo_apis(extra=extra)

    def memo_geacs(self, assunto: str) -> str:
        return self.novo_doc('Memorando 1', UNIDADE_GEACS, f'Assunto: {assunto}')

    def memo_geacs_para(self, destino: str, data: str | None = '18 de setembro de 2026') -> str:
        """Memo da GEACS com destinatário e data (identificação do VELHO)."""
        linha_data = f'Belo Horizonte, {data}.' if data else ''
        return self.novo_doc('Memorando 1', UNIDADE_GEACS, f'Para: {destino}\nAssunto: memo\n{linha_data}')

    def _memos_geacs(self) -> list[dict]:
        return [doc for doc in self.docs if doc['unidade'] == UNIDADE_GEACS and 'Memorando' in doc['nome_arvore']]

    @property
    def qnt_memos_geacs(self) -> int:
        return len(self._memos_geacs())

    @property
    def assuntos_memos_geacs(self) -> list[str]:
        return [self.textos[doc['numero_sei']].splitlines()[0].removeprefix('Assunto: ') for doc in self._memos_geacs()]

    @property
    def pdfs(self) -> list[str]:
        """Nome dos relatórios sem a data e hora da inclusão."""
        return [doc['nome_arvore'].rsplit(' - ', 1)[0] for doc in self.docs if doc['nome_arvore'].startswith('PDF ')]

    @property
    def nomes(self) -> list[str]:
        return [doc['nome_arvore'] for doc in self.docs]

    @property
    def tags_curtas(self) -> list[str]:
        return [curto(t) for t in self.tags]

    # --- substitutos da sei_automacao ---------------------------------------

    def _adicionar_marcador(self, driver, tag):
        if tag not in self.tags:
            self.tags.append(tag)

    def _remover_marcador(self, driver, tag):
        if self.falhar_remocao:
            raise RuntimeError('falha simulada ao remover marcador')
        self.tags.remove(tag)

    def _incluir_memo(self, driver, **kwargs):
        self.memos_passagem += 1
        if self.falhar_memo_n == self.memos_passagem:
            raise RuntimeError('falha simulada ao criar memo')
        self.novo_doc('Memorando 1', UNIDADE_GEACS, f'Assunto: {kwargs["assunto"]}\n{kwargs["texto_principal"]}')

    def _incluir_doc_externo(self, driver, *, tipo_doc, num, **kwargs):
        self.novo_doc(f'{tipo_doc} {num}', UNIDADE_GEACS, '')

    def instalar(self, monkeypatch) -> None:
        def arvore(driver):
            return [dict(doc) for doc in self.docs]

        monkeypatch.setattr(tags, 'adicionar_marcador', self._adicionar_marcador)
        monkeypatch.setattr(tags, 'remover_marcador', self._remover_marcador)
        monkeypatch.setattr(main, 'acessar_processo', lambda driver, num: None)
        monkeypatch.setattr(main, 'listar_documentos_arvore', arvore)
        monkeypatch.setattr(docs_processo, 'listar_documentos_arvore', arvore)
        monkeypatch.setattr(main, 'listar_marcadores', lambda driver: list(self.tags))
        monkeypatch.setattr(memos_sei, 'incluir_doc_sei_memo', self._incluir_memo)
        monkeypatch.setattr(memos_sei, 'inserir_bloco_ass', lambda driver, bloco: None)
        monkeypatch.setattr(docs_processo, 'ler_texto_doc', lambda driver, doc: self.textos[doc['numero_sei']])
        monkeypatch.setattr(processar_novo, 'garantir_marcadores_no_sei', lambda driver, lista: None)
        monkeypatch.setattr(main, 'garantir_marcadores_no_sei', lambda driver, lista: None)
        # Blocos dos memos à DISA e à APIS (sem uso) ainda não configurados (None)
        for nome, bloco in (('_DISA_VALIDAR_CONSTA', 1), ('_DISA_VALIDAR_NAO_CONSTA', 2), ('_DISA_SEM_MANTIS_RELATORIO', 3), ('_APIS_SEM_USO', 4)):
            monkeypatch.setattr(processar_novo, nome, replace(getattr(processar_novo, nome), bloco=bloco))
        monkeypatch.setattr(relatorios_mantis, 'incluir_doc_externo', self._incluir_doc_externo)
        monkeypatch.setattr(relatorios_mantis, 'transformar_xls_em_pdf', lambda **kwargs: Path('relatorio.pdf'))
        # Memos com texto pendente: liberados para testar o fluxo
        for memo in (MemoApisSemMemo, MemoApisFormatoInvalido, MemoApisPeriodoDependentes, MemoApisSemUso, MemoDisa):
            monkeypatch.setattr(memo, 'TEXTO_DEFINIDO', True)

    def passar(self, bases_uso: BasesUso, bases_mantis: BasesMantis = MANTIS_SEM_USO):
        """Uma passagem do processo pelo main.py."""
        self.memos_passagem = 0
        return main._processar_linha(None, 'PROC', bases_uso, bases_mantis)
