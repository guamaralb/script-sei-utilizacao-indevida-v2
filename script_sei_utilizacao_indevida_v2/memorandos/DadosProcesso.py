from dataclasses import dataclass
from typing import Optional, Sequence, Union


@dataclass
class DadosProcesso:
    nome_titular: str
    matricula_titular: str
    periodo_titular: str
    matriculas_dependentes: Union[str, Sequence[str]]
    periodo_dependentes: Optional[str] = None
