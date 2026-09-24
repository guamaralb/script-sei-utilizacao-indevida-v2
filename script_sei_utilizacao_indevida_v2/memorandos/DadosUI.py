from dataclasses import dataclass


@dataclass
class DadosUI:
    nome_titular: str
    matricula_titular: str
    periodo_titular: str
    # Modelo novo: bool (há datas para dependentes).
    # Modelo velho: datas unidas por "; " ou None.
    periodo_dependentes: bool | str | None
    matriculas_dependentes: str | None = None

    def texto_levantamento_html(self) -> str:
        infos_dep_html = ''

        if self.matriculas_dependentes:
            infos_dep_html = f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Matrículas dos dependentes:</strong> {self.matriculas_dependentes}</p>'
            if self.periodo_dependentes:
                infos_dep_html += '<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Período de apuração dos dependentes:</strong> [ANALISAR]</p>'

        return (
            f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Nome do titular:</strong> {self.nome_titular}</p>'
            f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Matrícula:</strong> {self.matricula_titular}</p>'
            f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Período de apuração do titular:</strong> {self.periodo_titular}</p>' + infos_dep_html
        )
