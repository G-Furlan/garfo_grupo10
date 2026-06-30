# Sistema de Recomendação de Matrícula

Projeto desenvolvido para a disciplina **CMAC03 - Algoritmos em Grafos**, da Universidade Federal de Itajubá (UNIFEI).

O sistema auxilia estudantes dos cursos de **Ciência da Computação** e **Sistemas de Informação** na escolha de disciplinas para matrícula, a partir da análise automatizada do histórico acadêmico emitido pelo SIGAA.

## Integrantes

- Gabriel Antonio Furlan
- Gustavo Taets e Sales
- Laura Carolini de Souza Saia
- Matheus Alcântara Pereira
- Natan Pereira Miranda

## Objetivo

O objetivo do projeto é recomendar uma grade de disciplinas para o próximo semestre letivo, considerando:

- disciplinas obrigatórias ainda pendentes;
- pré-requisitos já cumpridos;
- período ideal da disciplina na matriz curricular;
- reprovações anteriores;
- sazonalidade de oferta;
- carga horária máxima recomendada;
- conflitos de horário, quando as informações de horário estiverem disponíveis;
- disponibilidade de espaço para optativas.

## Modelagem do problema

A matriz curricular é representada como um **grafo direcionado acíclico** (*Directed Acyclic Graph* - DAG).

- Cada vértice representa uma disciplina.
- Cada aresta direcionada representa uma relação de pré-requisito.
- Uma aresta `u -> v` indica que a disciplina `u` é pré-requisito para a disciplina `v`.
- O grafo processado contém principalmente as disciplinas obrigatórias pendentes do aluno.

A partir desse grafo, o sistema calcula uma pontuação de prioridade para cada disciplina pendente.

## Critérios de prioridade

Cada disciplina recebe um peso total `W`, calculado a partir dos seguintes fatores:

| Fator | Descrição |
|---|---|
| `P1` | Caminho crítico: mede quantas disciplinas futuras dependem da disciplina atual. |
| `P2` | Obrigatoriedade: bônus fixo para disciplinas obrigatórias. |
| `P3` | Retenção: bônus proporcional ao número de reprovações anteriores. |
| `P4` | Sazonalidade: bônus para disciplinas ofertadas apenas uma vez por ano. |
| `P5` | Atraso: bônus conforme a diferença entre o período atual do aluno e o período ideal da disciplina. |

O peso final é dado por:

```text
W = P1 + P2 + P3 + P4 + P5
```

## Estratégia de recomendação

O sistema executa as seguintes etapas:

1. Recebe um histórico acadêmico em PDF.
2. Extrai as disciplinas cursadas, pendentes, reprovações, equivalências e dados de ingresso.
3. Identifica o curso do aluno.
4. Carrega a matriz curricular correspondente.
5. Constrói o grafo de disciplinas obrigatórias pendentes.
6. Calcula os pesos das disciplinas.
7. Filtra disciplinas disponíveis de acordo com os pré-requisitos.
8. Considera a oferta do semestre selecionado.
9. Monta a recomendação de matrícula respeitando carga horária e, quando disponível, conflitos de horário.
10. Exibe a recomendação em uma interface web com grafo interativo.

Quando a carga horária restante não é suficiente para outra disciplina obrigatória, ou quando não há mais obrigatórias viáveis, o sistema sinaliza vagas remanescentes para optativas.

## Estrutura do repositório

```text
garfo_grupo10/
├── interface/
│   ├── backend/
│   │   ├── server.js
│   │   └── package.json
│   └── frontend/
│       ├── index.html
│       ├── sistema.html
│       ├── resultados.html
│       └── styles*.css
├── software/
│   └── src/
│       ├── parser_historico.py
│       ├── grafo_pendentes.py
│       ├── grafo_pesos.py
│       ├── recomendar_semestre.py
│       ├── exportar_grafo.py
│       └── data/
│           ├── materiasCCO.json
│           ├── materiasSIN.json
│           ├── equivalencias.json
│           └── Dataset-Cenario1-RecomendacaoMatricula/
└── README.md
```

## Principais módulos

| Arquivo | Função |
|---|---|
| `parser_historico.py` | Extrai dados do histórico acadêmico em PDF. |
| `grafo_pendentes.py` | Constrói o grafo de dependências das disciplinas pendentes. |
| `grafo_pesos.py` | Calcula os pesos `P1` a `P5` e o peso total `W`. |
| `recomendar_semestre.py` | Seleciona as disciplinas recomendadas para o semestre. |
| `exportar_grafo.py` | Orquestra o pipeline e exporta o grafo em JSON para o frontend. |
| `server.js` | Backend Express responsável pelo upload do histórico e execução do pipeline Python. |
| `resultados.html` | Interface de visualização do grafo e das recomendações. |

## Requisitos

### Backend web

- Node.js 18 ou superior
- npm

### Pipeline Python

- Python 3.10 ou superior
- `pandas`
- `pdfplumber`

## Instalação

Clone o repositório:

```bash
git clone https://github.com/G-Furlan/garfo_grupo10.git
cd garfo_grupo10
```

### 1. Configurar o ambiente Python

Acesse o diretório `software`:

```bash
cd software
```

Crie e ative um ambiente virtual:

#### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

Instale as dependências Python:

```bash
pip install pandas pdfplumber
```

Volte para a raiz do projeto:

```bash
cd ..
```

### 2. Configurar o backend

Acesse o diretório do backend:

```bash
cd interface/backend
npm install
```

Execute o servidor:

```bash
node server.js
```

Se o `package.json` já possuir o script `start`, também é possível executar:

```bash
npm start
```

Por padrão, o servidor é iniciado em:

```text
http://localhost:3000
```

## Como usar

1. Inicie o backend.
2. Acesse `http://localhost:3000` no navegador.
3. Envie um histórico acadêmico em PDF emitido pelo SIGAA.
4. Aguarde o processamento.
5. Visualize o grafo de disciplinas pendentes.
6. Consulte a recomendação de matrícula para o semestre selecionado.
7. Verifique os pesos, a disponibilidade das disciplinas, possíveis conflitos de horário e vagas remanescentes para optativas.

## Entrada do sistema

O sistema recebe como entrada principal um histórico acadêmico em PDF. A extração considera, quando disponíveis:

- curso do aluno;
- período letivo inicial;
- disciplinas cursadas;
- disciplinas em matrícula;
- disciplinas pendentes;
- reprovações;
- equivalências;
- suspensões;
- média histórica de aprovações por semestre.

Disciplinas em situação de matrícula atual são tratadas como já alocadas no planejamento do estudante, para evitar que sejam recomendadas novamente.

## Saída do sistema

A saída principal é uma recomendação de matrícula composta por:

- disciplinas obrigatórias recomendadas;
- carga horária total recomendada;
- peso total da recomendação;
- disciplinas disponíveis que ficaram de fora;
- indicação de vagas livres para optativas;
- visualização do grafo de pendências;
- detalhamento dos pesos de cada disciplina;
- sinalização de horários e conflitos, quando essas informações estiverem cadastradas.

## Observações de escopo

Nesta versão, o sistema prioriza a recomendação de disciplinas obrigatórias. As optativas são tratadas como vagas remanescentes e listadas separadamente quando o aluno possui espaço de carga horária.

O sistema não substitui a análise final do discente ou da coordenação do curso. A recomendação deve ser interpretada como apoio ao planejamento acadêmico.

## Limitações conhecidas

- A qualidade da recomendação depende da consistência do histórico acadêmico em PDF.
- A extração de dados pode variar conforme alterações no formato do histórico do SIGAA.
- A matriz curricular precisa estar corretamente cadastrada nos arquivos JSON.
- Informações de horário só são consideradas quando estão presentes na base de dados.
- A recomendação de optativas ainda não é otimizada com o mesmo nível de detalhe das disciplinas obrigatórias.

## Trabalhos futuros

- Gerar um plano completo até a formatura.
- Otimizar a escolha de optativas.
- Controlar automaticamente a carga horária total de optativas já cumpridas.
- Permitir restrições personalizadas de disponibilidade do aluno.
- Criar testes automatizados para parser, construção do grafo e recomendação.

## Licença

Projeto acadêmico desenvolvido para fins educacionais na disciplina CMAC03 - Algoritmos em Grafos.












Como executar:

cd interface/backend
    npm install
    npm start


Para desenvolvimento:
    npm run dev
