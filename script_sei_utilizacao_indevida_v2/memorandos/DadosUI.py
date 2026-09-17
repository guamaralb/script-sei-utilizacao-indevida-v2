from dataclasses import dataclass


@dataclass
class DadosUI:
    nome_titular: str
    matricula_titular: str
    periodo_titular: str
    periodo_dependentes: bool
    matriculas_dependentes: str = None
