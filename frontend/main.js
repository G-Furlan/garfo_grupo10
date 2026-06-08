// Estado global da aplicação
let perfis = JSON.parse(localStorage.getItem('perfis_organizador')) || [];
let historicoTemporario = [];
let perfilSelecionadoIndex = null;

// Referências do DOM
const perfilForm = document.getElementById('perfil-form');
const perfisTbody = document.getElementById('perfis-tbody');
const listaHistoricoPreview = document.getElementById('lista-historico-preview');

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    renderizarTabelaPerfis();
});

// Controlar troca de abas
function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    if(tabName === 'crud') {
        document.querySelector("button[onclick*='crud']").classList.add('active');
        document.getElementById('tab-crud').classList.add('active');
    } else {
        document.querySelector("button[onclick*='ranking']").classList.add('active');
        document.getElementById('tab-ranking').classList.add('active');
    }
}

// Adiciona uma matéria na lista temporária antes de salvar o perfil
function addMateriaAoHistorico() {
    const codigo = document.getElementById('mat-codigo').value.toUpperCase().trim();
    const nota = parseFloat(document.getElementById('mat-nota').value);
    const situacao = document.getElementById('mat-situacao').value;

    if (!codigo) {
        alert('Digite o código da matéria!');
        return;
    }

    historicoTemporario.push({ codigo, nota: nota || 0, situacao });
    
    // Limpa inputs
    document.getElementById('mat-codigo').value = '';
    document.getElementById('mat-nota').value = '';
    
    atualizarPreviewHistorico();
}

function atualizarPreviewHistorico() {
    listaHistoricoPreview.innerHTML = historicoTemporario.map((mat, index) => `
        <li>${mat.codigo} - Nota: ${mat.nota} (${mat.situacao}) 
            <button type="button" style="color:red; border:none; background:none; cursor:pointer;" onclick="removerMateriaPreview(${index})">❌</button>
        </li>
    `).join('');
}

function removerMateriaPreview(index) {
    historicoTemporario.splice(index, 1);
    atualizarPreviewHistorico();
}

// Submissão do Formulário (Create e Update)
perfilForm.addEventListener('submit', (e) => {
    e.preventDefault();
    
    const id = document.getElementById('perfil-id').value;
    const perfilDados = {
        matricula: document.getElementById('matricula').value.trim(),
        curso: document.getElementById('curso').value,
        periodo: parseInt(document.getElementById('periodo').value),
        maxHoras: parseInt(document.getElementById('max-horas').value),
        historico: [...historicoTemporario]
    };

    if (id === "") {
        // Create
        perfis.push(perfilDados);
    } else {
        // Update
        perfis[parseInt(id)] = perfilDados;
        document.getElementById('perfil-id').value = "";
        document.getElementById('form-title').innerText = "Cadastrar Perfil Aluno";
        document.getElementById('btn-salvar').innerText = "Salvar Perfil";
    }

    localStorage.setItem('perfis_organizador', JSON.stringify(perfis));
    perfilForm.reset();
    historicoTemporario = [];
    atualizarPreviewHistorico();
    renderizarTabelaPerfis();
});

// Renderizar lista de perfis na tabela
function renderizarTabelaPerfis() {
    if(perfis.length === 0) {
        perfisTbody.innerHTML = `<tr><td colspan="4" style="text-align:center;">Nenhum perfil cadastrado.</td></tr>`;
        return;
    }

    perfisTbody.innerHTML = perfis.map((perfil, index) => `
        <tr style="${perfilSelecionadoIndex === index ? 'background-color: #f3e5f5; font-weight:bold;' : ''}">
            <td>${perfil.matricula}</td>
            <td>${perfil.curso}</td>
            <td>${perfil.periodo}°</td>
            <td>
                <button class="btn-edit" onclick="editarPerfil(${index})">✏️</button>
                <button class="btn-danger" onclick="deletarPerfil(${index})">🗑️</button>
                <button class="btn-secondary" onclick="selecionarPerfil(${index})">🎯 Selecionar</button>
            </td>
        </tr>
    `).join('');
}

// Editar Perfil (U do CRUD)
function editarPerfil(index) {
    const p = perfis[index];
    document.getElementById('perfil-id').value = index;
    document.getElementById('matricula').value = p.matricula;
    document.getElementById('curso').value = p.curso;
    document.getElementById('periodo').value = p.periodo;
    document.getElementById('max-horas').value = p.maxHoras;
    
    historicoTemporario = [...p.historico];
    atualizarPreviewHistorico();

    document.getElementById('form-title').innerText = "Editando Perfil";
    document.getElementById('btn-salvar').innerText = "Atualizar Perfil";
}

// Deletar Perfil (D do CRUD)
function deletarPerfil(index) {
    if(confirm("Deseja mesmo excluir este perfil?")) {
        perfis.splice(index, 1);
        if(perfilSelecionadoIndex === index) {
            perfilSelecionadoIndex = null;
            document.getElementById('perfil-selected-txt').innerText = "Nenhum perfil selecionado";
        }
        localStorage.setItem('perfis_organizador', JSON.stringify(perfis));
        renderizarTabelaPerfis();
    }
}

// Selecionar para o Cálculo do Grafo
function selecionarPerfil(index) {
    perfilSelecionadoIndex = index;
    const p = perfis[index];
    document.getElementById('perfil-selecionado-txt').innerText = `Perfil Selecionado: ${p.matricula} (${p.curso})`;
    renderizarTabelaPerfis();
    switchTab('ranking'); // Joga o usuário para a aba do ranking
}

// ==========================================
// CONEXÃO COM O BACKEND NODE.JS
// ==========================================
async function calcularGradeNoBackend() {
    if (perfilSelecionadoIndex === null) {
        alert("Por favor, selecione um perfil ativo na aba de gerenciamento antes!");
        return;
    }

    const perfilParaEnviar = perfis[perfilSelecionadoIndex];
    const tbodyRanking = document.getElementById('ranking-tbody');
    tbodyRanking.innerHTML = `<tr><td colspan="6" style="text-align: center;">O Python está processando o Grafo... ⏳</td></tr>`;

    try {
        // Envia os dados coletados no CRUD direto para a rota do Node.js
        const response = await fetch('http://localhost:3000/calcular-grade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(perfilParaEnviar)
        });

        const data = await response.json();

        if (data.error) {
            tbodyRanking.innerHTML = `<tr><td colspan="6" style="text-align: center; color: red;">Erro: ${data.error}</td></tr>`;
            return;
        }

        // Renderiza o ranking devolvido pelo back-end
        tbodyRanking.innerHTML = data.grade_sugerida.map((materia, idx) => `
            <tr>
                <td><strong>${idx + 1}°</strong></td>
                <td>${materia.codigo}</td>
                <td>${materia.disciplina}</td>
                <td>${materia.carga_horaria}</td>
                <td>${materia.unidade_responsavel}</td>
                <td><span style="color: green; font-weight: bold;">${materia.motivo || 'Libera fluxo/DP'}</span></td>
            </tr>
        `).join('');

    } catch (error) {
        tbodyRanking.innerHTML = `<tr><td colspan="6" style="text-align: center; color: red;">Não foi possível conectar ao servidor Node.js. Ligue o backend.</td></tr>`;
    }
}