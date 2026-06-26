const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const fs = require('fs');

const app = express();
app.use(cors());
app.use(express.json());

// Rota para processar a grade
app.post('/calcular-grade', (req, res) => {
    const materiasSelecionadas = req.body.materias; // Vem do front

    // Dispara o script Python passando os dados como argumento de texto (JSON)
    const pythonProcess = spawn('python', ['grafo.py', JSON.stringify(materiasSelecionadas)]);

    let dataResponse = "";

    // Pega o que o Python printar no terminal (stdout)
    pythonProcess.stdout.on('data', (data) => {
        dataResponse += data.toString();
    });

    // Quando o Python terminar de rodar
    pythonProcess.on('close', (code) => {
        try {
            const resultadoGrafo = JSON.parse(dataResponse);
            res.json(resultadoGrafo); // Devolve pro front
        } catch (error) {
            res.status(500).json({ error: "Erro ao processar o grafo em Python." });
        }
    });
});

app.listen(3000, () => console.log('Servidor rodando na porta 3000'));