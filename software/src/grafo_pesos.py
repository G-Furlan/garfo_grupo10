# -*- coding: utf-8 -*-
"""
Recebe o grafo de pendentes (grafo_pendentes.construir_grafo_dependencias)
e atribui a cada nó (disciplina) os pesos P1..P5, o peso total W e o booleano
'disponivel'.

Esquema de pesos (definido pelo grupo):
    P1  Caminho crítico   — quanto esta disciplina destrava à frente (vem da parte 1)
    P2  Obrigatoriedade   — bônus fixo por ser obrigatória
    P3  Retenção          — bônus por reprovações anteriores (do parser)
    P4  Sazonalidade      — bônus se ofertada em 1 só semestre (uma chance por ano)
    P5  Atraso            — bônus se o período ideal já passou (ou é o atual)
    W = P1 + P2 + P3 + P4 + P5
"""

from grafo_pendentes import calcular_caminhos_criticos


# -------------------------------------------------------------
# CONSTANTES DE CALIBRAÇÃO 
# -------------------------------------------------------------
FATOR_P1          = 4   # P1 = caminho_critico * FATOR_P1
P2_OBRIGATORIA    = 5   # P2 = bônus fixo para obrigatória (0 para optativa)
PESO_REPROVACAO   = 4   # P3 = nº de reprovações * PESO_REPROVACAO
PESO_SAZONALIDADE = 5   # P4 = bônus para oferta de semestre único
PESO_ATRASO       = 2   # P5 = (períodos de atraso + 1) * PESO_ATRASO


# -------------------------------------------------------------
# DISPONIBILIDADE
# -------------------------------------------------------------
def esta_disponivel(node, disciplinas_resolvidas):
    """True se ao menos um grupo de pré-requisitos está satisfeito."""
    grupos = node.get('pre_requisitos', [])
    if not grupos:
        return True
    return any(all(req in disciplinas_resolvidas for req in g) for g in grupos)


# -------------------------------------------------------------
# COMPONENTES P1 .. P5
# -------------------------------------------------------------
def calcular_p1(codigo, caminhos_criticos):
    """P1 — Topológico: tamanho da cadeia de pendentes que esta disciplina destrava."""
    return caminhos_criticos.get(codigo, 0) * FATOR_P1


def calcular_p2(node):
    """P2 — Obrigatoriedade: bônus fixo por ser obrigatória."""
    return P2_OBRIGATORIA if node.get('tipo') == 'Obrigatoria' else 0


def calcular_p3(codigo, df_historico):
    """P3 — Retenção histórica: bônus proporcional às reprovações (coletadas pelo parser)."""
    if df_historico is None or df_historico.empty:
        return 0
    if codigo not in df_historico['codigo'].values:
        return 0
    linha = df_historico[df_historico['codigo'] == codigo].iloc[0]
    return int(linha['reprovacoes']) * PESO_REPROVACAO


def calcular_p4(node):
    """
    P4 — Sazonalidade: bônus se a disciplina é ofertada em UM ÚNICO semestre
    ('2026-1' ou '2026-2'). Ofertada nos dois ('2026-1 / 2026-2') ou desconhecida
    ('') não recebe bônus — o aluno tem mais de uma janela por ano.
    """
    po = node.get('periodo_ofertado', '')
    if not po or '/' in po:
        return 0
    return PESO_SAZONALIDADE


def calcular_p5(node, periodo_atual_aluno):
    """
    P5 — Atraso: bônus quando o período ideal da disciplina já chegou ou passou.
    Aplica-se SÓ a obrigatórias — optativas não têm prazo, então não acumulam atraso.
    Disciplina do período atual recebe 1*PESO_ATRASO; cada período de atraso soma mais.
    """
    periodo_atual_aluno = periodo_atual_aluno + 1
    if node.get('tipo') != 'Obrigatoria':
        return 0
    periodo_ideal = node.get('periodo_ideal', 0)
    if periodo_ideal <= 0 or periodo_ideal > periodo_atual_aluno:
        return 0
    return (periodo_atual_aluno - periodo_ideal + 1) * PESO_ATRASO


# -------------------------------------------------------------
# ATRIBUIÇÃO DE PESOS (PRODUTO DA PARTE 2)
# -------------------------------------------------------------
def atribuir_pesos(grafo, disciplinas_resolvidas, df_historico, periodo_atual_aluno):
    """
    Aumenta cada nó do grafo da parte 1 com P1..P5, W e disponivel.
    Muta o grafo recebido e também o retorna.
    """
    resolvidas = set(disciplinas_resolvidas)
    caminhos = calcular_caminhos_criticos(grafo)

    for codigo, node in grafo['nos'].items():
        p1 = calcular_p1(codigo, caminhos)
        p2 = calcular_p2(node)
        p3 = calcular_p3(codigo, df_historico)
        p4 = calcular_p4(node)
        p5 = calcular_p5(node, periodo_atual_aluno)

        node['P1'], node['P2'], node['P3'], node['P4'], node['P5'] = p1, p2, p3, p4, p5
        node['W'] = p1 + p2 + p3 + p4 + p5
        node['disponivel'] = esta_disponivel(node, resolvidas)

    return grafo


# -------------------------------------------------------------
# IMPRESSÃO (diagnóstico)
# -------------------------------------------------------------
def imprimir_grafo_ponderado(grafo):
    nos = grafo['nos']
    print(f"\n{'='*100}")
    print(f"GRAFO PONDERADO — {len(nos)} disciplinas")
    print(f"{'='*100}")
    print(f"{'CÓDIGO':<10} | {'DISP':<4} | {'W':<5} | "
          f"{'P1':<4} | {'P2':<4} | {'P3':<4} | {'P4':<4} | {'P5':<4} | NOME")
    print("-" * 100)
    ordenados = sorted(nos.items(), key=lambda x: (not x[1]['disponivel'], -x[1]['W']))
    for cod, d in ordenados:
        disp = "SIM" if d['disponivel'] else "—"
        print(f"{cod:<10} | {disp:<4} | {d['W']:<5} | "
              f"{d['P1']:<4} | {d['P2']:<4} | {d['P3']:<4} | {d['P4']:<4} | {d['P5']:<4} | {d['nome']}")
    print("-" * 100)
    disp = sum(1 for d in nos.values() if d['disponivel'])
    print(f"Disponíveis para matrícula: {disp} de {len(nos)}")


# -------------------------------------------------------------
# EXECUÇÃO PRINCIPAL
# -------------------------------------------------------------
if __name__ == "__main__":
    from parser_historico import extrair_dados_completos_sigaa
    from grafo_pendentes import carregar_grade, construir_grafo_dependencias
    from datetime import datetime
    import os, glob

    def calcular_periodo_atual_aluno(periodo_ingresso, suspensoes):
        if not periodo_ingresso:
            return 1
        ano_i, sem_i = map(int, periodo_ingresso.split('.'))
        hoje = datetime.now()
        sem_atual = 1 if hoje.month <= 6 else 2
        decorridos = ((hoje.year - ano_i) * 2) + (sem_atual - sem_i) + 1
        return max(1, decorridos - len(suspensoes))

    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    diretorio_historicos = os.path.join(diretorio_atual, "data", "Dataset-Cenario1-RecomendacaoMatricula")
    arquivos_pdf = glob.glob(os.path.join(diretorio_historicos, "*.pdf"))

    if not arquivos_pdf:
        print(f"Erro: nenhum PDF encontrado em:\n-> {diretorio_historicos}")
    else:
        caminho = max(arquivos_pdf, key=os.path.getmtime)
        print(f"Processando: {os.path.basename(caminho)}")
        curso, df_historico, disciplinas_resolvidas, lista_pendentes, \
            periodo_ingresso, suspensoes, media_aprovacoes = extrair_dados_completos_sigaa(caminho)
        grade = carregar_grade(curso)
        grafo = construir_grafo_dependencias(lista_pendentes, grade, curso=curso)
        periodo_atual = calcular_periodo_atual_aluno(periodo_ingresso, suspensoes)
        grafo = atribuir_pesos(grafo, disciplinas_resolvidas, df_historico, periodo_atual)
        imprimir_grafo_ponderado(grafo)