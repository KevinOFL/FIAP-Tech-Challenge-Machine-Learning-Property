import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import learning_curve

def plot_learning_curve(estimator, title, X, y, cv=5, n_jobs=-1, train_sizes=np.linspace(0.1, 1.0, 10)):
    """
    Gera e plota uma curva de aprendizagem para um estimador.
    """
    train_sizes, train_scores, test_scores = learning_curve(
        estimator, X, y, cv=cv, n_jobs=n_jobs, train_sizes=train_sizes,
        scoring="neg_mean_squared_error" # Usamos erro para que "menor seja melhor"
    )
    
    # invertemos o sinal de erro e tiramos a média
    train_scores_mean = -np.mean(train_scores, axis=1)
    test_scores_mean = -np.mean(test_scores, axis=1)
    
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.figure(figsize=(10, 6))
    plt.plot(train_sizes, train_scores_mean, 'o-', color="r", label="Erro de Treino")
    plt.plot(train_sizes, test_scores_mean, 'o-', color="g", label="Erro de Validação Cruzada")
    
    plt.title(title, fontsize=18)
    plt.xlabel("Número de Amostras de Treino", fontsize=14)
    plt.ylabel("Erro Quadrático Médio (MSE)", fontsize=14)
    plt.legend(loc="best")
    plt.grid(True)
    plt.show()