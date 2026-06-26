import pdfplumber

caminho_pdf = "src/data/Dataset_-_Cenrio_1_-_Recomendao_Matrcula/historico_CCO-1.pdf"

with pdfplumber.open(caminho_pdf) as pdf:
    pagina = pdf.pages[0] # Analisaremos apenas a primeira página
    tabelas = pagina.extract_tables()
    
    if tabelas:
        print("Tabela estruturada detectada. Exibindo as primeiras linhas:")
        for i, linha in enumerate(tabelas[0][:15]): # Limite de 15 linhas
            print(f"[{i}] {linha}")
    else:
        print("Aviso: Nenhuma tabela em formato de grade foi detectada.")