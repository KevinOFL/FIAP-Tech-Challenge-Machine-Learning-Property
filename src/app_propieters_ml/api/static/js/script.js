// static/js/script.js

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('prediction-form');
    const resultDisplay = document.getElementById('result-display');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        resultDisplay.textContent = 'Calculando...';

        // O FormData já coleta todos os campos do formulário pelos seus 'name'
        const formData = new FormData(form);

        // Criamos o objeto payload com os tipos corretos
        const data = {
            property_type: formData.get('property_type'),
            area_m2: parseInt(formData.get('area_m2'), 10),
            rooms: parseInt(formData.get('rooms'), 10),
            bathrooms: parseInt(formData.get('bathrooms'), 10),
            vacancies: parseInt(formData.get('vacancies'), 10),
        };

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            // Pega o corpo da resposta, seja sucesso ou erro
            const result = await response.json();

            if (!response.ok) {
                // Se a API retornou um erro (ex: 400), o 'detail' estará no result
                throw new Error(result.detail || `Erro na requisição: ${response.statusText}`);
            }

            const predictionValue = result.prediction;

            // Cria um objeto de formatação para a moeda brasileira (Real)
            const formatter = new Intl.NumberFormat('pt-BR', {
                style: 'currency',
                currency: 'BRL',
            });

            // Usa o formatador para criar a string de valor formatado
            const formattedPrediction = formatter.format(predictionValue);
            
            // Exibe o resultado formatado de forma amigável
            resultDisplay.textContent = `Valor Predito do Imóvel: ${formattedPrediction}`;
            
            // Exibe o resultado formatado
            // resultDisplay.textContent = JSON.stringify(result, null, 2);

        } catch (error) {
            resultDisplay.textContent = `Ocorreu um erro: ${error.message}`;
            console.error('Erro ao fazer predição:', error);
        }
    });
});