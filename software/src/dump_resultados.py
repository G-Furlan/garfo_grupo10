# -*- coding: utf-8 -*-
"""
Roda o pipeline completo em TODOS os históricos do dataset e salva:
  - resultado_<arquivo>.json  : a saída completa (grafo + meta) de cada aluno
  - resumo.csv                : uma linha por aluno com os números-chave

Uso (a partir da pasta software/):
    python src/dump_resultados.py
ou apontando outra pasta de PDFs:
    python src/dump_resultados.py caminho/para/pasta_de_pdfs
"""
import os
import sys
import json
import glob
import csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exportar_grafo import gerar, RAIZ  # noqa: E402

PASTA_PADRAO = os.path.join(RAIZ, 'src', 'data', 'Dataset_-_Cenrio_1_-_Recomendao_Matrcula')
PASTA_SAIDA = os.path.join(RAIZ, 'resultados_rodada')


def resumo_de(meta, arquivo):
    r1 = meta['recomendacao']['1']
    r2 = meta['recomendacao']['2']
    return {
        'arquivo': arquivo,
        'curso': meta.get('curso'),
        'periodo_atual': meta.get('periodo_atual'),
        'pendentes_obrig': meta.get('total'),
        'disponiveis_prereq': meta.get('disponiveis'),
        'media_aprovacoes': meta.get('media_aprovacoes'),
        'orcamento_horas': meta.get('max_horas'),
        'orcamento_materias': meta.get('orcamento_materias'),
        'rec2026_1_qtd': len(r1['codigos']),
        'rec2026_1_horas': r1['horas'],
        'rec2026_1_w': r1['w'],
        'rec2026_1_vagas_opt': r1['slots_optativa'],
        'rec2026_2_qtd': len(r2['codigos']),
        'rec2026_2_horas': r2['horas'],
        'rec2026_2_w': r2['w'],
        'rec2026_2_vagas_opt': r2['slots_optativa'],
        'optativas_catalogo': len(meta.get('lista_optativas', [])),
    }


def main():
    pasta = sys.argv[1] if len(sys.argv) > 1 else PASTA_PADRAO
    pdfs = sorted(glob.glob(os.path.join(pasta, '*.pdf')))
    if not pdfs:
        print(f'Nenhum PDF encontrado em: {pasta}')
        return

    os.makedirs(PASTA_SAIDA, exist_ok=True)
    resumos = []
    print(f'Processando {len(pdfs)} histórico(s)...\n')

    for pdf in pdfs:
        nome = os.path.splitext(os.path.basename(pdf))[0]
        try:
            grafo = gerar(pdf)
            meta = grafo['meta']
            with open(os.path.join(PASTA_SAIDA, f'resultado_{nome}.json'), 'w', encoding='utf-8') as f:
                json.dump(grafo, f, ensure_ascii=False, indent=2)
            resumos.append(resumo_de(meta, nome))
            r1, r2 = meta['recomendacao']['1'], meta['recomendacao']['2']
            print(f'  OK  {nome}: {meta.get("curso")} · período {meta.get("periodo_atual")} · '
                  f'{meta.get("total")} obrig pendentes | '
                  f'2026.1 = {len(r1["codigos"])} obrig + {r1["slots_optativa"]} vaga · '
                  f'2026.2 = {len(r2["codigos"])} obrig + {r2["slots_optativa"]} vaga')
        except Exception as e:
            print(f'  ERRO {nome}: {e}')

    if resumos:
        caminho_csv = os.path.join(PASTA_SAIDA, 'resumo.csv')
        with open(caminho_csv, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(resumos[0].keys()))
            w.writeheader()
            w.writerows(resumos)
        print(f'\n{len(resumos)} histórico(s) processado(s).')
        print(f'JSONs e resumo.csv salvos em: {PASTA_SAIDA}')


if __name__ == '__main__':
    main()