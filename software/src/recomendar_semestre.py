# -*- coding: utf-8 -*-
"""
PARTE 3 (passo 1) do pipeline de recomendação de matrícula.

Recebe o grafo ponderado da PARTE 2 e escolhe a melhor grade do PRÓXIMO semestre
resolvendo uma MOCHILA 0/1 (knapsack):

    valor    = W (peso de prioridade da disciplina)
    peso     = carga horária (h)
    capacidade = max_horas (limite de carga horária do semestre)

Maximiza a soma de W das disciplinas escolhidas sem estourar max_horas, considerando
apenas as disciplinas disponíveis (pré-requisitos satisfeitos). Opcionalmente filtra
também pelas que são ofertadas no semestre-alvo.

O passo 2 (BFS multi-semestre) vai reaproveitar `recomendar_semestre` em ondas.
"""


def _ch_int(ch):
    """Carga horária como inteiro (o nó já guarda int, mas aceita '64h' por segurança)."""
    if isinstance(ch, int):
        return ch
    try:
        return int(str(ch).replace('h', '').strip())
    except (ValueError, AttributeError):
        return 64


def _ofertada_em(node, semestre):
    """
    True se a disciplina é ofertada no semestre-alvo (1=ímpar, 2=par).
    periodo_ofertado vazio ou '2026-1 / 2026-2' (ambos) → considera ofertada.
    """
    po = node.get('periodo_ofertado', '')
    if not po or '/' in po:
        return True
    try:
        return int(po.split('-')[1][0]) == semestre
    except (IndexError, ValueError):
        return True


def _knapsack(itens, capacidade):
    """
    Mochila 0/1 por programação dinâmica.
    itens: lista de (codigo, valor, peso). Retorna o conjunto de códigos escolhidos
    que maximiza a soma de valor com soma de peso <= capacidade.
    """
    n = len(itens)
    if n == 0 or capacidade <= 0:
        return set()

    # dp[i][c] = melhor valor usando os primeiros i itens com capacidade c
    dp = [[0] * (capacidade + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        _, valor, peso = itens[i - 1]
        for c in range(capacidade + 1):
            dp[i][c] = dp[i - 1][c]
            if peso <= c:
                incluir = dp[i - 1][c - peso] + valor
                if incluir > dp[i][c]:
                    dp[i][c] = incluir

    # Reconstrói quais itens entraram
    escolhidos = set()
    c = capacidade
    for i in range(n, 0, -1):
        if dp[i][c] != dp[i - 1][c]:
            cod, _, peso = itens[i - 1]
            escolhidos.add(cod)
            c -= peso
    return escolhidos


def recomendar_semestre(grafo, max_horas, semestre_alvo=None):
    """
    Escolhe a grade recomendada do próximo semestre.

    Parâmetros:
        grafo         : grafo ponderado (saída da parte 2), com W/ch/disponivel por nó
        max_horas     : limite de carga horária do semestre
        semestre_alvo : 1 ou 2 para recomendar só o que é ofertado nesse semestre;
                        None (default) considera todas as disponíveis

    Efeito: marca cada nó com 'recomendada' (bool).
    Retorno: dict com recomendadas, em_espera, total_w, total_horas, max_horas.
    """
    candidatos = []
    for cod, d in grafo['nos'].items():
        if not d.get('disponivel'):
            continue
        if semestre_alvo is not None and not _ofertada_em(d, semestre_alvo):
            continue
        candidatos.append((cod, d['W'], _ch_int(d['ch'])))

    # Ordena (maior W primeiro) só para tornar a reconstrução determinística
    candidatos.sort(key=lambda x: (-x[1], x[0]))
    escolhidos = _knapsack(candidatos, max_horas)

    for cod, d in grafo['nos'].items():
        d['recomendada'] = cod in escolhidos

    recomendadas = sorted(escolhidos, key=lambda c: -grafo['nos'][c]['W'])
    em_espera = sorted((c for c, _, _ in candidatos if c not in escolhidos),
                       key=lambda c: -grafo['nos'][c]['W'])
    total_w = sum(grafo['nos'][c]['W'] for c in escolhidos)
    total_horas = sum(_ch_int(grafo['nos'][c]['ch']) for c in escolhidos)

    return {
        'recomendadas': recomendadas,
        'em_espera': em_espera,
        'total_w': total_w,
        'total_horas': total_horas,
        'max_horas': max_horas,
    }


def imprimir_recomendacao(grafo, resultado):
    nos = grafo['nos']
    print(f"\n{'='*78}")
    print(f"RECOMENDAÇÃO DO PRÓXIMO SEMESTRE  "
          f"({resultado['total_horas']}h / {resultado['max_horas']}h · "
          f"W total {resultado['total_w']})")
    print(f"{'='*78}")
    print(f"{'':2}{'CÓDIGO':<10} | {'W':<4} | {'CH':<4} | NOME")
    print("-" * 78)
    for c in resultado['recomendadas']:
        d = nos[c]
        print(f"✓ {c:<10} | {d['W']:<4} | {_ch_int(d['ch']):<4} | {d['nome']}")
    if resultado['em_espera']:
        print(f"{'-'*78}\nDisponíveis que ficaram de fora (orçamento cheio):")
        for c in resultado['em_espera']:
            d = nos[c]
            print(f"  {c:<10} | {d['W']:<4} | {_ch_int(d['ch']):<4} | {d['nome']}")
    print("-" * 78)