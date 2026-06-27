import json
import networkx as nx

def carregar_grade(curso):
    """Carrega o banco de dados da estrutura curricular do curso correspondente."""
    caminho_arquivo = f"src/data/grade_{curso.lower()}.json"
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo de grade não encontrado: {caminho_arquivo}")

def construir_grafo_curricular(grade):
    """Constrói o Grafo Direcionado Acíclico (DAG) da matriz curricular."""
    G = nx.DiGraph()
    
    # Agrupa obrigatórias e optativas para iteração unificada
    todas_disciplinas = {**grade.get('obrigatorias', {}), **grade.get('optativas', {})}
    
    # 1. Adição dos Vértices (Disciplinas) com seus atributos base
    for codigo, dados in todas_disciplinas.items():
        G.add_node(
            codigo,
            ch=dados.get('ch', 64),
            periodo_ideal=dados.get('periodo_ideal', 0),
            tipo="Obrigatoria" if codigo in grade.get('obrigatorias', {}) else "Optativa"
        )
        
        # 2. Adição das Arestas Direcionadas (Pré-requisitos)
        for pre_req in dados.get('pre_requisitos', []):
            # Aresta: Pré-requisito -> Disciplina Alvo
            G.add_edge(pre_req, codigo)
            
    return G

def obter_disciplinas_disponiveis(G, disciplinas_resolvidas):
    """
    Filtra o grafo para retornar apenas os vértices que o aluno está apto a cursar,
    garantindo que todos os pré-requisitos foram satisfeitos.
    """
    disponiveis = []
    
    for no in G.nodes():
        # Exclui disciplinas já aprovadas, matriculadas ou cumpridas via equivalência
        if no in disciplinas_resolvidas:
            continue
            
        # Analisa os predecessores (pré-requisitos diretos) no grafo
        pre_requisitos = list(G.predecessors(no))
        
        # A disciplina só está disponível se a interseção dos pré-requisitos 
        # com as disciplinas resolvidas for total
        if all(pr in disciplinas_resolvidas for pr in pre_requisitos):
            disponiveis.append(no)
            
    return disponiveis

def calcular_p1_caminho_critico(G, codigo_disciplina):
    """
    Calcula a variável P1 (Fatores Topológicos).
    Identifica o tamanho do caminho crítico (corrente de dependências mais longa)
    que se origina a partir do vértice fornecido.
    
    Parâmetros:
    G (nx.DiGraph): O Grafo Direcionado Acíclico da matriz curricular.
    codigo_disciplina (str): O código do vértice a ser analisado.
    
    Retorno:
    int: O valor escalar correspondente ao tamanho do caminho crítico.
    """
    # Verifica se o nó existe no grafo para evitar KeyError
    if codigo_disciplina not in G:
        return 0

    # Extrai todos os nós que dependem, direta ou indiretamente, desta disciplina
    descendentes = nx.descendants(G, codigo_disciplina)
    
    # Se não houver descendentes, a disciplina não é pré-requisito para nenhuma outra (fim de cadeia)
    if not descendentes:
        return 0
        
    # Cria um subgrafo induzido contendo a disciplina atual e todos os seus descendentes
    subgrafo = G.subgraph(descendentes | {codigo_disciplina})
    
    # O método dag_longest_path_length retorna o número de arestas no caminho mais longo
    tamanho_caminho = nx.dag_longest_path_length(subgrafo)
    
    return tamanho_caminho


# --- Execução Principal (Pipeline Atualizado) ---
if __name__ == "__main__":
    from parser_historico import extrair_dados_completos_sigaa
    
    # 1. Extração de Dados
    caminho_historico = "src/data/Dataset_-_Cenrio_1_-_Recomendao_Matrcula/historico_CCO-5.pdf"
    curso, df_historico, disciplinas_resolvidas = extrair_dados_completos_sigaa(caminho_historico)
    
    # 2. Construção do Grafo
    grade = carregar_grade(curso)
    DAG = construir_grafo_curricular(grade)
    
    # 3. Determinação do Estado de Matrícula
    disciplinas_aptas = obter_disciplinas_disponiveis(DAG, disciplinas_resolvidas)
    
    # 4. Cálculo do Peso P1 (Fatores Topológicos)
    pesos_p1 = {}
    for disciplina in disciplinas_aptas:
        peso_topologico = calcular_p1_caminho_critico(DAG, disciplina)
        pesos_p1[disciplina] = peso_topologico
        
    # Ordenação decrescente para visualização das prioridades topológicas
    pesos_p1_ordenados = dict(sorted(pesos_p1.items(), key=lambda item: item[1], reverse=True))
    
    print(f"Topologia do Grafo: {DAG.number_of_nodes()} Vértices e {DAG.number_of_edges()} Arestas.\n")
    print("Avaliação da Variável P1 (Tamanho do Caminho Crítico) para Disciplinas Aptas:")
    
    for disciplina, peso in pesos_p1_ordenados.items():
        print(f"[{disciplina}] P1: {peso} " + ("(Alta Prioridade Estrutural)" if peso >= 3 else ""))