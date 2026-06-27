const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path'); 
const multer = require('multer');

const app = express();
app.use(cors());
app.use(express.json());

// Diz ao Node para servir os arquivos visuais (CSS, JS, Imagens) que estão na pasta frontend
app.use(express.static(path.join(__dirname, '../frontend')));

// Rota para abrir o seu arquivo index.html automaticamente ao acessar http://localhost:3000
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/index.html'));
});

// Rota alternativa caso queira acessar diretamente o sistema via barra /sistema
app.get('/sistema', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/sistema.html'));
});

// Rota para processar a grade manual (Via seleção de matérias no index)
app.post('/calcular-grade', (req, res) => {
    const materiasSelecionadas = req.body.materias; 

    const pythonProcess = spawn('python', ['grafo.py', JSON.stringify(materiasSelecionadas)]);
    let dataResponse = "";

    pythonProcess.stdout.on('data', (data) => {
        dataResponse += data.toString();
    });

    pythonProcess.on('close', (code) => {
        try {
            const resultadoGrafo = JSON.parse(dataResponse);
            res.json(resultadoGrafo); 
        } catch (error) {
            res.status(500).json({ error: "Erro ao processar o grafo em Python." });
        }
    });
});

// 1. Configuração de armazenamento do Multer (Histórico PDF)
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        // Define o caminho completo da pasta
        const pastaDestino = path.join(__dirname, '../../software/src/data/Dataset-Cenario1-RecomendacaoMatricula');
        
        // NOVO: Verifica se a pasta existe. Se não existir, cria ela automaticamente!
        if (!fs.existsSync(pastaDestino)) {
            fs.mkdirSync(pastaDestino, { recursive: true });
        }

        cb(null, pastaDestino);
    },
    filename: function (req, file, cb) {
        // Mantém o nome original do arquivo enviado
        cb(null, file.originalname);
    }
});

// Filtro para garantir que apenas PDFs sejam aceitos
const fileFilter = (req, file, cb) => {
    if (file.mimetype === 'application/pdf') {
        cb(null, true);
    } else {
        cb(new Error('Apenas arquivos PDF são permitidos!'), false);
    }
};

const upload = multer({ storage: storage, fileFilter: fileFilter });

// 2. Rota para receber o upload do histórico
app.post('/upload-historico', upload.single('historico'), (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ error: "Nenhum arquivo foi enviado." });
        }

        console.log(`Arquivo recebido com sucesso: ${req.file.filename}`);
        console.log(`Salvo em: ${req.file.path}`);

        // O arquivo já está salvo na pasta de datasets! 
        // Quando quiser chamar o parser no futuro:
        // const { exec } = require('child_process');
        // exec(`python3 ../../parser-historico.py "${req.file.path}"`, ...);

        return res.status(200).json({ 
            message: "Histórico recebido e salvo com sucesso!",
            fileName: req.file.filename,
            path: req.file.path
        });

    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

// Iniciar o servidor (APENAS UMA CHAMADA DA PORTA 3000)
const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Servidor rodando com sucesso na porta ${PORT}`);
});