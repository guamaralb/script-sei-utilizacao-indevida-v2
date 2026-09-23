from dataclasses import dataclass, field

from sei_automacao.classes.Memorando import Memorando


@dataclass(frozen=True)
class UsoRedeBeneficiarios:
    matricula_titular: str
    tit_usou: bool = False
    tit_nao_usou: bool = False
    deps_que_usaram: list[str] = field(default_factory=list)
    deps_que_nao_usaram: list[str] = field(default_factory=list)

    @property
    def alguem_nao_usou(self) -> bool:
        return self.tit_nao_usou or bool(self.deps_que_nao_usaram)

    def _listar(self, incluir_titular: bool, dependentes: list[str]) -> str:
        itens = []
        if incluir_titular:
            itens.append(f'Titular, matrícula {self.matricula_titular}')
        itens += [f'Dependente, matrícula {m}' for m in dependentes]
        return '; '.join(itens) + '.' if itens else 'Nenhum beneficiário.'

    def texto_usaram(self) -> str:
        return self._listar(self.tit_usou, self.deps_que_usaram)

    def texto_nao_usaram(self) -> str:
        return self._listar(self.tit_nao_usou, self.deps_que_nao_usaram)


def _par_intro():
    return (
        'Após consulta à base de beneficiários atendidos na rede própria, '
        'verificou-se a seguinte situação quanto aos beneficiários vinculados '
        'a este processo:'
    )


def _par_usaram(uso: UsoRedeBeneficiarios):
    return 'Utilizaram a rede própria: ' + uso.texto_usaram()


def _par_nao_usaram(uso: UsoRedeBeneficiarios):
    return 'Não utilizaram a rede própria: ' + uso.texto_nao_usaram()


def _par_fecho():
    return 'Atenciosamente,'


class MemoDisaUsoRede(Memorando):
    def __init__(
        self,
        *,
        nome_signatario: str,
        cargo_signatario: str,
        uso: UsoRedeBeneficiarios,
    ):
        super().__init__(
            destinatario_nome='IPSEMG/DISA-UTI-INDEV',
            assunto='ASSUNTO MEMO TESTE',
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                _par_intro(),
                _par_usaram(uso),
                _par_nao_usaram(uso),
                '',
                _par_fecho(),
            ],
        )
