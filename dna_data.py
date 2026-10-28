"""
Meu DNA da Personalidade — conteúdo do teste (PDF "Big Five" da escola).
(Arquivo reconstruído a partir da versão compilada em __pycache__; mesmo conteúdo e mesma lógica.)

30 afirmações, 6 por dimensão; cada resposta vale de 1 a 5, então cada dimensão soma de 6 a 30.
A afirmação i pertence à dimensão (i mod 5): as dimensões se intercalam como no PDF.
"""

N_QUESTIONS = 30
N_DIMENSIONS = 5

# Faixas: pontuação <= LOW_MAX é "low"; >= HIGH_MIN é "high"; no meio é "mid".
LOW_MAX = 14
HIGH_MIN = 22

SCALE = [{'value': 1, 'label': 'Discordo totalmente'},
 {'value': 2, 'label': 'Discordo'},
 {'value': 3, 'label': 'Nem concordo nem discordo'},
 {'value': 4, 'label': 'Concordo'},
 {'value': 5, 'label': 'Concordo totalmente'}]

DIMENSIONS = [{'key': 'abertura',
  'name': 'Abertura a experiências',
  'subtitle': 'Curiosidade, imaginação e interesse por novas ideias.',
  'concept': 'Representa o grau de curiosidade, criatividade, imaginação e disposição para '
             'conhecer novas ideias, experiências e perspectivas.',
  'high': 'Pessoas com maior abertura tendem a apresentar curiosidade intelectual, interesse por '
          'novidades, criatividade, imaginação e disposição para explorar diferentes '
          'possibilidades.',
  'low': 'Pessoas com menor abertura tendem a preferir experiências familiares, rotinas '
         'conhecidas, métodos tradicionais e situações mais previsíveis.',
  'strengths': 'Criatividade, inovação, flexibilidade de pensamento e aprendizagem.',
  'develop': 'Equilibrar a exploração de novidades com a capacidade de manter o foco, avaliar '
             'possibilidades e concluir projetos.'},
 {'key': 'conscienciosidade',
  'name': 'Conscienciosidade',
  'subtitle': 'Planejamento, responsabilidade e persistência.',
  'concept': 'Refere-se ao grau de organização, disciplina, responsabilidade, persistência e '
             'capacidade de direcionar comportamentos para alcançar objetivos.',
  'high': 'Pessoas com maior conscienciosidade tendem a ser organizadas, comprometidas, '
          'disciplinadas, cuidadosas e orientadas ao cumprimento de responsabilidades.',
  'low': 'Pessoas com menor conscienciosidade tendem a apresentar maior espontaneidade, '
         'flexibilidade com planejamentos e menor preferência por estruturas rígidas, podendo '
         'encontrar dificuldades na organização e manutenção de tarefas.',
  'strengths': 'Responsabilidade, planejamento, persistência e comprometimento.',
  'develop': 'Organização, gestão do tempo, estabelecimento de prioridades e equilíbrio entre '
             'produtividade e descanso.'},
 {'key': 'extroversao',
  'name': 'Extroversão',
  'subtitle': 'Sociabilidade, expressividade e energia nas interações.',
  'concept': 'Representa a tendência de buscar interações sociais, expressar-se, demonstrar '
             'assertividade e experimentar emoções positivas.',
  'high': 'Pessoas com maior extroversão tendem a ser comunicativas, sociáveis, expressivas, '
          'participativas e a buscar ambientes com maior estimulação social.',
  'low': 'Pessoas com menor extroversão, frequentemente chamadas de introvertidas, tendem a '
         'preferir ambientes tranquilos, interações em grupos menores, momentos de introspecção e '
         'atividades individuais.',
  'strengths': 'Comunicação, interação social, iniciativa e participação em atividades coletivas.',
  'develop': 'Escuta ativa, comunicação assertiva, respeito aos diferentes estilos de interação e '
             'equilíbrio entre socialização e momentos individuais.'},
 {'key': 'amabilidade',
  'name': 'Amabilidade',
  'subtitle': 'Consideração pelos outros, confiança e disposição para cooperar.',
  'concept': 'Refere-se à maneira como a pessoa se relaciona com os outros, especialmente em '
             'aspectos como empatia, cooperação, confiança, respeito e consideração pelas '
             'necessidades alheias.',
  'high': 'Pessoas com maior amabilidade tendem a ser cooperativas, acolhedoras, compreensivas, '
          'gentis e interessadas em manter relacionamentos harmoniosos.',
  'low': 'Pessoas com menor amabilidade tendem a apresentar maior competitividade, ceticismo, '
         'postura crítica e disposição para confrontar opiniões, podendo demonstrar menor '
         'preocupação em preservar a harmonia interpessoal.',
  'strengths': 'Empatia, cooperação, construção de vínculos e resolução colaborativa de conflitos.',
  'develop': 'Comunicação respeitosa, estabelecimento de limites, assertividade, empatia e '
             'capacidade de lidar com divergências.'},
 {'key': 'sensibilidade',
  'name': 'Sensibilidade emocional',
  'subtitle': 'Frequência de preocupações e intensidade de reações emocionais.',
  'concept': 'Representa a tendência de experimentar emoções desagradáveis, como ansiedade, '
             'preocupação, irritabilidade, insegurança e tristeza, especialmente diante de '
             'situações estressantes.',
  'high': 'Pessoas com maior neuroticismo tendem a apresentar maior reatividade emocional, '
          'preocupação, sensibilidade ao estresse e dificuldade para recuperar o equilíbrio '
          'emocional após acontecimentos desagradáveis.',
  'low': 'Pessoas com menor neuroticismo tendem a apresentar maior estabilidade emocional, '
         'tranquilidade diante de situações difíceis e menor frequência ou intensidade de emoções '
         'negativas.',
  'strengths': 'O reconhecimento das próprias emoções pode favorecer o autoconhecimento, enquanto '
               'a estabilidade emocional pode contribuir para o enfrentamento de situações '
               'desafiadoras.',
  'develop': 'Identificação das emoções, tolerância à frustração, estratégias de regulação '
             'emocional, manejo do estresse e enfrentamento de dificuldades.'}]

QUESTIONS = ['Gosto de aprender assuntos diferentes dos que já conheço.',
 'Costumo organizar minhas tarefas antes de começar.',
 'Sinto-me à vontade para conversar com vários colegas.',
 'Procuro compreender o ponto de vista de outras pessoas.',
 'Fico preocupado quando algo não acontece como eu esperava.',
 'Gosto de imaginar soluções diferentes para um problema.',
 'Costumo cumprir os combinados que assumo.',
 'Gosto de participar de conversas e atividades em grupo.',
 'Procuro ajudar colegas quando percebo que precisam.',
 'Fico nervoso quando recebo críticas.',
 'Tenho curiosidade sobre ideias diferentes das minhas.',
 'Consigo manter o foco em tarefas importantes mesmo quando são difíceis.',
 'Tenho facilidade para iniciar conversas com pessoas novas.',
 'Tento resolver desentendimentos sem ofender ninguém.',
 'Pequenos problemas podem me deixar muito preocupado.',
 'Gosto de experimentar novas maneiras de realizar atividades.',
 'Procuro terminar o que começo.',
 'Gosto de expressar minhas opiniões durante atividades coletivas.',
 'Levo em consideração os sentimentos dos outros antes de agir.',
 'Quando fico chateado, demoro para me sentir tranquilo novamente.',
 'Gosto de conhecer opiniões diferentes, mesmo quando discordo delas.',
 'Costumo pensar nas consequências antes de tomar decisões.',
 'Sinto-me animado quando tenho oportunidades de conhecer novas pessoas.',
 'Consigo colaborar com pessoas que pensam diferente de mim.',
 'Fico tenso quando preciso enfrentar situações inesperadas.',
 'Tenho interesse em atividades que estimulem minha criatividade.',
 'Procuro me preparar com antecedência para compromissos importantes.',
 'Gosto de atividades que envolvem bastante interação social.',
 'Procuro tratar as pessoas com respeito, mesmo durante discordâncias.',
 'Costumo pensar bastante sobre situações que me incomodaram.']


def level_of(score):
    if score <= LOW_MAX:
        return "low"
    if score >= HIGH_MIN:
        return "high"
    return "mid"


def compute(answers):
    """Soma as respostas de cada dimensão (6 a 30) e devolve os dados para a tela de resultado."""
    result = []
    for i, d in enumerate(DIMENSIONS):
        score = sum(answers[i::N_DIMENSIONS])
        result.append({
            "key": d["key"],
            "name": d["name"],
            "subtitle": d["subtitle"],
            "score": score,
            "min": 6,
            "max": 30,
            "level": level_of(score),
            "concept": d["concept"],
            "high": d["high"],
            "low": d["low"],
            "strengths": d["strengths"],
            "develop": d["develop"],
        })
    return result
