from sei_automacao.classes.Memorando import Memorando


def _par_1():
    return 'No âmbito do fluxo de apuração dos valores referentes à utilização indevida da assistência à saúde, formalizado pelos Memorandos IPSEMG/APIS-UTILIZAÇÃO nº 467/2026 e nº 468/2026, encaminha-se o presente processo à Diretoria de Saúde - DISA para levantamento das informações relativas aos atendimentos realizados na rede própria do Instituto que não integram as bases de faturamento disponíveis à Gerência de Auditoria e Contas da Saúde - GEACS.'


def _par_2():
    return 'Nos termos do fluxo estabelecido, compete à GEACS realizar o levantamento dos valores referentes à rede contratada e à coparticipação, encaminhar à DISA a demanda relativa aos atendimentos da rede própria cujas informações estejam sob sua gestão e, após o respectivo retorno, consolidar os dados para composição do demonstrativo final a ser encaminhado à Assessoria de Políticas e Informações em Saúde - APIS. A atuação da DISA no levantamento das informações da rede própria decorre de suas competências relativas à coordenação da prestação de assistência à saúde por meio dos serviços próprios, nos termos do art. 68 do Decreto Estadual nº 48.823, de 16 de maio de 2024.'


def _par_3():
    return 'Conforme operacionalização posteriormente definida entre as áreas e formalizada no Memorando IPSEMG/DISA nº 579/2026 e no Memorando IPSEMG/GEACS nº 118/2026, os processos serão encaminhados à unidade IPSEMG/DISA-UTI-INDEV, responsável pela articulação interna necessária à obtenção das informações junto às unidades detentoras dos respectivos dados.'


def _par_4():
    return 'Para fins desta apuração, a GEACS já dispõe das informações da rede própria que integram as bases de faturamento sob sua gestão. Assim, solicita-se à DISA, especificamente, o levantamento dos atendimentos de internação e de pronto atendimento realizados na rede própria, cujos dados necessários à apuração não se encontram disponíveis nas bases utilizadas por esta Gerência.'


def _par_5():
    return 'A consulta deverá considerar o titular e os dependentes indicados no processo, exclusivamente nos respectivos períodos de manutenção indevida do direito assistencial informados pela APIS, conforme dados abaixo:'


def _par_6():
    return (
        'Nome do titular: R.A.S.R'
        'Matrícula: 3147797-6'
        'Período de apuração do titular: 02/2024 a 06/2024'
        'Matrículas dos dependentes: 3147799; 3479648'
        'Período de apuração dos dependentes: '
        '[informar, quando houver período específico distinto]'
    )


def _par_7():
    return 'Para cada beneficiário, solicita-se verificar inicialmente a existência de internação e/ou atendimento de pronto atendimento no período indicado.'


def _par_8():
    return 'Não sendo identificado atendimento dessa natureza, solicita-se que essa informação seja registrada no processo para prosseguimento da apuração pela GEACS.'


def _par_9():
    return 'Caso sejam identificados atendimentos, solicita-se o levantamento e a apuração das respectivas contas, contemplando, no mínimo, a identificação do beneficiário, data do atendimento, natureza do atendimento, procedimentos realizados e respectivos valores, observadas as regras de faturamento aplicáveis e a tabela da rede própria vigente à época da realização.'


def _par_10():
    return 'Para subsidiar a padronização do retorno, poderão ser observados, no que couber, os campos dos modelos de relatório encaminhados por meio do Memorando IPSEMG/GEACS nº 96/2026. O retorno deverá conter os elementos necessários à posterior consolidação, pela GEACS, das informações da rede própria com aquelas referentes à rede contratada e à coparticipação, para composição do demonstrativo final por beneficiário.'


def _par_11():
    return 'O tratamento e o compartilhamento das informações deverão observar os princípios e as disposições da Lei nº 13.709, de 14 de agosto de 2018 - Lei Geral de Proteção de Dados Pessoais - LGPD, especialmente quanto à finalidade, à necessidade e à segurança dos dados.'


def _par_12():
    return 'Após o levantamento, solicita-se o retorno do processo à IPSEMG/GEACS-Utilização, para continuidade da apuração.'


def _par_nome_signatario(nome):
    return f'<p class="Nome_Signatario">"{nome}"</p>'


def _par_cargo_signatario(cargo):
    return f'<p class="Cargo_Signatario">"{cargo}"</p>'


MemoDisa: Memorando = Memorando(
    destinatario_nome='IPSEMG/DISA-UTI-INDEV',
    assunto='Levantamento de atendimentos da rede própria - utilização indevida da assistência à saúde',
    vocativo='Prezados',
    nome_signatario='Bruna Miiller Lavarini',
    cargo_signatario='Gerência de Auditoria e Contas da Saúde',
    nivel_acesso='Restrito',
    hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
    paragrafos=[
        _par_1(),
        _par_2(),
        _par_3(),
        _par_4(),
        _par_5(),
        _par_6(),
        _par_7(),
        _par_8(),
        _par_9(),
        _par_10(),
        _par_11(),
        _par_12(),
    ],
)
