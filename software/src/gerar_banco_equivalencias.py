import pandas as pd
import json

def extrair_codigos(texto):
    """Limpa a célula e separa disciplinas caso haja um '+' (Ex: ECOS02A + ECOS12A)"""
    if pd.isna(texto) or str(texto).strip() == '--':
        return []
    
    codigos = [c.strip() for c in str(texto).split('+')]
    return [c for c in codigos if len(c) >= 4]

def processar_aba_equivalencia(caminho_excel, nome_da_aba, skiprows):
    # Mudança crucial: read_excel no lugar de read_csv
    df = pd.read_excel(caminho_excel, sheet_name=nome_da_aba, skiprows=skiprows)
    grupos_equivalencia = []

    for index, row in df.iterrows():
        # Verifica se a coluna CÓDIGO existe na linha atual
        if 'CÓDIGO' not in df.columns or pd.isna(row.get('CÓDIGO')):
            continue

        grupo = set()
        # Adiciona o código principal da grade 2022
        grupo.update(extrair_codigos(row['CÓDIGO']))

        # Itera sobre as demais colunas de grades antigas/outros cursos
        colunas_ignorar = ['PERÍODO', 'CÓDIGO', 'DISCIPLINA', 'CH']
        for col in df.columns:
            if col not in colunas_ignorar:
                grupo.update(extrair_codigos(row[col]))

        if len(grupo) > 1:
            grupos_equivalencia.append(list(grupo))

    return grupos_equivalencia

# --- Execução Principal ---
# Caminho único para a planilha Excel que o professor enviou
caminho_planilha = "src/data/Dataset_-_Cenrio_1_-_Recomendao_Matrcula/XMCO03 - CCO e SIN - Disciplinas Equivalentes e Pré-Requisitos Grades 2013 e 2022.xlsx"

# Lê as duas abas do mesmo arquivo. 
# (As linhas a pular 'skiprows' são diferentes em cada aba devido ao cabeçalho da UNIFEI)
grupos_cco = processar_aba_equivalencia(caminho_planilha, nome_da_aba="CCO - Equivalências 2022 v2", skiprows=8)
grupos_sin = processar_aba_equivalencia(caminho_planilha, nome_da_aba="SIN - Equivalências 2022 v2", skiprows=9)

mapa_equivalencias = {}
todos_grupos = grupos_sin + grupos_cco

# Constrói o dicionário de equivalências mútuas
for grupo in todos_grupos:
    for codigo in grupo:
        if codigo not in mapa_equivalencias:
            mapa_equivalencias[codigo] = set()
        for outro_codigo in grupo:
            if codigo != outro_codigo:
                mapa_equivalencias[codigo].add(outro_codigo)

# Converte Sets para Lists para poder salvar em JSON
for k in mapa_equivalencias:
    mapa_equivalencias[k] = list(mapa_equivalencias[k])

# Salva o arquivo JSON
caminho_saida_json = 'src/data/equivalencias.json'
with open(caminho_saida_json, 'w', encoding='utf-8') as f:
    json.dump(mapa_equivalencias, f, indent=4, ensure_ascii=False)

print(f"Banco de equivalências gerado com sucesso em: {caminho_saida_json}")