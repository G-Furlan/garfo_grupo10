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
from grafo_pendentes import carregar_grade, construir_grafo_dependencias  # noqa: E402
from grafo_pesos import atribuir_pesos                              # noqa: E402
from recomendar_semestre import recomendar_semestre                 # noqa: E402

MAX_HORAS_PADRAO = 384  # limite de carga horária do semestre (6 x 64h)


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
            "ch": d.get('ch'),
            "periodo": d.get('periodo_ideal'),
            "disponivel": bool(d.get('disponivel')),
            "periodo_ofertado": d.get('periodo_ofertado', ''),
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


def gerar(caminho_pdf=None, max_horas=MAX_HORAS_PADRAO):
    pasta = os.path.join(RAIZ, 'src', 'data', 'Dataset-Cenario1-RecomendacaoMatricula')
    if not caminho_pdf:
        pdfs = glob.glob(os.path.join(pasta, '*.pdf'))
        if not pdfs:
            raise FileNotFoundError("Nenhum PDF de histórico encontrado.")
        caminho_pdf = max(pdfs, key=os.path.getmtime)

    curso, df_historico, resolvidas, pendentes, periodo_ingresso, suspensoes, media = \
        extrair_dados_completos_sigaa(caminho_pdf)

    grade = carregar_grade(curso)
    grafo = construir_grafo_dependencias(pendentes, grade, curso=curso)
    periodo_atual = calcular_periodo_atual_aluno(periodo_ingresso, suspensoes)
    grafo = atribuir_pesos(grafo, resolvidas, df_historico, periodo_atual)

    # PARTE 3 (passo 1): knapsack para CADA semestre-alvo (1=ímpar, 2=par).
    # Cada um filtra por disponibilidade E oferta no semestre. O front alterna entre eles.
    rec1 = recomendar_semestre(grafo, max_horas, semestre_alvo=1)
    rec2 = recomendar_semestre(grafo, max_horas, semestre_alvo=2)

    meta = {
        "curso": curso,
        "periodo_atual": periodo_atual,
        "periodo_ingresso": periodo_ingresso,
        "total": len(grafo['nos']),
        "disponiveis": sum(1 for d in grafo['nos'].values() if d['disponivel']),
        "max_horas": max_horas,
        "recomendacao": {
            "1": {"codigos": rec1['recomendadas'], "horas": rec1['total_horas'], "w": rec1['total_w']},
            "2": {"codigos": rec2['recomendadas'], "horas": rec2['total_horas'], "w": rec2['total_w']},
        },
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