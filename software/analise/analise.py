import json, glob, statistics as st

def ofertada(po, sem):
    if not po or '/' in po: return True
    try: return int(po.split('-')[1][0]) == sem
    except: return True

def knapsack(items, cap):  # items: (cod,W,ch) -> (set, W)
    n=len(items)
    if n==0 or cap<=0: return set(),0
    dp=[[0]*(cap+1) for _ in range(n+1)]
    for i in range(1,n+1):
        _,v,w=items[i-1]
        for c in range(cap+1):
            dp[i][c]=dp[i-1][c]
            if w<=c: dp[i][c]=max(dp[i][c],dp[i-1][c-w]+v)
    sel=set(); c=cap
    for i in range(n,0,-1):
        if dp[i][c]!=dp[i-1][c]:
            cod,v,w=items[i-1]; sel.add(cod); c-=w
    return sel, dp[n][cap]

def greedy_W(items, cap):  # ordena por W desc, pega se cabe
    tot=0; h=0; sel=set()
    for cod,v,w in sorted(items, key=lambda x:(-x[1],-x[1]/x[2])):
        if h+w<=cap: sel.add(cod); h+=w; tot+=v
    return sel, tot

def greedy_ratio(items, cap):
    tot=0; h=0; sel=set()
    for cod,v,w in sorted(items, key=lambda x:-x[1]/x[2]):
        if h+w<=cap: sel.add(cod); h+=w; tot+=v
    return sel, tot

arqs=sorted(glob.glob('resultado_*.json'))
linhas=[]
wins_knap_vs_gw=0; wins_knap_vs_gr=0; total_cmp=0
disp_total=disp_aval=0
P_acc={'P1':0,'P2':0,'P3':0,'P4':0,'P5':0}; W_acc=0; n_rec=0
slot_sems=0; total_sems=0
for a in arqs:
    d=json.load(open(a,encoding='utf-8'))
    nos={n['data']['codigo']:n['data'] for n in d['elements']['nodes']}
    m=d['meta']; cap=m['max_horas']
    for sem in (1,2):
        total_sems+=1
        cand=[(c,x['W'],x['ch']) for c,x in nos.items() if x['disponivel'] and ofertada(x['periodo_ofertado'],sem)]
        ks,kw=knapsack(cand,cap); gws,gw=greedy_W(cand,cap); grs,gr=greedy_ratio(cand,cap)
        jrec=set(m['recomendacao'][str(sem)]['codigos']); jw=m['recomendacao'][str(sem)]['w']
        ok = (kw==jw)  # knapsack reproduz a recomendação do JSON (valor)
        total_cmp+=1
        if kw>gw: wins_knap_vs_gw+=1
        if kw>gr: wins_knap_vs_gr+=1
        if m['recomendacao'][str(sem)]['slots_optativa']>0: slot_sems+=1
        # composição de pesos das recomendadas (do JSON)
        for c in jrec:
            for p in P_acc: P_acc[p]+=nos[c][p]
            W_acc+=nos[c]['W']; n_rec+=1
        linhas.append((a.replace('resultado_historico_','').replace('.json',''),sem,len(cand),kw,gw,gr,jw,ok,
                       m['recomendacao'][str(sem)]['slots_optativa']))
    disp_total+=m['total']; disp_aval+=m['disponiveis']

print("=== VERIFICAÇÃO: knapsack reproduz recomendação do JSON? ===")
print("Todos OK:", all(l[7] for l in linhas), f"({sum(l[7] for l in linhas)}/{len(linhas)} cenários)")
print()
print("=== KNAPSACK vs GULOSO (W) — por cenário (aluno, semestre) ===")
print(f"{'aluno':10} sem  #cand  W_knap  W_gulosoW  W_gulosoRatio  slots")
for l in linhas:
    flag = '  <-- knap>guloso' if (l[3]>l[4] or l[3]>l[5]) else ''
    print(f"{l[0]:10} {l[1]}    {l[2]:>4}   {l[3]:>5}   {l[4]:>7}    {l[5]:>9}     {l[8]}{flag}")
print()
print(f"Cenários onde knapsack > guloso-por-W:      {wins_knap_vs_gw}/{total_cmp}")
print(f"Cenários onde knapsack > guloso-por-razão:   {wins_knap_vs_gr}/{total_cmp}")
print(f"Semestres com vaga de optativa sobrando:     {slot_sems}/{total_sems}")
print()
print("=== DISPONIBILIDADE ===")
print(f"Pendentes obrig (soma): {disp_total} | disponíveis por pré-req (soma): {disp_aval} "
      f"({100*disp_aval/disp_total:.0f}%)")
print()
print("=== COMPOSIÇÃO DOS PESOS (média da contribuição entre as recomendadas) ===")
for p in ['P1','P2','P3','P4','P5']:
    print(f"  {p}: soma {P_acc[p]:>4}  | média/disciplina {P_acc[p]/n_rec:.2f}  | % do W {100*P_acc[p]/W_acc:.0f}%")
print(f"  W total das recomendadas: {W_acc} em {n_rec} recomendações")