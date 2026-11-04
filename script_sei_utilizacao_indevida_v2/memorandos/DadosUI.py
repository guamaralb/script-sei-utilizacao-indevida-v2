from dataclasses import dataclass

# Partículas do nome que não entram nas iniciais
_PARTICULAS_NOME = frozenset({'de', 'da', 'do', 'das', 'dos', 'e', 'd', 'di', 'du', 'del'})


def iniciais_nome(nome: str) -> str:
    """Iniciais do nome, sem as partículas: 'José da Silva e Souza' -> 'J.S.S.'."""
    partes = nome.replace("'", ' ').replace('’', ' ').replace('-', ' ').split()
    return ''.join(f'{p[0].upper()}.' for p in partes if p.lower() not in _PARTICULAS_NOME)


@dataclass
class DadosUI:
    nome_titular: str
    matricula_titular: str
    periodo_titular: str
    # Há datas específicas para os dependentes no memo da APIS (o fluxo para
    # com memo à APIS)
    periodo_dependentes: bool
    matriculas_dependentes: str | None = None
    # Modelo com período por dependente: matrícula do dependente (como no
    # memo) -> período de apuração. None nos outros modelos
    periodos_por_dependente: dict[str, str] | None = None

    @property
    def nome_titular_iniciais(self) -> str:
        """Usado nos memorandos no lugar do nome (LGPD)."""
        return iniciais_nome(self.nome_titular)

    def texto_levantamento_html(self) -> str:
        infos_dep_html = ''

        if self.matriculas_dependentes:
            infos_dep_html = f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Matrículas dos dependentes:</strong> {self.matriculas_dependentes}</p>'
            if self.periodo_dependentes:
                infos_dep_html += '<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Período de apuração dos dependentes:</strong> [ANALISAR]</p>'
            for matricula, periodo in (self.periodos_por_dependente or {}).items():
                infos_dep_html += f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Período de apuração do dependente {matricula}:</strong> {periodo}</p>'

        return (
            f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Iniciais do titular:</strong> {self.nome_titular_iniciais}</p>'
            f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Matrícula:</strong> {self.matricula_titular}</p>'
            f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Período de apuração do titular:</strong> {self.periodo_titular}</p>' + infos_dep_html
        )

    def periodo_dependentes_html(self) -> str:
        """O período do titular vale para os dependentes: o processo com
        período variável para antes da DEPROC."""
        if not self.matriculas_dependentes or self.periodo_dependentes:
            return ''
        return f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Período de apuração dos dependentes:</strong> {self.periodo_titular}</p>'
