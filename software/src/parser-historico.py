import pdfplumber
import pandas as pd
import re

def extrair_dados_completos_sigaa(caminho_pdf):
    disciplinas_brutas = []
    pendentes = []
    
    # Flag para controlar quando o parser deve ler os pendentes
    capturando_pendentes = False 
    
    # Padrão Regex para capturar códigos da UNIFEI (Ex: COM110, XDES01, MAT00A, SIN130)
    padrao_codigo_unifei = r'\b([A-Z]{3,4}[0-9]{2}[0-9A-Z]?)\b'

    with pdfplumber.open(caminho_pdf) as pdf:
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
            # ETAPA 2: Extração das Disciplinas Pendentes via Texto e Regex
            # -------------------------------------------------------------
            texto_pagina = page.extract_text()
            if texto_pagina:
                linhas_texto = texto_pagina.split('\n')
                
                for linha in linhas_texto:
                    # Gatilho de INÍCIO da captura
                    if "Componentes Curriculares Obrigatórios Pendentes" in linha:
                        capturando_pendentes = True
                        continue
                    
                    # Gatilhos de PARADA da captura (próximas seções do documento)
                    if capturando_pendentes and any(termo in linha for termo in [
                        "Componentes Curriculares Optativos",
                        "Atividades Complementares",
                        "Atividades de Extensão",
                        "Índice de Rendimento",
                        "Observações"
                    ]):
                        capturando_pendentes = False
                        
                    # Se estiver na seção correta, busca o código da disciplina na linha
                    if capturando_pendentes:
                        match = re.search(padrao_codigo_unifei, linha)
                        if match:
                            pendentes.append(match.group(1))

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
            situacao_final=('situacao', lambda x: 'APR' if 'APR' in x.values else ('MAT' if 'MAT' in x.values else x.values[-1]))
        ).reset_index()
        
        # Mapeia as disciplinas que não requerem recomendação de matrícula
        disciplinas_resolvidas = df_consolidado[df_consolidado['situacao_final'].isin(['APR', 'MAT'])]['codigo'].tolist()
    
    # Remove duplicatas da captura via Regex
    pendentes_unicos = set(pendentes)
    
    # Filtra as pendências, subtraindo as disciplinas com status resolvido
    pendentes_reais = [codigo for codigo in pendentes_unicos if codigo not in disciplinas_resolvidas]
    
    return df_consolidado, pendentes_reais

# --- Execução Principal ---
caminho_arquivo = "src/data/Dataset_-_Cenrio_1_-_Recomendao_Matrcula/historico_CCO-2.pdf"
df_historico, lista_pendentes = extrair_dados_completos_sigaa(caminho_arquivo)

print("Tabela Consolidada para Alimentação do Grafo (Pesos P3):")
print(df_historico.head(10).to_string(index=False))
print("...\n")

print(f"Total de Disciplinas Obrigatórias Pendentes Encontradas: {len(lista_pendentes)}")
print("Lista de Pendentes (Pesos P2):")
print(lista_pendentes)