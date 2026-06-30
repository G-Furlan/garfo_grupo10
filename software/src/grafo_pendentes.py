"""
PARTE 1 do pipeline de recomendação de matrícula.

Gera o grafo de dependências das disciplinas OBRIGATÓRIAS que ainda faltam
para o aluno concluir o curso (lidas do histórico pelo parser).

Representação canônica: dicionário puro (sem NetworkX), na forma

    {
        'curso': 'CCO',
        'nos': {
            'COD': {
                'nome': str,
                'tipo': 'Obrigatoria',
                'ch': int,
                'periodo_ideal': int,
                'periodo_ofertado': str,
                'pre_requisitos': [[...], ...]   # grupos: OR entre grupos, AND dentro
            },
            ...
        },
        'arestas': {
            'COD': ['COD_QUE_DEPENDE_DELE', ...]  # COD -> dep  (dep depende de COD)
        },
        'fantasmas': ['CODIGO_INEXISTENTE', ...]   # pendentes que não estão na grade
    }

Este grafo é o produto da PARTE 1. A PARTE 2 vai decorá-lo com pesos (P1-P5) e
"""

import json


# -------------------------------------------------------------
# CARREGAMENTO E NORMALIZAÇÃO
# -------------------------------------------------------------

def carregar_grade(curso):
    """Carrega o JSON da grade curricular do curso."""
    caminho = f"src/data/materias{curso.upper()}.json"
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)


def eh_obrigatoria(dados):
    """True se a disciplina é obrigatória (tolerante a acento/variação)."""
    tipo_raw = dados.get('tipo', '')
    return 'brigatóri' in tipo_raw or 'brigatoria' in tipo_raw


def normalizar_pre_requisitos(pre_req_raw):
    """
    Garante o formato lista-de-listas (OR de grupos AND).
    Obrigatórias já vêm como [['A', 'B'], ['C']]; flat ['A', 'B'] vira [['A'], ['B']].
    """
    if not pre_req_raw:
        return []
    if isinstance(pre_req_raw[0], list):
        return pre_req_raw
    return [[req] for req in pre_req_raw]


def _montar_no(codigo, grade):
    """Extrai e tipa os atributos de uma disciplina a partir do JSON da grade."""
    dados = grade.get(codigo, {})

    ch_raw = dados.get('carga_horaria', '64h')
    try:
        ch = int(str(ch_raw).replace('h', '').strip())
    except (ValueError, AttributeError):
        ch = 64

    try:
        periodo_ideal = int(dados.get('periodo', 0))
    except (ValueError, TypeError):
        periodo_ideal = 0

    return {
        'nome': dados.get('disciplina', codigo),
        'tipo': 'Obrigatoria' if eh_obrigatoria(dados) else 'Optativa',
        'ch': ch,
        'periodo_ideal': periodo_ideal,
        'periodo_ofertado': dados.get('periodo_ofertado', ''),
        'horario': dados.get('horario', {}),  # {'2026-1': '2T34 4T12', ...} por semestre
        'pre_requisitos': normalizar_pre_requisitos(dados.get('pre_requisitos', [])),
    }


# -------------------------------------------------------------
# CONSTRUÇÃO DO GRAFO (PARTE 1)
# -------------------------------------------------------------

def construir_grafo_dependencias(pendentes, grade, curso=None):
    """
    Constrói o grafo de dependências entre as disciplinas obrigatórias pendentes.

    Só entram no grafo disciplinas que estão em `pendentes`, existem na grade e
    são obrigatórias. Uma aresta v -> u é criada quando v é pré-requisito de u
    (em qualquer grupo) e ambos são pendentes. Disciplinas já concluídas não
    viram nó nem aresta — o grafo representa apenas o que ainda falta.

    Parâmetros:
        pendentes : list[str]  — códigos das obrigatórias pendentes (do parser)
        grade     : dict       — grade completa carregada do JSON
        curso     : str | None — metadado opcional

    Retorno:
        dict  com chaves 'curso', 'nos', 'arestas', 'fantasmas'
    """
    pendentes_unicos = list(dict.fromkeys(pendentes))  # remove duplicatas, preserva ordem

    # Conjunto de nós: pendentes que existem na grade (obrigatória OU optativa).
    # O escopo (incluir ou não optativas) é decidido por quem monta a lista `pendentes`.
    nos_validos = {
        cod for cod in pendentes_unicos
        if cod in grade
    }

    # Pendentes que o parser trouxe mas não existem na grade (ruído de regex, grade antiga)
    fantasmas = [cod for cod in pendentes_unicos if cod not in grade]

    grafo = {
        'curso': curso,
        'nos': {},
        'arestas': {cod: [] for cod in nos_validos},
        'fantasmas': fantasmas,
    }

    for codigo in nos_validos:
        grafo['nos'][codigo] = _montar_no(codigo, grade)

    # Arestas: para cada obrigatória pendente, ligar cada pré-requisito que também
    # seja pendente. (pré-req já concluído não gera aresta — não é mais dependência.)
    for codigo in nos_validos:
        reqs_vistos = set()  # evita aresta duplicada quando o mesmo req aparece em vários grupos
        for grupo in grafo['nos'][codigo]['pre_requisitos']:
            for req in grupo:
                if req in nos_validos and req not in reqs_vistos:
                    grafo['arestas'][req].append(codigo)
                    reqs_vistos.add(req)

    return grafo


# -------------------------------------------------------------
# MÉTRICA ESTRUTURAL: CAMINHO CRÍTICO (insumo do P1 na parte 2)
# -------------------------------------------------------------

def calcular_caminhos_criticos(grafo):
    """
    Para cada nó, comprimento do maior caminho de dependências a partir dele.
    Ex.: A -> B -> C  =>  {A:2, B:1, C:0}.

    DFS com memoização e detecção de ciclo (a grade deveria ser um DAG, mas
    dados inconsistentes não devem travar o programa em recursão infinita).
    """
    arestas = grafo['arestas']
    cache = {}
    em_visita = set()

    def dfs(codigo):
        if codigo in cache:
            return cache[codigo]
        if codigo in em_visita:
            # ciclo detectado: corta para não recorrer infinitamente
            return 0
        em_visita.add(codigo)

        dependentes = arestas.get(codigo, [])
        maior = 0
        for dep in dependentes:
            maior = max(maior, 1 + dfs(dep))

        em_visita.discard(codigo)
        cache[codigo] = maior
        return maior

    for codigo in grafo['nos']:
        dfs(codigo)

    return cache


# -------------------------------------------------------------
# IMPRESSÃO (diagnóstico)
# -------------------------------------------------------------

def imprimir_grafo(grafo):
    """Imprime o grafo de pendentes de forma legível."""
    nos = grafo['nos']
    arestas = grafo['arestas']
    caminhos = calcular_caminhos_criticos(grafo)

    print(f"\n{'='*72}")
    print(f"GRAFO DE PENDENTES — {len(nos)} disciplinas obrigatórias")
    print(f"{'='*72}")
    print(f"{'CÓDIGO':<14} | {'CH':<4} | {'PER':<4} | {'CRÍT':<5} | NOME")
    print("-" * 72)

    # Ordena por caminho crítico (mais estruturante primeiro), depois período
    ordenados = sorted(
        nos.items(),
        key=lambda x: (-caminhos.get(x[0], 0), x[1]['periodo_ideal'])
    )
    for codigo, dados in ordenados:
        print(
            f"{codigo:<14} | {dados['ch']:<4} | {dados['periodo_ideal']:<4} | "
            f"{caminhos.get(codigo, 0):<5} | {dados['nome']}"
        )

    print("-" * 72)
    print(f"\nDEPENDÊNCIAS (v → u significa: u depende de v)")
    print("-" * 72)
    tem_aresta = False
    for origem, destinos in sorted(arestas.items()):
        for destino in destinos:
            tem_aresta = True
            nome_destino = nos.get(destino, {}).get('nome', destino)
            print(f"  {origem:<12} → {destino:<12} ({nome_destino})")
    if not tem_aresta:
        print("  (nenhuma dependência entre as pendentes — todas estão liberadas)")

    if grafo.get('fantasmas'):
        print("-" * 72)
        print(f"\n⚠ PENDENTES SEM CORRESPONDÊNCIA NA GRADE ({len(grafo['fantasmas'])}):")
        print(f"  {grafo['fantasmas']}")

    print("-" * 72)


# -------------------------------------------------------------
# EXECUÇÃO PRINCIPAL
# -------------------------------------------------------------

if __name__ == "__main__":
    from parser_historico import extrair_dados_completos_sigaa
    import os
    import glob

    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    diretorio_historicos = os.path.join(diretorio_atual, "data", "Dataset-Cenario1-RecomendacaoMatricula")
    arquivos_pdf = glob.glob(os.path.join(diretorio_historicos, "*.pdf"))

    if not arquivos_pdf:
        print(f"Erro: Nenhum PDF encontrado em:\n-> {diretorio_historicos}")
    else:
        caminho_historico = max(arquivos_pdf, key=os.path.getmtime)
        print(f"Processando: {os.path.basename(caminho_historico)}")

        curso, df_historico, disciplinas_resolvidas, lista_pendentes, \
            periodo_ingresso, suspensoes, media_aprovacoes = extrair_dados_completos_sigaa(caminho_historico)

        grade = carregar_grade(curso)
        grafo = construir_grafo_dependencias(lista_pendentes, grade, curso=curso)
        imprimir_grafo(grafo)