"""SEI simulado em memória para os testes do fluxo.

Guarda a árvore (documentos e textos) e os marcadores de um processo e
substitui as funções da sei_automacao usadas pelo script.
"""

from datetime import date

import correcao_rede_propria
import docs_processo
import main
import matriculas_nao_encontradas
import memos_sei
import processar_novo
import tags
from constantes import UNIDADE_APIS, UNIDADE_GEACS
from mantis import Atendimento, BaseMantis, BasesMantis
from rede_propria import BasesUso

from script_sei_utilizacao_indevida_v2.memorandos import (
    MemoApisFormatoInvalido,
    MemoApisPeriodoDependentes,
    MemoApisSemMemo,
    MemoDisaValidarUsosMantis,
)

MEMO_APIS = """IPSEMG/APIS-UTILIZAÇÃO
Solicita-se à Gerência de Auditoria e Contas da Saúde - GEACS
Nome completo: FULANO
Matrícula: 1234567-8
Período de apuração do titular: 01/2024 a 06/2024
Matrícula dos dependentes: 555
{extra}
Documento assinado eletronicamente"""

TITULAR = '12345678'
DEPENDENTE = '555'

_VAZIA = BaseMantis('vazia', {}, {})
MANTIS_SEM_USO = BasesMantis(_VAZIA, _VAZIA)
# Dependente com atendimento na rede própria do MANTIS dentro do período
MANTIS_DEPENDENTE_USOU = BasesMantis(BaseMantis('rede própria', {}, {DEPENDENTE: (Atendimento(date(2024, 3, 1), 10.0),)}), _VAZIA)


def bases(*, tit_usou=True, tit_na_disa=True, tit_na_geral=True) -> BasesUso:
    return BasesUso(
        titulares={TITULAR: tit_usou} if tit_na_disa else {},
        dependentes={DEPENDENTE: False},
        geral_titulares=frozenset({TITULAR} if tit_na_geral else set()),
        geral_dependentes=frozenset({DEPENDENTE}),
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

    def novo_processo(self, *, extra: str = '', com_memo_apis: bool = True) -> None:
        self.novo_doc('E-mail', UNIDADE_APIS, 'e-mail')
        if com_memo_apis:
            self.novo_doc('Memorando 7', UNIDADE_APIS, MEMO_APIS.format(extra=extra))

    def memo_geacs(self, assunto: str) -> str:
        return self.novo_doc('Memorando 1', UNIDADE_GEACS, f'Assunto: {assunto}')

    @property
    def qnt_memos_geacs(self) -> int:
        return sum(1 for doc in self.docs if doc['unidade'] == UNIDADE_GEACS)

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
        for modulo in (processar_novo, matriculas_nao_encontradas, correcao_rede_propria):
            monkeypatch.setattr(modulo, 'garantir_marcadores_no_sei', lambda driver, lista: None)
        monkeypatch.setattr(correcao_rede_propria, 'reabrir_processo', lambda driver: None)
        # Memos com texto pendente: liberados para testar o fluxo
        for memo in (MemoApisSemMemo, MemoApisFormatoInvalido, MemoApisPeriodoDependentes, MemoDisaValidarUsosMantis):
            monkeypatch.setattr(memo, 'TEXTO_DEFINIDO', True)

    def passar(self, bases_uso: BasesUso, bases_mantis: BasesMantis = MANTIS_SEM_USO):
        """Uma passagem do processo pelo main.py."""
        self.memos_passagem = 0
        return main._processar_linha(None, 'PROC', bases_uso, bases_mantis)
