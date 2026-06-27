import pdfplumber
import json
import re
import os

def processar_ppc(caminho_pdf, nome_curso):
    # Estrutura do Banco de Dados NoSQL
    grade = {
        "curso": nome_curso,
        "obrigatorias": {},
        "optativas": {},
        "trilhas": {
            "Desenvolvimento de Sistemas": [],
            "Persistência e Análise de Dados": [],
            "Redes e Sistemas Computacionais": [],
            "Ciência, Tecnologia e Inovação": [],
            "Resolução de Problemas": []
        }
    }
    
    # Regex para o formato de disciplinas da UNIFEI
    padrao_codigo = r'\b[A-Z]{3,4}[0-9]{2}[0-9A-Z]?\b'
    
    with pdfplumber.open(caminho_pdf) as pdf:
        for page in pdf.pages:
            texto = page.extract_text() or ""
            
            # 1. CAPTURA DAS TRILHAS DE FORMAÇÃO
            trilha_contexto = None
            for linha in texto.split('\n'):
                linha_up = linha.upper()
                # Identifica a trilha atual pelo texto do parágrafo
                if "PERSISTÊNCIA E ANÁLISE DE DADOS" in linha_up:
                    trilha_contexto = "Persistência e Análise de Dados"
                elif "REDES E SISTEMAS COMPUTACIONAIS" in linha_up:
                    trilha_contexto = "Redes e Sistemas Computacionais"
                elif "DESENVOLVIMENTO DE SISTEMAS" in linha_up or "ENGENHARIA DE SOFTWARE" in linha_up:
                    trilha_contexto = "Desenvolvimento de Sistemas"
                elif "CIÊNCIA, TECNOLOGIA E INOVAÇÃO" in linha_up:
                    trilha_contexto = "Ciência, Tecnologia e Inovação"
                elif "RESOLUÇÃO DE PROBLEMAS" in linha_up:
                    trilha_contexto = "Resolução de Problemas"
                
                # Captura os códigos que aparecem listados nas trilhas
                if trilha_contexto and ("Optativa" in linha or "Figura" in linha):
                    codigos = re.findall(padrao_codigo, linha)
                    for c in codigos:
                        if c not in grade["trilhas"][trilha_contexto]:
                            grade["trilhas"][trilha_contexto].append(c)

            # 2. CAPTURA DAS DISCIPLINAS (Tabelas 4.2 e 4.3)
            tabelas = page.extract_tables()
            for tabela in tabelas:
                for linha in tabela:
                    if not linha: continue
                    
                    # Achata a linha em uma string única para driblar as células mescladas
                    linha_str = " | ".join([str(celula) for celula in linha if celula])
                    
                    codigos = re.findall(padrao_codigo, linha_str)
                    if not codigos or "CÓDIGO" in linha_str.upper():
                        continue
                        
                    codigo_principal = codigos[0]
                    # Tudo que for código após o primeiro é pré-requisito
                    pre_requisitos = list(set([c for c in codigos[1:] if c != codigo_principal]))
                    
                    # Captura a Carga Horária (32, 48 ou 64)
                    chs = re.findall(r'\b(32|48|64)\b', linha_str)
                    ch = int(chs[0]) if chs else 64
                    
                    # Captura o Período. Optativas costumam ter vírgula/ponto "5,7" ou "6.8" no PDF
                    periodos_multiplos = re.search(r'\b[1-9]\s*[,.]\s*[1-9]\b', linha_str)
                    periodos_isolados = re.findall(r'\b[1-9]\b', linha_str)
                    
                    is_optativa = bool(periodos_multiplos) or "Optativa" in texto
                    
                    periodo_ideal = 0
                    if periodos_isolados:
                        periodo_ideal = int(periodos_isolados[0])

                    disciplina_obj = {
                        "codigo": codigo_principal,
                        "periodo_ideal": periodo_ideal,
                        "ch": ch,
                        "pre_requisitos": pre_requisitos
                    }
                    
                    # Separação lógica entre Obrigatórias e Optativas
                    if is_optativa and periodo_ideal >= 5:
                        grade["optativas"][codigo_principal] = disciplina_obj
                    else:
                        grade["obrigatorias"][codigo_principal] = disciplina_obj
    
    # Remove trilhas vazias
    grade["trilhas"] = {k: v for k, v in grade["trilhas"].items() if v}
    return grade

# --- Execução Principal ---
# Ajuste os nomes dos arquivos conforme baixados no seu repositório
caminho_cco = "src/data/ProjetoPedagogicoCCO_atualizadoJan2025.pdf"
caminho_sin = "src/data/projetoPedagogicoSIN_Itajuba-Maio2024_1.pdf"

# Gera e salva a matriz curricular de CCO
if os.path.exists(caminho_cco):
    grade_cco = processar_ppc(caminho_cco, "CCO")
    with open('src/data/grade_cco.json', 'w', encoding='utf-8') as f:
        json.dump(grade_cco, f, indent=4, ensure_ascii=False)
    print("Grade de CCO gerada com sucesso!")

# Gera e salva a matriz curricular de SIN
if os.path.exists(caminho_sin):
    grade_sin = processar_ppc(caminho_sin, "SIN")
    with open('src/data/grade_sin.json', 'w', encoding='utf-8') as f:
        json.dump(grade_sin, f, indent=4, ensure_ascii=False)
    print("Grade de SIN gerada com sucesso!")