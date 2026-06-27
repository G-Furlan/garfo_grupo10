import json
import networkx as nx
import pandas as pd
from datetime import datetime

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
    todas_disciplinas = {**grade.get('obrigatorias', {}), **grade.get('optativas', {})}
    
    for codigo, dados in todas_disciplinas.items():
        G.add_node(
            codigo,
            ch=dados.get('ch', 64),
            periodo_ideal=dados.get('periodo_ideal', 0),
            tipo="Obrigatoria" if codigo in grade.get('obrigatorias', {}) else "Optativa"
        )
        for pre_req in dados.get('pre_requisitos', []):
            G.add_edge(pre_req, codigo)
            
    return G

def obter_disciplinas_disponiveis(G, disciplinas_resolvidas):
    """Filtra o grafo para retornar apenas os vértices com pré-requisitos satisfeitos."""
    disponiveis = []
    for no in G.nodes():
        if no in disciplinas_resolvidas:
            continue
        pre_requisitos = list(G.predecessors(no))
        if all(pr in disciplinas_resolvidas for pr in pre_requisitos):
            disponiveis.append(no)
    return disponiveis

# -------------------------------------------------------------
# FUNÇÕES DE CÁLCULO DE PESOS (P1 a P6)
# -------------------------------------------------------------

def calcular_p1_caminho_critico(G, codigo_disciplina):
    """P1 - Fatores Topológicos: Tamanho da corrente de pré-requisitos."""
    if codigo_disciplina not in G:
        return 0
    descendentes = nx.descendants(G, codigo_disciplina)
    if not descendentes:
        return 0
    subgrafo = G.subgraph(descendentes | {codigo_disciplina})
    return nx.dag_longest_path_length(subgrafo)

def calcular_p2_obrigatoriedade(G, codigo_disciplina):
    """P2 - Obrigatoriedade: Peso escalar base."""
    if codigo_disciplina not in G:
        return 0
    tipo_disciplina = G.nodes[codigo_disciplina].get('tipo', 'Desconhecido')
    
    PESO_OBRIGATORIA = 100
    PESO_OPTATIVA = 10
    
    if tipo_disciplina == 'Obrigatoria':
        return PESO_OBRIGATORIA
    elif tipo_disciplina == 'Optativa':
        return PESO_OPTATIVA
    return 0

def calcular_p3_retencao_historica(codigo_disciplina, df_historico):
    """P3 - Retenção Histórica: Bônus baseado em reprovações anteriores."""
    PESO_REPROVACAO = 20
    if not df_historico.empty and codigo_disciplina in df_historico['codigo'].values:
        linha = df_historico[df_historico['codigo'] == codigo_disciplina].iloc[0]
        reprovacoes = linha['reprovacoes']
        return reprovacoes * PESO_REPROVACAO
    return 0

def calcular_p4_sazonalidade(codigo_disciplina, periodo_atual_impar_par):
    """P4 - Sazonalidade: Bônus para disciplinas com oferta restrita. (MOCK)"""
    # Requer integração futura com o JSON de horários ofertados
    PESO_SAZONALIDADE = 30
    # Lógica de implementação pendente dos dados de horário
    return 0 

def calcular_p5_atraso(G, codigo_disciplina, periodo_atual_aluno):
    """P5 - Fatores de Tempo: Taxa de atraso em relação ao período ideal."""
    PESO_ATRASO = 15
    periodo_ideal = G.nodes[codigo_disciplina].get('periodo_ideal', 0)
    
    if periodo_ideal > 0 and periodo_atual_aluno > periodo_ideal:
        taxa_atraso = periodo_atual_aluno - periodo_ideal
        return taxa_atraso * PESO_ATRASO
    return 0

def calcular_p6_penalizacao(G, codigo_disciplina):
    """P6 - Pesos Negativos: Balanceamento e redução de prioridade."""
    PENALIDADE_OPTATIVA = -5
    tipo = G.nodes[codigo_disciplina].get('tipo', 'Optativa')
    if tipo == 'Optativa':
        return PENALIDADE_OPTATIVA
    return 0

def calcular_periodo_atual_aluno(periodo_ingresso, suspensoes):
    """
    Calcula o período real do discente baseado no tempo decorrido
    desde o ingresso, descontando os semestres suspensos.
    """
    if not periodo_ingresso:
        return 1
        
    ano_ingresso, sem_ingresso = map(int, periodo_ingresso.split('.'))
    
    # Obtém a data real do sistema em que o código está sendo executado
    hoje = datetime.now()
    ano_atual = hoje.year
    # No Brasil, meses de 1 a 6 são semestre 1. Meses de 7 a 12 são semestre 2.
    sem_atual = 1 if hoje.month <= 6 else 2
    
    # Diferença algébrica total de semestres
    periodos_decorridos = ((ano_atual - ano_ingresso) * 2) + (sem_atual - sem_ingresso) + 1
    
    # Abate os semestres trancados/suspensos
    periodo_real = periodos_decorridos - len(suspensoes)
    
    # Retorna no mínimo 1 para evitar períodos negativos em casos de anomalias no PDF
    return max(1, periodo_real)

# -------------------------------------------------------------
# ALGORITMO DE RECOMENDAÇÃO
# -------------------------------------------------------------

def gerar_recomendacao_matricula(G, disciplinas_aptas, df_historico, periodo_atual_aluno, limite_ch=400):
    """
    Calcula o peso total (W) para cada disciplina apta e seleciona a melhor
    combinação respeitando o limite de Carga Horária.
    """
    tabela_pesos = {}
    for disc in disciplinas_aptas:
        p1 = calcular_p1_caminho_critico(G, disc) * 10  # Fator de escala topológico
        p2 = calcular_p2_obrigatoriedade(G, disc)
        p3 = calcular_p3_retencao_historica(disc, df_historico)
        p4 = calcular_p4_sazonalidade(disc, 1) 
        p5 = calcular_p5_atraso(G, disc, periodo_atual_aluno)
        p6 = calcular_p6_penalizacao(G, disc)
        
        w_total = p1 + p2 + p3 + p4 + p5 + p6
        ch_disciplina = G.nodes[disc].get('ch', 64)
        
        tabela_pesos[disc] = {
            'P1': p1, 'P2': p2, 'P3': p3, 'P4': p4, 'P5': p5, 'P6': p6,
            'W': w_total,
            'CH': ch_disciplina
        }
        
    # Ordenação decrescente pelo peso total (W)
    disciplinas_ordenadas = sorted(tabela_pesos.items(), key=lambda x: x[1]['W'], reverse=True)
    
    recomendacao = []
    ch_acumulada = 0
    
    # Seleção Gulosa (Greedy) respeitando o limite de Carga Horária
    for disc, dados in disciplinas_ordenadas:
        if ch_acumulada + dados['CH'] <= limite_ch:
            recomendacao.append((disc, dados))
            ch_acumulada += dados['CH']
            
    return recomendacao, disciplinas_ordenadas

# --- Execução Principal ---
if __name__ == "__main__":
    from parser_historico import extrair_dados_completos_sigaa
    import os
    import glob
    
    # 1. Busca dinâmica do PDF mais recente (igual ao parser)
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    diretorio_historicos = os.path.join(diretorio_atual, "data", "Dataset-Cenario1-RecomendacaoMatricula")
    arquivos_pdf = glob.glob(os.path.join(diretorio_historicos, "*.pdf"))
    
    if not arquivos_pdf:
        print(f"Erro: Nenhum arquivo PDF encontrado no diretório mapeado:\n-> {diretorio_historicos}")
    else:
        # Pega o arquivo mais recente
        caminho_historico = max(arquivos_pdf, key=os.path.getmtime)
        print(f"Gerando recomendação baseada no arquivo: {os.path.basename(caminho_historico)}\n")
        
        # 2. Extração via Parser (ATUALIZADO PARA RECEBER AS RESOLVIDAS NA POSIÇÃO CORRETA)
        curso, df_historico, disciplinas_resolvidas, lista_pendentes, periodo_ingresso, suspensoes = extrair_dados_completos_sigaa(caminho_historico)
        
        # 3. Inicialização do Grafo
        grade = carregar_grade(curso)
        DAG = construir_grafo_curricular(grade)
        
        # 4. Determinação de Variáveis Externas
        disciplinas_aptas = obter_disciplinas_disponiveis(DAG, disciplinas_resolvidas)
        
        # CÁLCULO DINÂMICO DO PERÍODO DO ALUNO 
        periodo_estimado_aluno = calcular_periodo_atual_aluno(periodo_ingresso, suspensoes)
        
        carga_horaria_maxima = 384  # Limite aproximado de 6 disciplinas de 64h
        
        # 5. Geração da Recomendação
        recomendacao_final, fila_geral = gerar_recomendacao_matricula(
            DAG, 
            disciplinas_aptas, 
            df_historico, 
            periodo_estimado_aluno, 
            carga_horaria_maxima
        )
        
        # 6. Apresentação de Resultados
        print(f"--- RECOMENDAÇÃO DE MATRÍCULA ({curso}) ---")
        print(f"Ingresso: {periodo_ingresso} | Suspensões Detectadas: {len(suspensoes)}")
        print(f"Período Atual Estimado: {periodo_estimado_aluno} | Carga Horária Máxima: {carga_horaria_maxima}h\n")
        
        print(f"{'CÓDIGO':<10} | {'CH':<5} | {'W (TOTAL)':<10} | {'P1':<5} | {'P2':<5} | {'P3':<5} | {'P5':<5} | {'P6':<5}")
        print("-" * 75)
        
        ch_total = 0
        for disc, dados in recomendacao_final:
            print(f"{disc:<10} | {dados['CH']:<5} | {dados['W']:<10} | {dados['P1']:<5} | {dados['P2']:<5} | {dados['P3']:<5} | {dados['P5']:<5} | {dados['P6']:<5}")
            ch_total += dados['CH']
            
        print("-" * 75)
        print(f"Carga Horária Total Recomendada: {ch_total}h")