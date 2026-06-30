import pdfplumber
import pandas as pd
import re
import json
import os
import glob

def extrair_dados_completos_sigaa(caminho_pdf):
    disciplinas_brutas = []
    pendentes = []
    codigos_equivalencias = [] 
    codigos_suspensoes = [] 
    curso_identificado = "DESCONHECIDO"
    
    # Flags para controlar quando o parser deve ler cada seção do texto
    capturando_pendentes = False 
    capturando_suspensoes = False 
    capturando_equivalencias = False 
    
    # Padrões Regex
    padrao_codigo_unifei = r'\b([A-Z]{3,4}[0-9]{2}[0-9A-Z]?)\b'
    padrao_suspensao_unifei = r'\b([0-9]{4}[.]{1}[1-2]{1}?)\b'

    with pdfplumber.open(caminho_pdf) as pdf:
        
        # -------------------------------------------------------------
        # ETAPA 0: Extração do Curso e Ingresso
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

        ultimo_semestre_visto = "Desconhecido" # Variável para lidar com células mescladas no PDF

        for page in pdf.pages:
            
            # -------------------------------------------------------------
            # ETAPA 1: Extração do Histórico (Cursadas/Cursando) via Tabelas
            # -------------------------------------------------------------
            tabelas = page.extract_tables()
            for tabela in tabelas:
                for linha in tabela:
                    if not linha or len(linha) < 11:
                        continue
                    
                    # 1.1 Captura do Semestre
                    coluna_semestre = str(linha[0]).strip()
                    match_sem = re.search(r'([0-9]{4}\.[1-2])', coluna_semestre)
                    if match_sem:
                        ultimo_semestre_visto = match_sem.group(1)
                    
                    codigo = str(linha[2]).strip()
                    situacao = str(linha[10]).strip()
                    
                    if len(codigo) >= 4 and codigo != "None" and "Componente" not in codigo:
                        if situacao in ['REP', 'REPMF']:
                            situacao = 'REP'
                        
                        # Adicionamos o semestre no dicionário
                        disciplinas_brutas.append({
                            'semestre': ultimo_semestre_visto,
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
                    
                    if "Suspensões" in linha:
                        capturando_suspensoes = True
                        
                    if capturando_suspensoes:
                        suspensoes_linha = re.findall(r'\b([0-9]{4}\.[1-2])\b', linha)
                        codigos_suspensoes.extend(suspensoes_linha)

                    if capturando_suspensoes and any(termo in linha for termo in [
                        "Prorrogações", "Componentes Curriculares Cursados", 
                        "Componentes Curriculares Optativos", "Atividades Complementares", 
                        "Atividades de Extensão", "Índice de Rendimento", "Observações", "Equivalências"
                    ]):
                        capturando_suspensoes = False
                        
                    if "Componentes Curriculares Obrigatórios Pendentes" in linha:
                        capturando_pendentes = True
                        continue
                    
                    if capturando_pendentes and any(termo in linha for termo in [
                        "Componentes Curriculares Optativos", "Atividades Complementares", 
                        "Atividades de Extensão", "Índice de Rendimento", "Observações", "Equivalências"
                    ]):
                        capturando_pendentes = False
                    
                    if "Equivalências" in linha:
                        capturando_equivalencias = True
                        continue
                        
                    if capturando_pendentes:
                        match = re.search(padrao_codigo_unifei, linha)
                        if match:
                            pendentes.append(match.group(1))
                            
                    if capturando_equivalencias:
                        codigos_linha = re.findall(padrao_codigo_unifei, linha)
                        if len(codigos_linha) == 2:
                            codigos_equivalencias.extend(codigos_linha)

 # -------------------------------------------------------------
    # ETAPA 3: CONSOLIDAÇÃO E ANÁLISE DOS DADOS
    # -------------------------------------------------------------
    df_bruto = pd.DataFrame(disciplinas_brutas)
    media_aprovacao_semestre = 0.0
    
    if df_bruto.empty:
        df_consolidado = pd.DataFrame()
        disciplinas_resolvidas = []
    else:
        # --- NOVO CÁLCULO DA MÉDIA (Desconsiderando o semestre em andamento) ---
        status_sucesso = ['APR', 'APRN', 'CUMP', 'DISP']
        
        # 1. Lista todos os semestres reais (ignora erros de leitura) e ordena cronologicamente
        semestres_unicos = sorted(df_bruto[df_bruto['semestre'] != 'Desconhecido']['semestre'].unique())
        
        # 2. Remove o semestre mais recente da conta (último da lista)
        if len(semestres_unicos) > 1:
            semestres_fechados = semestres_unicos[:-1] # Corta o último fora
        else:
            # Se o aluno for calouro e só tiver 1 semestre no histórico, usa ele mesmo 
            # para não zerar a conta, mas o ideal é que ele já tenha histórico finalizado.
            semestres_fechados = semestres_unicos 
            
        # 3. Filtra o histórico para olhar apenas para os semestres que já terminaram
        df_historico_fechado = df_bruto[df_bruto['semestre'].isin(semestres_fechados)]
        
        # 4. Faz o cálculo real
        total_aprovacoes = len(df_historico_fechado[df_historico_fechado['situacao'].isin(status_sucesso)])
        total_semestres_avaliados = len(semestres_fechados)
        
        if total_semestres_avaliados > 0:
            media_aprovacao_semestre = total_aprovacoes / total_semestres_avaliados
        # -----------------------------------------------------------------------

        # Agrupamento da tabela do histórico 
        df_consolidado = df_bruto.groupby('codigo').agg(
            tentativas=('situacao', 'count'),
            reprovacoes=('situacao', lambda x: (x == 'REP').sum()),
            situacao_final=('situacao', lambda x: 'APR' if 'APR' in x.values else ('CUMP' if 'CUMP' in x.values else ('MATR' if 'MATR' in x.values else x.values[-1])))
        ).reset_index()
        
        disciplinas_resolvidas = df_consolidado[df_consolidado['situacao_final'].isin(['APR', 'MATR', 'CUMP'])]['codigo'].tolist()
    # -------------------------------------------------------------
    # 3. LÓGICA DE SUBSTITUIÇÃO DAS EQUIVALÊNCIAS
    # -------------------------------------------------------------
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
        pass 

    disciplinas_resolvidas_expandidas = set(disciplinas_resolvidas)
    for disc in disciplinas_resolvidas:
        if disc in mapa_equivalencias:
            equivalentes = mapa_equivalencias[disc]
            disciplinas_resolvidas_expandidas.update(equivalentes)

    pendentes_unicos = set(pendentes)
    pendentes_reais = [codigo for codigo in pendentes_unicos if codigo not in disciplinas_resolvidas_expandidas]

    return curso_identificado, df_consolidado, list(disciplinas_resolvidas_expandidas), pendentes_reais, periodo_ingresso, codigos_suspensoes, media_aprovacao_semestre


# --- Execução Principal ---
if __name__ == "__main__":
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    diretorio_historicos = os.path.join(diretorio_atual, "data", "Dataset-Cenario1-RecomendacaoMatricula")
    arquivos_pdf = glob.glob(os.path.join(diretorio_historicos, "*.pdf"))

    if not arquivos_pdf:
        print(f"Erro: Nenhum arquivo PDF encontrado no diretório mapeado:\n-> {diretorio_historicos}\nPor favor, verifique o caminho ou faça o upload.")
    else:
        caminho_arquivo = max(arquivos_pdf, key=os.path.getmtime)
        print(f"Arquivo detectado automaticamente para análise: {os.path.basename(caminho_arquivo)}")
        
        curso, df_historico, disciplinas_resolvidas, lista_pendentes, periodo_ingresso, suspensoes, media_aprovacoes = extrair_dados_completos_sigaa(caminho_arquivo)

        print(f"\n===== RESULTADOS DA ANÁLISE =====")
        print(f"Curso Identificado: {curso}")
        print(f"Período de Ingresso: {periodo_ingresso}")
        print(f"Média Histórica de Aprovações: {media_aprovacoes:.2f} matérias / semestre")
        print(f"=================================\n")

        print("Tabela Consolidada para Alimentação do Grafo:")
        print(df_historico.head(10).to_string(index=False))
        print("...\n")

        print(f"Total de Disciplinas Obrigatórias Pendentes Encontradas: {len(lista_pendentes)}")
        print("Lista de Pendentes:")
        print(lista_pendentes)

        print(f"Media de Aprovação por Semestre: {media_aprovacoes}")