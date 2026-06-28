import json
import networkx as nx
import pandas as pd
from datetime import datetime
from grafo_pendentes import construir_grafo_dependencias, calcular_caminhos_criticos


# -------------------------------------------------------------
# CARREGAMENTO E CONSTRUÇÃO DO GRAFO
# -------------------------------------------------------------

def carregar_grade(curso):
    """Carrega o banco de dados da estrutura curricular do curso correspondente."""
    caminho_arquivo = f"src/data/materias{curso.upper()}.json"
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo de grade não encontrado: {caminho_arquivo}")


def construir_grafo_curricular(grade):
    """
    Constrói o Grafo Direcionado Acíclico (DAG) completo da matriz curricular.
    Todos os atributos do JSON são preservados como atributos do nó.
    """
    G = nx.DiGraph()

    for codigo, dados in grade.items():
        # Normaliza o tipo removendo variações de acento
        tipo_raw = dados.get('tipo', 'Optativa')
        tipo = 'Obrigatoria' if 'brigatóri' in tipo_raw or 'brigatoria' in tipo_raw else 'Optativa'

        # Carga horária vem como "64h" — extrai só o número
        ch_raw = dados.get('carga_horaria', '64h')
        try:
            ch = int(str(ch_raw).replace('h', '').strip())
        except (ValueError, AttributeError):
            ch = 64

        # Período ideal vem como string "1", "2", etc.
        try:
            periodo_ideal = int(dados.get('periodo', 0))
        except (ValueError, TypeError):
            periodo_ideal = 0

        G.add_node(
            codigo,
            nome=dados.get('disciplina', ''),
            ch=ch,
            periodo_ideal=periodo_ideal,
            tipo=tipo,
            periodo_ofertado=dados.get('periodo_ofertado', ''),
            pre_requisitos=dados.get('pre_requisitos', [])  # lista de listas (OR de grupos AND)
        )

    # Adiciona arestas para cada disciplina dentro de cada grupo alternativo de pré-requisitos
    for codigo, dados in grade.items():
        for grupo in dados.get('pre_requisitos', []):
            for pre_req in grupo:
                if pre_req in grade:  # evita nós fantasmas de grades antigas
                    G.add_edge(pre_req, codigo)

    return G


def obter_disciplinas_disponiveis(G, disciplinas_resolvidas):
    """
    Retorna disciplinas cujos pré-requisitos estão satisfeitos.
    Lógica: OR entre grupos, AND dentro de cada grupo.
    Ex: [[A, B], [C]] significa (A e B) OU (C).
    """
    disponiveis = []
    for no in G.nodes():
        if no in disciplinas_resolvidas:
            continue

        grupos = G.nodes[no].get('pre_requisitos', [])

        if not grupos:
            disponiveis.append(no)
            continue

        satisfeito = any(
            all(req in disciplinas_resolvidas for req in grupo)
            for grupo in grupos
        )

        if satisfeito:
            disponiveis.append(no)

    return disponiveis


# -------------------------------------------------------------
# FUNÇÕES DE CÁLCULO DE PESOS (P1 a P6)
# -------------------------------------------------------------

def calcular_p1_caminho_critico(caminhos_criticos, codigo_disciplina):
    """
    P1 - Fatores Topológicos: comprimento do caminho crítico a partir desta disciplina.
    Valor calculado pelo grafo_pendentes.py via DFS e recebido como dicionário.
    Quanto maior a cadeia de dependências, maior a prioridade.
    """
    return caminhos_criticos.get(codigo_disciplina, 0)


def calcular_p2_obrigatoriedade(G, codigo_disciplina, periodo_atual_aluno):
    """
    P2 - Obrigatoriedade: peso base por tipo e urgência temporal.

    Obrigatórias que já deveriam ter sido cursadas (periodo_ideal <= periodo_atual)
    recebem peso maior do que obrigatórias que ainda estão no futuro.
    Optativas recebem peso mínimo.

    Escala:
        Obrigatória atrasada ou no prazo : +10
        Obrigatória futura               : +6
        Optativa                         : +1
    """
    if codigo_disciplina not in G:
        return 0

    tipo = G.nodes[codigo_disciplina].get('tipo', 'Optativa')
    periodo_ideal = G.nodes[codigo_disciplina].get('periodo_ideal', 0)

    if tipo == 'Obrigatoria':
        # periodo_ideal == 0 significa sem informação → trata como futura
        if periodo_ideal > 0 and periodo_ideal <= periodo_atual_aluno:
            return 10   # deveria já ter sido cursada
        else:
            return 6    # ainda está no prazo ou sem dado
    else:
        return 1


def calcular_p3_retencao_historica(codigo_disciplina, df_historico):
    """
    P3 - Retenção Histórica: bônus proporcional ao número de reprovações anteriores.
    Evita que o aluno continue adiando disciplinas em que já travou.
    """
    PESO_REPROVACAO = 2
    if not df_historico.empty and codigo_disciplina in df_historico['codigo'].values:
        linha = df_historico[df_historico['codigo'] == codigo_disciplina].iloc[0]
        return int(linha['reprovacoes']) * PESO_REPROVACAO
    return 0


def calcular_p4_sazonalidade(G, codigo_disciplina):
    """
    P4 - Sazonalidade: bônus para disciplinas com oferta semestral restrita.
    Se a janela de matrícula desta disciplina não é agora, o aluno perde ~1 ano.
    """
    PESO_SAZONALIDADE = 4

    periodo_ofertado = G.nodes[codigo_disciplina].get('periodo_ofertado', '')
    if not periodo_ofertado or periodo_ofertado in ('Não listado', '') or periodo_ofertado in ('2026-1 / 2026-2', ''):
        return 0

    # Ofertada nos dois semestres: sem restrição, sem bônus
    if '/' in periodo_ofertado:
        return 0

    hoje = datetime.now()
    sem_atual = 1 if hoje.month <= 6 else 2

    try:
        sem_ofertado = int(periodo_ofertado.split('-')[1][0])
    except (IndexError, ValueError):
        return 0

    # Bônus apenas se a disciplina NÃO está sendo ofertada no semestre atual
    # (ou seja, esta é a última chance antes de esperar 1 ano)
    return PESO_SAZONALIDADE if sem_ofertado != sem_atual else 0


def calcular_p5_atraso(G, codigo_disciplina, periodo_atual_aluno):
    """
    P5 - Atraso: penalidade crescente para pendências de períodos anteriores.
    Quanto mais antiga a pendência em relação ao período ideal, maior o peso.
    """
    PESO_ATRASO = 4
    periodo_ideal = G.nodes[codigo_disciplina].get('periodo_ideal', 0)

    if periodo_ideal > 0 and periodo_atual_aluno > periodo_ideal:
        return (periodo_atual_aluno - periodo_ideal) * PESO_ATRASO
    return 0


def calcular_p6_penalizacao(G, codigo_disciplina):
    """
    P6 - Penalização de optativas: garante que optativas nunca superem obrigatórias.
    """
    PENALIDADE_OPTATIVA = -8
    tipo = G.nodes[codigo_disciplina].get('tipo', 'Optativa')
    return PENALIDADE_OPTATIVA if tipo == 'Optativa' else 0


# -------------------------------------------------------------
# CÁLCULO DO PERÍODO ATUAL DO ALUNO
# -------------------------------------------------------------

def calcular_periodo_atual_aluno(periodo_ingresso, suspensoes):
    """
    Calcula o período real do aluno com base no tempo decorrido desde
    o ingresso, descontando semestres suspensos/trancados.
    """
    if not periodo_ingresso:
        return 1

    ano_ingresso, sem_ingresso = map(int, periodo_ingresso.split('.'))

    hoje = datetime.now()
    ano_atual = hoje.year
    sem_atual = 1 if hoje.month <= 6 else 2

    periodos_decorridos = ((ano_atual - ano_ingresso) * 2) + (sem_atual - sem_ingresso) + 1
    periodo_real = periodos_decorridos - len(suspensoes)

    return max(1, periodo_real)


# -------------------------------------------------------------
# CONSTRUÇÃO DO SUBGRAFO DE PENDENTES COM PESOS
# -------------------------------------------------------------

def construir_grafo_pendentes(G, disciplinas_disponiveis, disciplinas_resolvidas,
                               df_historico, periodo_atual_aluno, lista_pendentes, grade):
    """
    Gera um subgrafo contendo apenas as disciplinas pendentes e disponíveis,
    com os pesos P1-P6 e o peso total W calculados como atributos de cada nó.

    P1 é fornecido pelo grafo_pendentes.py (DFS sobre grafo dict puro, sem NetworkX).
    Os demais pesos são calculados localmente.

    Atributos de cada nó no grafo resultante:
        - nome, ch, tipo, periodo_ideal, periodo_ofertado  (dados curriculares)
        - P1, P2, P3, P4, P5, P6                          (componentes do peso)
        - W                                                 (peso total de prioridade)
        - disponivel                                        (True = pré-requisitos satisfeitos)
    """
    # P1: caminhos críticos calculados pelo grafo_pendentes (dict puro, sem NetworkX)
    grafo_dict = construir_grafo_dependencias(lista_pendentes, grade)
    caminhos_criticos = calcular_caminhos_criticos(grafo_dict)

    # Universo de nós: disponíveis + bloqueados (a BFS precisa enxergar a cadeia completa)
    todos_pendentes = [
        no for no in G.nodes()
        if no not in disciplinas_resolvidas
    ]

    subgrafo = G.subgraph(todos_pendentes).copy()

    # Calcula e atribui os pesos em cada nó
    for no in subgrafo.nodes():
        p1 = calcular_p1_caminho_critico(caminhos_criticos, no) * 3  # fator de escala topológico
        p2 = calcular_p2_obrigatoriedade(G, no, periodo_atual_aluno)
        p3 = calcular_p3_retencao_historica(no, df_historico)
        p4 = calcular_p4_sazonalidade(G, no)
        p5 = calcular_p5_atraso(G, no, periodo_atual_aluno)
        p6 = calcular_p6_penalizacao(G, no)

        subgrafo.nodes[no]['P1'] = p1
        subgrafo.nodes[no]['P2'] = p2
        subgrafo.nodes[no]['P3'] = p3
        subgrafo.nodes[no]['P4'] = p4
        subgrafo.nodes[no]['P5'] = p5
        subgrafo.nodes[no]['P6'] = p6
        subgrafo.nodes[no]['W']  = p1 + p2 + p3 + p4 + p5 + p6
        subgrafo.nodes[no]['disponivel'] = no in disciplinas_disponiveis

    return subgrafo


# -------------------------------------------------------------
# EXECUÇÃO PRINCIPAL (diagnóstico)
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
        print(f"Processando: {os.path.basename(caminho_historico)}\n")

        # 1. Parser
        curso, df_historico, disciplinas_resolvidas, lista_pendentes, \
            periodo_ingresso, suspensoes, media_aprovacoes = extrair_dados_completos_sigaa(caminho_historico)

        # 2. Grafo completo da grade
        grade = carregar_grade(curso)
        DAG = construir_grafo_curricular(grade)

        # 3. Variáveis do aluno
        periodo_atual = calcular_periodo_atual_aluno(periodo_ingresso, suspensoes)
        disciplinas_disponiveis = obter_disciplinas_disponiveis(DAG, disciplinas_resolvidas)

        # 4. Subgrafo de pendentes com pesos → produto deste módulo
        grafo_pendentes = construir_grafo_pendentes(
            DAG,
            disciplinas_disponiveis,
            disciplinas_resolvidas,
            df_historico,
            periodo_atual,
            lista_pendentes,  # necessário para o cálculo do P1 via grafo_pendentes.py
            grade             # necessário para o cálculo do P1 via grafo_pendentes.py
        )

        # 5. Diagnóstico: exibe apenas as disciplinas disponíveis, ordenadas por W
        print(f"--- GRAFO DE PENDENTES ({curso}) ---")
        print(f"Ingresso: {periodo_ingresso} | Suspensões: {len(suspensoes)} | Período atual: {periodo_atual}\n")
        print(f"Nós no grafo de pendentes : {grafo_pendentes.number_of_nodes()}")
        print(f"Disciplinas disponíveis   : {len(disciplinas_disponiveis)}")
        print(f"Arestas (dependências)    : {grafo_pendentes.number_of_edges()}\n")

        # 6. Impressão completa do grafo
        print(f"\n{'='*110}")
        print(f"GRAFO COMPLETO DE PENDENTES ({grafo_pendentes.number_of_nodes()} nós)")
        print(f"{'='*110}")
        print(f"{'CÓDIGO':<10} | {'DISP':<5} | {'CH':<4} | {'W':<6} | {'P1':<5} | {'P2':<5} | {'P3':<5} | {'P4':<5} | {'P5':<5} | {'P6':<5} | NOME")
        print("-" * 110)

        todos_nos = [
            (no, dados) for no, dados in grafo_pendentes.nodes(data=True)
        ]
        todos_nos.sort(key=lambda x: (not x[1].get('disponivel'), -x[1]['W']))

        for no, dados in todos_nos:
            disp = "SIM" if dados.get('disponivel') else "NÃO"
            print(
                f"{no:<10} | {disp:<5} | {dados['ch']:<4} | {dados['W']:<6} | "
                f"{dados['P1']:<5} | {dados['P2']:<5} | {dados['P3']:<5} | "
                f"{dados['P4']:<5} | {dados['P5']:<5} | {dados['P6']:<5} | "
                f"{dados['nome']}"
            )

        print("-" * 110)

        # Arestas: mostra quem depende de quem
        print(f"\nDEPENDÊNCIAS (arestas do grafo):")
        print(f"{'PRÉ-REQUISITO':<12} --> DESBLOQUEIA")
        print("-" * 50)
        for u, v in sorted(grafo_pendentes.edges()):
            nome_v = grafo_pendentes.nodes[v].get('nome', '')
            print(f"{u:<12} --> {v:<10} ({nome_v})")

        nos_disponiveis = [
            (no, dados) for no, dados in grafo_pendentes.nodes(data=True)
            if dados.get('disponivel')
        ]
        nos_disponiveis.sort(key=lambda x: x[1]['W'], reverse=True)

        print(f"{'CÓDIGO':<10} | {'CH':<4} | {'W':<6} | {'P1':<5} | {'P2':<5} | {'P3':<5} | {'P4':<5} | {'P5':<5} | {'P6':<5} | NOME")
        print("-" * 110)
        for no, dados in nos_disponiveis:
            print(
                f"{no:<10} | {dados['ch']:<4} | {dados['W']:<6} | "
                f"{dados['P1']:<5} | {dados['P2']:<5} | {dados['P3']:<5} | "
                f"{dados['P4']:<5} | {dados['P5']:<5} | {dados['P6']:<5} | "
                f"{dados['nome']}"
            )
        print("-" * 110)
        print(f"\nEste grafo será consumido pela BFS na próxima etapa.")