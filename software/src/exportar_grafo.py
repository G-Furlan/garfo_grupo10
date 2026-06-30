# -*- coding: utf-8 -*-
"""
Orquestra o pipeline (parser -> parte 1 -> parte 2) e exporta o grafo ponderado
em JSON no formato que o Cytoscape consome.

Uso:
    python src/exportar_grafo.py [caminho_do_pdf]
Se o caminho não for passado, usa o PDF mais recente do diretório de datasets.
Imprime na stdout: {"elements": {"nodes":[...], "edges":[...]}, "meta": {...}}
ou {"error": "..."} em caso de falha.
"""
import os, sys, json, glob
from datetime import datetime

# Torna o script independente do diretório de onde é chamado (ex.: pelo Node).
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../software
os.chdir(RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'src'))

from parser_historico import extrair_dados_completos_sigaa          # noqa: E402
from grafo_pendentes import carregar_grade, construir_grafo_dependencias, eh_obrigatoria  # noqa: E402
from grafo_pesos import atribuir_pesos, esta_disponivel                  # noqa: E402
from recomendar_semestre import recomendar_semestre                 # noqa: E402

MAX_MATERIAS_TETO = 8     # teto de matérias por semestre (evita orçamento irreal)
MATERIAS_FALLBACK = 4     # usado quando o aluno não tem histórico fechado (média < 1)
CH_REFERENCIA = 64        # carga horária de referência por matéria


def orcamento_por_media(media):
    """
    Orçamento de carga horária do semestre a partir da média de matérias aprovadas
    por semestre (vinda do parser). Ex.: média 4.3 -> 4 matérias -> 256h.
    Calouro/sem histórico fechado (média < 1) cai no fallback.
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

    # O GRAFO contém apenas as obrigatórias pendentes (espinha dorsal).
    grafo = construir_grafo_dependencias(pendentes_obrig, grade, curso=curso)
    periodo_atual = calcular_periodo_atual_aluno(periodo_ingresso, suspensoes)
    grafo = atribuir_pesos(grafo, resolvidas, df_historico, periodo_atual)

    # Orçamento do semestre: personalizado pela média de aprovações do aluno
    if max_horas is None:
        max_horas = orcamento_por_media(media)

    # Recomendação por semestre (só obrigatórias). O que sobrar do orçamento
    # vira "vagas de optativa" (slots), não disciplinas optativas específicas.
    def recomendar(sem):
        r = recomendar_semestre(grafo, max_horas, semestre_alvo=sem)
        horas_livres = max(0, max_horas - r['total_horas'])
        return {
            "codigos": r['recomendadas'],
            "horas": r['total_horas'],
            "w": r['total_w'],
            "horas_livres": horas_livres,
            "slots_optativa": horas_livres // CH_REFERENCIA,  # vagas de ~64h para optativa
        }

    # Lista de optativas (catálogo ainda não cursado): sigla, nome, período, CH, oferta
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