from dataclasses import dataclass

REFERENCIA_PLANILHA_REDE_PROPRIA = '<strong>Planilha BENEFICIÁRIOS ATENDIDOS NA REDE PRÓPRIA (SEI nº 149768791)</strong>, disponibilizada no processo 2010.01.0058549/2026-56'


@dataclass(frozen=True)
class UsoRedeBeneficiarios:
    """Uso da rede própria segundo a base DISA."""

    matricula_titular: str
    tit_usou: bool
    deps_que_usaram: tuple[str, ...] = ()
    deps_que_nao_usaram: tuple[str, ...] = ()

    @property
    def alguem_usou(self) -> bool:
        return self.tit_usou or bool(self.deps_que_usaram)
