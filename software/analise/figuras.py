import json, glob
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                     'figure.dpi':150,'savefig.dpi':300,'savefig.bbox':'tight','font.family':'DejaVu Sans'})
ROXO='#6a1b9a'; OURO='#e09f00'; VERDE='#2e8b57'; CINZA='#9aa0a6'; AZUL='#2c6fbb'; VERM='#c0392b'

def ofertada(po, sem):
    if not po or '/' in po: return True
    try: return int(po.split('-')[1][0]) == sem
    except: return True

dados={}
for a in sorted(glob.glob('resultado_*.json')):
    d=json.load(open(a,encoding='utf-8'))
    nome=a.replace('resultado_historico_','').replace('.json','')
    dados[nome]=d
nomes=sorted(dados, key=lambda x:(x[:3],int(x.split('-')[1])))

# ---------- FIG 1: funil pendentes -> disponíveis -> recomendadas ----------
pend=[dados[n]['meta']['total'] for n in nomes]
disp=[dados[n]['meta']['disponiveis'] for n in nomes]
rec=[max(len(dados[n]['meta']['recomendacao']['1']['codigos']),
         len(dados[n]['meta']['recomendacao']['2']['codigos'])) for n in nomes]
import numpy as np
x=np.arange(len(nomes)); w=0.27
fig,ax=plt.subplots(figsize=(9,4.2))
ax.bar(x-w, pend, w, label='Obrigatórias pendentes', color=CINZA)
ax.bar(x,   disp, w, label='Disponíveis (pré-req. ok)', color=AZUL)
ax.bar(x+w, rec,  w, label='Recomendadas (melhor semestre)', color=ROXO)
ax.set_xticks(x); ax.set_xticklabels(nomes, rotation=45, ha='right')
ax.set_ylabel('Nº de disciplinas'); ax.legend(frameon=False, fontsize=9.5)
ax.set_title('Funil de seleção: pendentes → disponíveis → recomendadas', fontsize=12)
plt.savefig('fig1_funil.png'); plt.close()

# ---------- FIG 2: composição do peso W (P1..P5) ----------
P={'P1':0,'P2':0,'P3':0,'P4':0,'P5':0}; Wt=0
for n in nomes:
    nos={c['data']['codigo']:c['data'] for c in dados[n]['elements']['nodes']}
    for sem in ('1','2'):
        for c in dados[n]['meta']['recomendacao'][sem]['codigos']:
            for p in P: P[p]+=nos[c][p]
            Wt+=nos[c]['W']
labels=['P1 caminho\ncrítico','P2 obriga-\ntoriedade','P3 retenção','P4 sazona-\nlidade','P5 atraso']
vals=[P['P1'],P['P2'],P['P3'],P['P4'],P['P5']]
pct=[100*v/Wt for v in vals]
cores=[AZUL,ROXO,VERM,VERDE,OURO]
fig,ax=plt.subplots(figsize=(7.5,4.2))
bars=ax.bar(labels, vals, color=cores)
for b,v,p in zip(bars,vals,pct):
    ax.text(b.get_x()+b.get_width()/2, v+4, f'{p:.0f}%', ha='center', fontsize=10, fontweight='bold')
ax.set_ylabel('Contribuição somada ao W'); ax.set_ylim(0,max(vals)*1.18)
ax.set_title('Composição do peso W das disciplinas recomendadas', fontsize=12)
plt.savefig('fig2_composicao_peso.png'); plt.close()

# ---------- FIG 3: orçamento personalizado (média -> nº recomendado) ----------
media=[dados[n]['meta']['media_aprovacoes'] for n in nomes]
fig,ax=plt.subplots(figsize=(7.2,4.4))
for n,mi,ri in zip(nomes,media,rec):
    cor = ROXO if n.startswith('CCO') else OURO
    ax.scatter(mi,ri,color=cor,s=70,zorder=3,edgecolor='white',linewidth=0.8)
    ax.annotate(n, (mi,ri), textcoords='offset points', xytext=(6,4), fontsize=8, color='#555')
# linha do orçamento teórico = round(media) (limitado a piso 4 só quando media<1; aqui não aplica)
import numpy as np
mm=np.linspace(min(media)-0.3,max(media)+0.3,100)
ax.plot(mm,[round(v) for v in mm],'--',color=CINZA,zorder=1,label='Orçamento = round(média) matérias')
ax.set_xlabel('Média de aprovações por semestre (histórico do aluno)')
ax.set_ylabel('Nº de disciplinas recomendadas')
from matplotlib.lines import Line2D
leg=[Line2D([0],[0],marker='o',color='w',markerfacecolor=ROXO,markersize=9,label='CCO'),
     Line2D([0],[0],marker='o',color='w',markerfacecolor=OURO,markersize=9,label='SIN'),
     Line2D([0],[0],linestyle='--',color=CINZA,label='Orçamento = round(média)')]
ax.legend(handles=leg, frameon=False, fontsize=9.5, loc='upper left')
ax.set_title('Personalização do orçamento pela média de aprovações', fontsize=12)
ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
plt.savefig('fig3_orcamento.png'); plt.close()

# ---------- FIG 4: knapsack vs guloso (caso controlado heterogêneo) ----------
# Orçamento 64h: A(W20,64h) vs B(W12,32h)+C(W12,32h)
fig,ax=plt.subplots(figsize=(5.6,4.0))
metodos=['Guloso\n(por peso)','Knapsack\n(ótimo)']
ww=[20,24]; cores2=[CINZA,ROXO]
bars=ax.bar(metodos, ww, color=cores2, width=0.55)
for b,v,txt in zip(bars,ww,['Escolhe A (W=20)\ne para','Escolhe B+C\n(W=24)']):
    ax.text(b.get_x()+b.get_width()/2, v+0.4, str(v), ha='center', fontweight='bold')
    ax.text(b.get_x()+b.get_width()/2, v/2, txt, ha='center', color='white', fontsize=9)
ax.set_ylabel('Peso total da grade (W)'); ax.set_ylim(0,28)
ax.set_title('Knapsack × guloso — orçamento 64h\nA(W20,64h)  vs  B(W12,32h)+C(W12,32h)', fontsize=11)
plt.savefig('fig4_knapsack_vs_guloso.png'); plt.close()
print("Figuras geradas:", glob.glob('fig*.png'))