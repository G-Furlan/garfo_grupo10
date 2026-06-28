const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const multer = require('multer');

const app = express();
app.use(cors());
app.use(express.json());

// Serve os arquivos do frontend
app.use(express.static(path.join(__dirname, '../frontend')));

// Guarda o último grafo processado, para o resultados.html buscar
let ultimoGrafo = null;

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/index.html'));
});

app.get('/sistema', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/sistema.html'));
});

// Rota da grade manual (mantida como estava)
app.post('/calcular-grade', (req, res) => {
    const materiasSelecionadas = req.body.materias;
    const pythonProcess = spawn(PYTHON, ['grafo.py', JSON.stringify(materiasSelecionadas)]);
    let dataResponse = "";
    pythonProcess.on('error', () => res.status(500).json({ error: "Não foi possível iniciar o Python." }));
    pythonProcess.stdout.on('data', (data) => { dataResponse += data.toString(); });
    pythonProcess.on('close', () => {
        try {
            res.json(JSON.parse(dataResponse));
        } catch (error) {
            res.status(500).json({ error: "Erro ao processar o grafo em Python." });
        }
    });
});

// -----------------------------------------------------------------
// Upload do histórico  (salva o PDF e roda o pipeline automaticamente)
// -----------------------------------------------------------------
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        const pastaDestino = path.join(__dirname, '../../software/src/data/Dataset-Cenario1-RecomendacaoMatricula');
        if (!fs.existsSync(pastaDestino)) {
            fs.mkdirSync(pastaDestino, { recursive: true });
        }
        cb(null, pastaDestino);
    },
    filename: function (req, file, cb) {
        cb(null, file.originalname);
    }
});

const fileFilter = (req, file, cb) => {
    if (file.mimetype === 'application/pdf') {
        cb(null, true);
    } else {
        cb(new Error('Apenas arquivos PDF são permitidos!'), false);
    }
};

const upload = multer({ storage: storage, fileFilter: fileFilter });

// Resolve qual Python usar: prioriza o da venv do software/ (onde pandas/pdfplumber
// estão instalados); senão usa a variável PYTHON_BIN; senão tenta 'python3'/'python'.
function resolverPython() {
    const candidatos = [
        path.join(__dirname, '../../software/.venv/bin/python'),        // Linux/Mac/WSL
        path.join(__dirname, '../../software/.venv/Scripts/python.exe'),// Windows
        process.env.PYTHON_BIN,
    ].filter(Boolean);
    for (const c of candidatos) {
        if (fs.existsSync(c)) return c;
    }
    return process.env.PYTHON_BIN || 'python3';
}
const PYTHON = resolverPython();
console.log(`Python usado pelo backend: ${PYTHON}`);

// Roda o pipeline Python (parser -> parte 1 -> parte 2) e devolve o grafo Cytoscape
function processarGrafo(caminhoPdf) {
    return new Promise((resolve, reject) => {
        const scriptPath = path.join(__dirname, '../../software/src/exportar_grafo.py');
        const softwareDir = path.join(__dirname, '../../software');
        const py = spawn(PYTHON, [scriptPath, caminhoPdf], { cwd: softwareDir });

        let out = "", err = "", finalizado = false;
        const encerrar = (fn, arg) => { if (!finalizado) { finalizado = true; fn(arg); } };

        // Se o python não existir / não puder ser iniciado, isto evita o "pendura sem resposta"
        py.on('error', (e) => {
            encerrar(reject, new Error(
                `Não foi possível iniciar o Python ("${PYTHON}"): ${e.message}. ` +
                `Ative a venv ou defina a variável de ambiente PYTHON_BIN.`));
        });

        py.stdout.on('data', (d) => { out += d.toString(); });
        py.stderr.on('data', (d) => { err += d.toString(); });

        // Trava de segurança: não deixa a requisição pendurada para sempre
        const timer = setTimeout(() => {
            py.kill();
            encerrar(reject, new Error("O processamento demorou demais (timeout)."));
        }, 60000);

        py.on('close', (code) => {
            clearTimeout(timer);
            if (code !== 0 && !out) {
                return encerrar(reject, new Error(err || `Python encerrou com código ${code}`));
            }
            try {
                const json = JSON.parse(out);
                if (json.error) return encerrar(reject, new Error(json.error));
                encerrar(resolve, json);
            } catch (e) {
                encerrar(reject, new Error("Saída do Python não é JSON válido. stderr: " + err));
            }
        });
    });
}

app.post('/upload-historico', upload.single('historico'), async (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ error: "Nenhum arquivo foi enviado." });
        }
        console.log(`Arquivo recebido: ${req.file.filename}`);

        const grafo = await processarGrafo(req.file.path);
        ultimoGrafo = grafo; // fica disponível para o resultados.html

        return res.status(200).json({
            message: "Histórico processado com sucesso!",
            fileName: req.file.filename,
            meta: grafo.meta,
            grafo: grafo
        });
    } catch (error) {
        console.error("Erro no pipeline:", error.message);
        return res.status(500).json({ error: error.message });
    }
});

// Endpoint que o resultados.html consome para desenhar o grafo
app.get('/grafo-atual', (req, res) => {
    if (!ultimoGrafo) {
        return res.status(404).json({ error: "Nenhum grafo processado ainda. Envie um histórico primeiro." });
    }
    res.json(ultimoGrafo);
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Servidor rodando com sucesso na porta ${PORT}`);
});