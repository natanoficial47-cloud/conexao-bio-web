"""
Missões do Estresse em Foco.

Para editar ou acrescentar missões, basta mexer neste arquivo (o site lê daqui).
Cada missão tem:
  - id          texto curto e único (não mude depois que alunos já responderam)
  - title       título mostrado no cartão
  - dimension   "comunicacao", "conflitos" ou "cooperacao"
  - scenario    a situação
  - options     3 opções (key "A", "B" e "C"), cada uma com:
        text      o que o aluno escolhe
        level     "good" (10 pts), "ok" (5 pts) ou "poor" (0 pts)
        title     título do feedback
        feedback  explicação mostrada depois da escolha
"""

POINTS = {"good": 10, "ok": 5, "poor": 0}

MISSIONS = [
    {
        "id": "boato-no-grupo",
        "title": "O boato no grupo da turma",
        "dimension": "comunicacao",
        "scenario": (
            "Um colega espalhou no grupo da turma que você colou em uma prova. Não é verdade, "
            "e agora várias pessoas estão comentando. O que você faz?"
        ),
        "options": [
            {
                "key": "A",
                "text": "Confronto o colega no corredor, na frente de todo mundo.",
                "level": "poor",
                "title": "Confronto público",
                "feedback": (
                    "Confrontar alguém em público, sem checar os fatos, costuma escalar o conflito: "
                    "a pessoa se defende, a plateia se envolve e a tensão na turma aumenta."
                ),
            },
            {
                "key": "B",
                "text": "Respiro, confirmo o que realmente foi dito e converso com ele com calma.",
                "level": "good",
                "title": "Verificação e diálogo",
                "feedback": (
                    "Excelente escolha! Verificar os fatos e conversar com respeito, longe da plateia, "
                    "dá chance de resolver sem piorar a situação. Se o boato continuar, vale também "
                    "contar para um professor."
                ),
            },
            {
                "key": "C",
                "text": "Espalho um boato sobre ele para ficarmos quites.",
                "level": "poor",
                "title": "Retaliação",
                "feedback": (
                    "Revidar com outro boato alimenta o ciclo de fofocas e machuca mais gente. "
                    "No fim, o problema original continua sem solução."
                ),
            },
        ],
    },
    {
        "id": "feedback-relatorio",
        "title": "A crítica ao seu trabalho",
        "dimension": "comunicacao",
        "scenario": (
            "Seu colega de dupla leu o seu trabalho e disse: \"Tá confuso, ninguém "
            "entende essa parte.\" Você se esforçou muito e ficou chateado(a). O que faz?"
        ),
        "options": [
            {
                "key": "A",
                "text": "Agradeço, pergunto qual parte ficou confusa e peço sugestões para melhorar.",
                "level": "good",
                "title": "Transformar crítica em melhoria",
                "feedback": (
                    "Muito bom! Receber um feedback sem se defender, e pedir exemplos, "
                    "mostra maturidade e deixa o trabalho da dupla melhor."
                ),
            },
            {
                "key": "B",
                "text": "Fico quieto(a), mas depois reescrevo sozinho(a), sem falar nada.",
                "level": "ok",
                "title": "Resolveu, mas sem conversar",
                "feedback": (
                    "Melhorar o texto foi positivo, mas guardar a chateação e não conversar faz a dupla "
                    "perder a chance de se entender. Da próxima vez, tente perguntar o que ficou confuso."
                ),
            },
            {
                "key": "C",
                "text": "Digo que ele não tem moral para criticar e deixo o relatório como está.",
                "level": "poor",
                "title": "Reação defensiva",
                "feedback": (
                    "Responder na defensiva fecha a conversa e o problema do texto continua. "
                    "Criticar o colega não melhora o relatório."
                ),
            },
        ],
    },
    {
        "id": "microscopio",
        "title": "Só sobrou um recurso",
        "dimension": "conflitos",
        "scenario": (
            "Na sala só restou um recurso livre (o equipamento, o projetor, o caderno de apoio "
            "da biblioteca, o que for na sua sala), e você e outro colega chegaram "
            "juntos. Os dois precisam dele agora."
        ),
        "options": [
            {
                "key": "A",
                "text": "Pego primeiro e digo que cheguei antes.",
                "level": "poor",
                "title": "Resolver pela força",
                "feedback": (
                    "Pegar sem combinar gera discussão e deixa o outro colega com a sensação de injustiça. "
                    "Pode virar um conflito maior do que o problema."
                ),
            },
            {
                "key": "B",
                "text": "Deixo ele usar primeiro, mesmo precisando, e fico irritado(a) o resto da aula.",
                "level": "ok",
                "title": "Cedeu, mas ficou ressentido",
                "feedback": (
                    "Ceder pode ser uma boa atitude, mas se você fica com raiva por dentro, o problema não "
                    "foi resolvido de verdade. Combinar um revezamento atenderia os dois."
                ),
            },
            {
                "key": "C",
                "text": "Proponho dividirmos o tempo ou revezarmos e, se não chegarmos a um acordo, peço ajuda à professora.",
                "level": "good",
                "title": "Negociação",
                "feedback": (
                    "Ótima escolha! Propor uma solução justa para os dois e pedir ajuda quando não dá para "
                    "resolver sozinho é uma forma madura de lidar com conflitos."
                ),
            },
        ],
    },
    {
        "id": "grupo-desigual",
        "title": "Um colega não fez a parte dele",
        "dimension": "cooperacao",
        "scenario": (
            "No projeto em grupo, um colega não entregou a parte dele e a apresentação é amanhã. "
            "O grupo está irritado e alguém sugere reclamar dele no grupo da turma."
        ),
        "options": [
            {
                "key": "A",
                "text": "Faço a parte dele em silêncio para não atrasar ninguém.",
                "level": "ok",
                "title": "Resolveu o prazo, mas não o problema",
                "feedback": (
                    "Você garantiu a entrega, mas assumiu um trabalho que não era seu e o colega não "
                    "aprendeu nada. Conversar com ele também é importante."
                ),
            },
            {
                "key": "B",
                "text": "Exponho no grupo do WhatsApp que ele não fez nada.",
                "level": "poor",
                "title": "Expor o colega",
                "feedback": (
                    "Expor alguém publicamente humilha e costuma piorar a relação, sem garantir que o "
                    "trabalho fique pronto. Falar com a pessoa antes ajuda mais."
                ),
            },
            {
                "key": "C",
                "text": "Converso com ele em particular, entendo o que aconteceu e combinamos como ele compensa. Se precisar, aviso a professora.",
                "level": "good",
                "title": "Conversa e combinado",
                "feedback": (
                    "Excelente! Entender o motivo e combinar uma solução, com ajuda do professor se for "
                    "preciso, fortalece o grupo e resolve o problema."
                ),
            },
        ],
    },
    {
        "id": "colega-novo",
        "title": "O colega novo está sozinho",
        "dimension": "cooperacao",
        "scenario": (
            "Um aluno novo está sozinho no intervalo há três dias. Seu grupo de amigos já está "
            "formado e ninguém convidou ele ainda."
        ),
        "options": [
            {
                "key": "A",
                "text": "Convido ele para sentar com a gente e puxo conversa sobre algo que ele goste.",
                "level": "good",
                "title": "Acolhimento",
                "feedback": (
                    "Muito bom! Um convite simples faz muita diferença para quem chegou agora, "
                    "e ajuda toda a turma a se sentir parte do grupo."
                ),
            },
            {
                "key": "B",
                "text": "Sorrio quando cruzo com ele, mas não chego a conversar.",
                "level": "ok",
                "title": "Um primeiro passo",
                "feedback": (
                    "Um sorriso é gentil, mas pode não bastar para quem está sozinho. "
                    "Que tal dar o próximo passo e puxar uma conversa?"
                ),
            },
            {
                "key": "C",
                "text": "Ignoro: cada um que cuide de si.",
                "level": "poor",
                "title": "Indiferença",
                "feedback": (
                    "Ficar de fora pode parecer neutro, mas para quem está sozinho a indiferença pesa. "
                    "Pequenas atitudes de inclusão fortalecem toda a turma."
                ),
            },
        ],
    },
    {
        "id": "meme-colega",
        "title": "O meme com a foto de um colega",
        "dimension": "conflitos",
        "scenario": (
            "Circula na turma um meme feito com a foto de um colega, tirada sem ele saber. "
            "Todo mundo está rindo e te mandam o meme também."
        ),
        "options": [
            {
                "key": "A",
                "text": "Compartilho: é só uma brincadeira.",
                "level": "poor",
                "title": "Compartilhar a exposição",
                "feedback": (
                    "Mesmo parecendo brincadeira, expor alguém sem permissão pode machucar muito e, "
                    "dependendo do caso, trazer consequências sérias. Quem compartilha também participa."
                ),
            },
            {
                "key": "B",
                "text": "Não compartilho, falo com o colega para saber como ele está e, se o meme continuar circulando, aviso um professor ou a coordenação.",
                "level": "good",
                "title": "Cuidar e pedir ajuda",
                "feedback": (
                    "Ótima atitude! Não repassar, apoiar o colega e envolver um adulto quando a situação "
                    "continua é a forma mais segura de interromper esse tipo de exposição."
                ),
            },
            {
                "key": "C",
                "text": "Não compartilho, mas também não faço nada.",
                "level": "ok",
                "title": "Não repassar já ajuda",
                "feedback": (
                    "Não repassar é importante e já reduz o estrago. Mas o colega pode estar sofrendo: "
                    "um gesto de apoio ou avisar um adulto faria muita diferença."
                ),
            },
        ],
    },
    {
        "id": "seminario-discordancia",
        "title": "Você discorda do grupo",
        "dimension": "comunicacao",
        "scenario": (
            "Seu grupo decidiu o tema e a abordagem do seminário, mas você acha que existe uma "
            "forma melhor de apresentar. Você quer dar sua opinião."
        ),
        "options": [
            {
                "key": "A",
                "text": "Fico calado(a) e aceito a decisão, mesmo discordando.",
                "level": "ok",
                "title": "Evitou o conflito, mas perdeu a chance de contribuir",
                "feedback": (
                    "Evitar discussão é compreensível, mas sua ideia pode melhorar o trabalho. "
                    "Dizer o que pensa, com respeito, também faz parte de trabalhar em grupo."
                ),
            },
            {
                "key": "B",
                "text": "Imponho minha ideia e digo que o resto do grupo está errado.",
                "level": "poor",
                "title": "Imposição",
                "feedback": (
                    "Impor a ideia e desqualificar os outros afasta o grupo e dificulta que sua proposta "
                    "seja aceita. Quem se sente desrespeitado deixa de ouvir."
                ),
            },
            {
                "key": "C",
                "text": "Explico minha ideia com calma, ouço os argumentos do grupo e buscamos juntos o que funciona melhor.",
                "level": "good",
                "title": "Diálogo e construção coletiva",
                "feedback": (
                    "Excelente! Expor sua opinião com respeito e ouvir os outros deixa o trabalho melhor "
                    "e fortalece a confiança do grupo."
                ),
            },
        ],
    },
    {
        "id": "discussao-amigo",
        "title": "Briga com um amigo",
        "dimension": "conflitos",
        "scenario": (
            "Você discutiu feio com um amigo e está com muita raiva. Ele te manda mensagem "
            "pedindo para conversar."
        ),
        "options": [
            {
                "key": "A",
                "text": "Aviso que ainda estou com raiva, respiro e combino de conversar quando estiver mais calmo(a).",
                "level": "good",
                "title": "Autorregulação",
                "feedback": (
                    "Muito bem! Reconhecer a raiva e esperar acalmar evita falar coisas das quais você "
                    "pode se arrepender, e mostra que a amizade importa."
                ),
            },
            {
                "key": "B",
                "text": "Respondo na hora, despejando tudo o que estou sentindo.",
                "level": "poor",
                "title": "Reagir no calor da raiva",
                "feedback": (
                    "Responder com muita raiva costuma gerar mais brigas e frases que depois não dá para "
                    "desfazer. Respirar e esperar um pouco ajuda a conversar de verdade."
                ),
            },
            {
                "key": "C",
                "text": "Deixo no vácuo e fico dias sem falar com ele.",
                "level": "ok",
                "title": "Silêncio prolongado",
                "feedback": (
                    "Dar um tempo para esfriar a cabeça é válido, mas sumir por dias sem avisar deixa "
                    "o conflito mal resolvido. Combinar um momento para conversar é melhor."
                ),
            },
        ],
    },
]
