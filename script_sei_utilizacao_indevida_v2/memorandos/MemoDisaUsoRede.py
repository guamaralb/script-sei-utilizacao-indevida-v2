import re
from dataclasses import dataclass

from sei_automacao.classes.Memorando import Memorando

_CLASSE_PARAGRAFO = 'Texto_Justificado_Recuo_Primeira_Linha'

REFERENCIA_PLANILHA_REDE_PROPRIA = 'Planilha BENEFICIÁRIOS ATENDIDOS NA REDE PRÓPRIA (SEI nº 149768791), disponibilizada no processo 2010.01.0058549/2026-56'

ASSUNTO_MEMO_USO_REDE = 'Relação de Beneficiários Quanto ao Uso da Rede Própria'

# Também aceita a grafia antiga do assunto ("Quanto ao Rede Prória"),
# usada em memos que já tenham sido criados.
PADRAO_ASSUNTO_MEMO_USO_REDE = re.compile(
    r'Rela[çc][ãa]o\s+de\s+Benefici[áa]rios\s+Quanto\s+ao\s+'
    r'(?:Uso\s+da\s+)?Rede\s+Pr[óo]p?ria',
    flags=re.IGNORECASE,
)


def _p(conteudo: str) -> str:
    return f'<p class="{_CLASSE_PARAGRAFO}">{conteudo}</p>'


def _bloco_html(titulo: str, itens: list[str]) -> str:
    linhas = itens or ['Nenhum beneficiário.']
    return _p(f'<strong>{titulo}</strong>') + ''.join(_p(i) for i in linhas)


@dataclass(frozen=True)
class UsoRedeBeneficiarios:
    matricula_titular: str
    tit_usou: bool
    deps_que_usaram: tuple[str, ...] = ()
    deps_que_nao_usaram: tuple[str, ...] = ()

    @property
    def tit_nao_usou(self) -> bool:
        return not self.tit_usou

    @property
    def alguem_usou(self) -> bool:
        return self.tit_usou or bool(self.deps_que_usaram)

    @property
    def alguem_nao_usou(self) -> bool:
        return self.tit_nao_usou or bool(self.deps_que_nao_usaram)

    def _itens(self, incluir_titular: bool, dependentes) -> list[str]:
        itens = []
        if incluir_titular:
            itens.append(f'TITULAR: matrícula {self.matricula_titular}')
        itens += [f'DEPENDENTE: matrícula {m}' for m in dependentes]
        return itens

    def itens_usaram(self) -> list[str]:
        return self._itens(self.tit_usou, self.deps_que_usaram)

    def itens_nao_usaram(self) -> list[str]:
        return self._itens(self.tit_nao_usou, self.deps_que_nao_usaram)

    def situacao_uso_html(self) -> str:
        return _bloco_html('Utilizaram a rede própria:', self.itens_usaram()) + _bloco_html('NÃO utilizaram a rede própria:', self.itens_nao_usaram())


def _par_intro():
    return f'Conforme a {REFERENCIA_PLANILHA_REDE_PROPRIA}, verificou-se a seguinte situação quanto aos beneficiários relacionados ao presente processo:'


def _par_fecho():
    return 'Atenciosamente,'


class MemoDisaUsoRede(Memorando):
    """Memo do fluxo de correção: informa à DISA quem usou e quem não usou
    a rede própria. Só deve existir se alguém NÃO usou."""

    def __init__(
        self,
        *,
        nome_signatario: str,
        cargo_signatario: str,
        uso: UsoRedeBeneficiarios,
    ):
        if not uso.alguem_nao_usou:
            raise ValueError('Memorando de uso da rede própria criado sem beneficiários que NÃO utilizaram a Rede Própria')

        super().__init__(
            destinatario_nome='IPSEMG/DISA-UTI-INDEV',
            assunto=ASSUNTO_MEMO_USO_REDE,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                _par_intro(),
                uso.situacao_uso_html(),
                '',
                '',
                '',
                _par_fecho(),
            ],
        )
