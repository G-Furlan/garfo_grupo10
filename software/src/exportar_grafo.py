# -*- coding: utf-8 -*-
"""
Monta o pipeline e exporta o grafo ponderado
em JSON no formato que o Cytoscape consome.

"""
import os, sys, json, glob, re
from datetime import datetime

# Torna o script independente do diretório de onde é chamado
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../software
os.chdir(RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'src'))

from parser_historico import extrair_dados_completos_sigaa          
from grafo_pendentes import carregar_grade, construir_grafo_dependencias, eh_obrigatoria  
from grafo_pesos import atribuir_pesos, esta_disponivel                 
from recomendar_semestre import recomendar_semestre                

MAX_MATERIAS_TETO = 8     # teto de matérias por semestre 
MATERIAS_FALLBACK = 4     # usado quando o aluno não tem histórico fechado (média < 4)
CH_REFERENCIA = 64        # carga horária de referência por matéria


def orcamento_por_media(media):
    """
    Orçamento de carga horária do semestre a partir da média de matérias aprovadas
    por semestre (vinda do parser). Ex.: média 4.3 -> 4 matérias -> 256h.
    Calouro/sem histórico fechado (média < 4) cai no fallback.
    """
    if not media or media < 4:
        n = MATERIAS_FALLBACK
    else:
        n = min(MAX_MATERIAS_TETO, round(media))
    return n * CH_REFERENCIA


def calcular_periodo_atual_aluno(periodo_ingresso, suspensoes):
    if not periodo_ingresso:
        return 1
    ano_i, sem_i = map(int, periodo_ingresso.split('.'))
    hoje = datetime.now()
    sem_atual = 1 if hoje.month <= 6 else 2
    decorridos = ((hoje.year - ano_i) * 2) + (sem_atual - sem_i) + 1
    return max(1, decorridos - len(suspensoes))


def para_cytoscape(grafo, meta):
    """Converte o grafo dict (parte 1+2) em elements do Cytoscape."""
    nodes = []
    for cod, d in grafo['nos'].items():
        nodes.append({"data": {
            "id": cod,
            "codigo": cod,
            "nome": d.get('nome', cod),
            "tipo": d.get('tipo', 'Obrigatoria'),
            "ch": d.get('ch'),
            "periodo": d.get('periodo_ideal'),
            "disponivel": bool(d.get('disponivel')),
            "periodo_ofertado": d.get('periodo_ofertado', ''),
            "horario": d.get('horario', {}),
            "W": d.get('W', 0),
            "P1": d.get('P1', 0), "P2": d.get('P2', 0), "P3": d.get('P3', 0),
            "P4": d.get('P4', 0), "P5": d.get('P5', 0),
        }})
    edges = []
    i = 0
    for origem, destinos in grafo['arestas'].items():
        for destino in destinos:
            edges.append({"data": {"id": f"e{i}", "source": origem, "target": destino}})
            i += 1
    return {"elements": {"nodes": nodes, "edges": edges}, "meta": meta}


def _ch_int(ch_raw):
    try:
        return int(str(ch_raw).replace('h', '').strip())
    except (ValueError, AttributeError):
        return 64


def _parse_horario(horario_str):
    """Fatia uma string de horário UNIFEI ('2T34 4T12') em {dia+turno+aula}."""
    slots = set()
    if not horario_str:
        return slots
    for token in str(horario_str).split():
        m = re.match(r'^(\d+)([MTN])(\d+)$', token, re.I)
        if not m:
            continue
        turno = m.group(2).upper()
        for dia in m.group(1):
            for aula in m.group(3):
                slots.add(dia + turno + aula)
    return slots


def _horario_no_semestre(node, semestre):
    return (node.get('horario') or {}).get(f'2026-{semestre}', '')


def resolver_conflitos_horario(grafo, recomendadas, em_espera, semestre, max_horas):
    """
    Reparo guloso de conflitos de horário sobre a grade vinda do knapsack.

    Percorre as disciplinas em ordem decrescente de peso e mantém as que não
    colidem com as já escolhidas; em cada par em conflito, a de MENOR peso é
    descartada. O espaço liberado é repreenchido pela próxima obrigatória
    disponível (também por peso) que caiba no orçamento e não gere novo conflito;
    o que sobrar vira vaga de optativa.

    Observação de projeto: a seleção ótima por carga horária (knapsack 0/1) NÃO é
    alterada — este é um pós-processamento. A versão exata (mochila com restrição
    de conflito, DCKP) é NP-difícil, por isso adota-se aqui o reparo guloso.

    Retorna (grade_sem_conflito, horas_usadas, descartadas).
    """
    nos = grafo['nos']
    grade, ocupados, horas, descartadas = [], set(), 0, []

    for cod in recomendadas:                       # já ordenadas por -W
        slots = _parse_horario(_horario_no_semestre(nos[cod], semestre))
        ch = _ch_int(nos[cod]['ch'])
        if not (slots & ocupados) and horas + ch <= max_horas:
            grade.append(cod); ocupados |= slots; horas += ch
        else:
            descartadas.append(cod)                # bloqueada por conflito

    for cod in em_espera:                          # reservas, já ordenadas por -W
        slots = _parse_horario(_horario_no_semestre(nos[cod], semestre))
        ch = _ch_int(nos[cod]['ch'])
        if horas + ch <= max_horas and not (slots & ocupados):
            grade.append(cod); ocupados |= slots; horas += ch

    return grade, horas, descartadas


def gerar(caminho_pdf=None, max_horas=None):
    pasta = os.path.join(RAIZ, 'src', 'data', 'Dataset-Cenario1-RecomendacaoMatricula')
    if not caminho_pdf:
        pdfs = glob.glob(os.path.join(pasta, '*.pdf'))
        if not pdfs:
            raise FileNotFoundError("Nenhum PDF de histórico encontrado.")
        caminho_pdf = max(pdfs, key=os.path.getmtime)

    curso, df_historico, resolvidas, pendentes_obrig, periodo_ingresso, suspensoes, media = \
        extrair_dados_completos_sigaa(caminho_pdf)

    grade = carregar_grade(curso)
    resolvidas_set = set(resolvidas)

    # O grafo contém apenas as obrigatórias pendentes
    grafo = construir_grafo_dependencias(pendentes_obrig, grade, curso=curso)
    periodo_atual = calcular_periodo_atual_aluno(periodo_ingresso, suspensoes)
    grafo = atribuir_pesos(grafo, resolvidas, df_historico, periodo_atual)

    # Orçamento do semestre: personalizado pela média de aprovações do aluno
    if max_horas is None:
        max_horas = orcamento_por_media(media)

    # Recomendação por semestre (só obrigatórias). O que sobrar do orçamento
    # vira "vagas de optativa", não disciplinas optativas específicas.
    def recomendar(sem):
        r = recomendar_semestre(grafo, max_horas, semestre_alvo=sem)
        # Pós-processamento: remove conflitos de horário da grade do knapsack.
        grade, horas, descartadas = resolver_conflitos_horario(
            grafo, r['recomendadas'], r['em_espera'], sem, max_horas)
        horas_livres = max(0, max_horas - horas)
        return {
            "codigos": grade,                       # grade oficial (sem conflito de horário)
            "horas": horas,
            "w": sum(grafo['nos'][c]['W'] for c in grade),
            "horas_livres": horas_livres,
            "slots_optativa": horas_livres // CH_REFERENCIA,  # vagas de ~64h para optativa
            "pick_knapsack": r['recomendadas'],     # seleção do knapsack (pode ter conflito)
            "descartadas": descartadas,             # removidas pelo reparo de conflito
        }

    # Lista de optativas: sigla, nome, período, CH, oferta
    # e se os pré-requisitos já estão satisfeitos. NÃO entram no grafo.
    lista_optativas = []
    for cod, dados in grade.items():
        if eh_obrigatoria(dados) or cod in resolvidas_set:
            continue
        lista_optativas.append({
            "codigo": cod,
            "nome": dados.get('disciplina', cod),
            "periodo": int(dados.get('periodo', 0) or 0),
            "ch": _ch_int(dados.get('carga_horaria', '64h')),
            "periodo_ofertado": dados.get('periodo_ofertado', ''),
            "horario": dados.get('horario', {}),
            "disponivel": esta_disponivel({'pre_requisitos': dados.get('pre_requisitos', [])}, resolvidas_set),
        })
    lista_optativas.sort(key=lambda o: (o['periodo'], o['codigo']))

    meta = {
        "curso": curso,
        "periodo_atual": periodo_atual,
        "periodo_ingresso": periodo_ingresso,
        "total": len(grafo['nos']),
        "disponiveis": sum(1 for d in grafo['nos'].values() if d['disponivel']),
        "max_horas": max_horas,
        "media_aprovacoes": round(media, 1) if media else 0,
        "orcamento_materias": max_horas // CH_REFERENCIA,
        "recomendacao": {"1": recomendar(1), "2": recomendar(2)},
        "lista_optativas": lista_optativas,
        "fantasmas": grafo.get('fantasmas', []),
        "arquivo": os.path.basename(caminho_pdf),
    }
    return para_cytoscape(grafo, meta)


if __name__ == "__main__":
    try:
        caminho = sys.argv[1] if len(sys.argv) > 1 else None
        print(json.dumps(gerar(caminho), ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)