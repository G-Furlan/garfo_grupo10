import pdfplumber
import pandas as pd
import re
import json
import os
import glob

def extrair_dados_completos_sigaa(caminho_pdf):
    disciplinas_brutas = []
    pendentes = []
    codigos_equivalencias = [] # 1. Lista única para reunir as equivalências extraídas
    codigos_suspensoes = [] # 2. Lista única para reunir as suspensões extraídas
    curso_identificado = "DESCONHECIDO"
    
    # Flags para controlar quando o parser deve ler cada seção do texto
    capturando_pendentes = False 
    capturando_suspensoes = False 
    capturando_equivalencias = False 
    
    # Padrão Regex para capturar:
    # 1. Códigos da UNIFEI (Ex: COM110, XDES01, MAT00A, SIN130)
    padrao_codigo_unifei = r'\b([A-Z]{3,4}[0-9]{2}[0-9A-Z]?)\b'
    # 2. Códigos de suspensão da UNIFEI (Ex: 2025.1, 2025.2)
    padrao_suspensao_unifei = r'\b([0-9]{4}[.]{1}[1-2]{1}?)\b'

    with pdfplumber.open(caminho_pdf) as pdf:
        
        # -------------------------------------------------------------
        # ETAPA 0: Extração do Curso (Apenas na primeira página)
        # -------------------------------------------------------------
        texto_cabecalho = pdf.pages[0].extract_text()
        periodo_ingresso = "2024.1"

        if texto_cabecalho:
            texto_cabecalho_upper = texto_cabecalho.upper()
            if "CIÊNCIA DA COMPUTAÇÃO" in texto_cabecalho_upper or "CIENCIA DA COMPUTACAO" in texto_cabecalho_upper:
                curso_identificado = "CCO"
            elif "SISTEMAS DE INFORMAÇÃO" in texto_cabecalho_upper or "SISTEMAS DE INFORMACAO" in texto_cabecalho_upper:
                curso_identificado = "SIN"

            match_ingresso = re.search(r'Ano\s*/\s*Per[íi]odo Letivo Inicial:\s*([0-9]{4}\.[1-2])', texto_cabecalho)
            if match_ingresso:
                periodo_ingresso = match_ingresso.group(1)

        for page in pdf.pages:
            
            # -------------------------------------------------------------
            # ETAPA 1: Extração do Histórico (Cursadas/Cursando) via Tabelas
            # -------------------------------------------------------------
            tabelas = page.extract_tables()
            for tabela in tabelas:
                for linha in tabela:
                    if not linha or len(linha) < 11:
                        continue
                    
                    codigo = str(linha[2]).strip()
                    situacao = str(linha[10]).strip()
                    
                    if len(codigo) >= 4 and codigo != "None" and "Componente" not in codigo:
                        if situacao in ['REP', 'REPMF']:
                            situacao = 'REP'
                        
                        disciplinas_brutas.append({
                            'codigo': codigo,
                            'situacao': situacao
                        })

            # -------------------------------------------------------------
            # ETAPA 2: Extração de Pendentes e Equivalências via Texto Puro
            # -------------------------------------------------------------
            texto_pagina = page.extract_text()
            if texto_pagina:
                linhas_texto = texto_pagina.split('\n')
                
                for linha in linhas_texto:
                    
                    # 1. Gatilho de LIGAR
                    if "Suspensões" in linha:
                        capturando_suspensoes = True
                        # O 'continue' foi removido para não pular a leitura desta linha
                        
                    # 2. Executa a EXTRAÇÃO imediatamente
                    if capturando_suspensoes:
                        # Regex otimizado para o padrão AAAA.S (ex: 2025.1)
                        suspensoes_linha = re.findall(r'\b([0-9]{4}\.[1-2])\b', linha)
                        codigos_suspensoes.extend(suspensoes_linha)

                    # 3. Gatilho de DESLIGAR
                    if capturando_suspensoes and any(termo in linha for termo in [
                        "Prorrogações",
                        "Componentes Curriculares Cursados",
                        "Componentes Curriculares Optativos",
                        "Atividades Complementares",
                        "Atividades de Extensão",
                        "Índice de Rendimento",
                        "Observações",
                        "Equivalências"
                    ]):
                        capturando_suspensoes = False
                        

                    # Gatilho de INÍCIO da captura de Pendentes
                    if "Componentes Curriculares Obrigatórios Pendentes" in linha:
                        capturando_pendentes = True
                        continue
                    
                    # Gatilhos de PARADA da captura de Pendentes
                    if capturando_pendentes and any(termo in linha for termo in [
                        "Componentes Curriculares Optativos",
                        "Atividades Complementares",
                        "Atividades de Extensão",
                        "Índice de Rendimento",
                        "Observações",
                        "Equivalências"
                    ]):
                        capturando_pendentes = False
                    
                    # Gatilho de INÍCIO da captura de Equivalências
                    if "Equivalências" in linha:
                        capturando_equivalencias = True
                        continue
                        
                    # Executa a captura de Pendentes
                    if capturando_pendentes:
                        match = re.search(padrao_codigo_unifei, linha)
                        if match:
                            pendentes.append(match.group(1))
                            
                    # Executa a captura de Equivalências (Pega ambos os códigos da linha)
                    if capturando_equivalencias:
                        codigos_linha = re.findall(padrao_codigo_unifei, linha)
                        # Garante que pegou exatamente o par (materia_alvo e materia_origem)
                        if len(codigos_linha) == 2:
                            codigos_equivalencias.extend(codigos_linha)

    # -------------------------------------------------------------
    # CONSOLIDAÇÃO DOS DADOS
    # -------------------------------------------------------------
    df_bruto = pd.DataFrame(disciplinas_brutas)
    
    if df_bruto.empty:
        df_consolidado = pd.DataFrame()
        disciplinas_resolvidas = []
    else:
        df_consolidado = df_bruto.groupby('codigo').agg(
            tentativas=('situacao', 'count'),
            reprovacoes=('situacao', lambda x: (x == 'REP').sum()),
            situacao_final=('situacao', lambda x: 'APR' if 'APR' in x.values else ('CUMP' if 'CUMP' in x.values else ('MATR' if 'MATR' in x.values else x.values[-1])))
        ).reset_index()
        
        # Mapeia as disciplinas resolvidas/concluídas iniciais
        disciplinas_resolvidas = df_consolidado[df_consolidado['situacao_final'].isin(['APR', 'MATR', 'CUMP'])]['codigo'].tolist()
    
    # -------------------------------------------------------------
    # 3. LÓGICA DE SUBSTITUIÇÃO DAS EQUIVALÊNCIAS DO PDF
    # -------------------------------------------------------------
    # O range começa em 1 e pula de 2 em 2 (1, 3, 5...) avaliando apenas matérias cursadas.
    # Se der Match, substitui pelo índice j-1 (a equivalente correta da grade).
    for i in range(len(disciplinas_resolvidas)):
        for j in range(1, len(codigos_equivalencias), 2):
            if disciplinas_resolvidas[i] == codigos_equivalencias[j]:
                disciplinas_resolvidas[i] = codigos_equivalencias[j-1]

    mapa_equivalencias = {}
    try:
        diretorio_script = os.path.dirname(os.path.abspath(__file__))
        caminho_json = os.path.join(diretorio_script, "data", "equivalencias.json")
        with open(caminho_json, 'r', encoding='utf-8') as f:
            mapa_equivalencias = json.load(f)
    except FileNotFoundError:
        print("Aviso: Arquivo de equivalências JSON não encontrado. Rodando apenas com as do PDF.")

    # 2. Expande as disciplinas resolvidas adicionando também todas as equivalentes do JSON
    disciplinas_resolvidas_expandidas = set(disciplinas_resolvidas)
    for disc in disciplinas_resolvidas:
        if disc in mapa_equivalencias:
            equivalentes = mapa_equivalencias[disc]
            disciplinas_resolvidas_expandidas.update(equivalentes)

    # 3. Remove duplicatas da captura de pendentes
    pendentes_unicos = set(pendentes)
    
    # 4. Filtra as pendências reais subtraindo as disciplinas resolvidas/substituídas
    pendentes_reais = [codigo for codigo in pendentes_unicos if codigo not in disciplinas_resolvidas_expandidas]
    
    return curso_identificado, df_consolidado, pendentes_reais, periodo_ingresso, codigos_suspensoes

# --- Execução Principal ---
if __name__ == "__main__":
    # 1. Defina o caminho da pasta onde os uploads ou os arquivos de histórico são salvos
    # Mudamos para apontar para o diretório (pasta) e não para um arquivo fixo
    # 1. Pega o caminho absoluto da pasta onde este script (parser_historico.py) está salvo
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))

    # 2. Constrói o caminho subindo ou navegando até a pasta do Dataset

    diretorio_historicos = os.path.join(diretorio_atual, "data", "Dataset-Cenario1-RecomendacaoMatricula")

    # 3. Busca todos os arquivos .pdf dentro desta pasta
    arquivos_pdf = glob.glob(os.path.join(diretorio_historicos, "*.pdf"))

    if not arquivos_pdf:
        print(f"Erro: Nenhum arquivo PDF encontrado no diretório mapeado:\n-> {diretorio_historicos}\nPor favor, verifique o caminho ou faça o upload.")
    else:
        # 4. Encontra o arquivo mais recente baseado na data de modificação
        caminho_arquivo = max(arquivos_pdf, key=os.path.getmtime)
        
        print(f"Arquivo detectado automaticamente para análise: {os.path.basename(caminho_arquivo)}")
        
    # 5. Executa a sua função de extração com o arquivo mais recente
        curso, df_historico, lista_pendentes, periodo_ingresso, suspensoes = extrair_dados_completos_sigaa(caminho_arquivo)

        # --- Print dos Resultados ---
        print(f"\nCurso Identificado: {curso}\n")

        print("Tabela Consolidada para Alimentação do Grafo:")
        print(df_historico.head(10).to_string(index=False))
        print("...\n")

        print(f"Total de Disciplinas Obrigatórias Pendentes Encontradas: {len(lista_pendentes)}")
        print("Lista de Pendentes:")
        print(lista_pendentes)
