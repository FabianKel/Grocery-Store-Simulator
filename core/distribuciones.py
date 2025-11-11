import random
import numpy as np
from scipy.stats import poisson, expon, beta, norm


def clientes_por_hora(dia: str, hora: int) -> int:
    """
    Genera el número esperado de clientes por hora usando Poisson.
    """
    # Tasa base (por hora)
    base_lambda = 10  

    # Ajuste por día
    dia_factor = {
        "lunes": 0.6, "martes": 0.7, "miércoles": 0.8,
        "jueves": 1.0, "viernes": 1.3, "sábado": 1.5, "domingo": 1.2
    }.get(dia.lower(), 1.0)

    # Ajuste por hora
    if 9 <= hora < 12:
        hora_factor = 0.8
    elif 12 <= hora < 15:
        hora_factor = 1.5  # hora pico
    elif 15 <= hora < 18:
        hora_factor = 1.2
    else:
        hora_factor = 0.9

    λ = base_lambda * dia_factor * hora_factor
    print(f"dia: {dia}, hora: {hora}, λ: {λ}")
    return poisson.rvs(λ)

def calc_client_type(dia: str, hora: int) -> str:
    """
    Retorna 'familia' o 'solo' según día y hora.
    """
    prob_familia = 0.3  # base
    
    if dia.lower() in ["sábado", "domingo"]:
        prob_familia += 0.4
    if 16 <= hora <= 20:
        prob_familia += 0.2
    if 9 <= hora <= 11:
        prob_familia -= 0.2
    
    prob_familia = np.clip(prob_familia, 0, 1)
    return "familia" if random.random() < prob_familia else "solo"


def intervalo_entre_clientes(lmbda: float = 1/5) -> int:
    """
    Devuelve ticks entre llegadas (mínimo 1).
    λ controla la frecuencia de llegada (menor λ = llegadas más frecuentes)
    """
    valor = int(expon.rvs(scale=1/lmbda))
    print(f"valor: {max(1, valor)}")
    return max(1, valor)


def calc_speed(dia: str, hora: int, tipo: str) -> str:
    """
    Retorna 'Rapido', 'Normal' o 'Tranquilo' basado en contexto.
    """
    if tipo == "familia":
        probs = {"Rapido": 0.1, "Normal": 0.5, "Tranquilo": 0.2}
    else:
        probs = {"Rapido": 0.4, "Normal": 0.5, "Tranquilo": 0.1}

    if dia.lower() in ["sábado", "domingo"]:
        probs["Tranquilo"] += 0.2
        probs["Rapido"] -= 0.1

    if 9 <= hora <= 11:
        probs["Rapido"] += 0.2
        probs["Tranquilo"] -= 0.1

    # Normalizar
    total = sum(probs.values())
    for k in probs:
        probs[k] /= total

    return random.choices(list(probs.keys()), weights=probs.values())[0]


def calc_paciencia() -> float:
    """
    Retorna un valor entre 0 y 1 representando la paciencia.
    """
    return float(beta.rvs(2, 5))


def noise_caja(mu=1, sigma=0.5) -> int:
    """
    Retorna un entero representando la variación en tiempo de servicio.
    """
    valor = int(np.clip(norm.rvs(mu, sigma), 0, 3))
    return valor

import numpy as np

def calc_move_delay(tipo: str, rapidez: str) -> int:
    """
    Calcula la cantidad de ticks que tarda un cliente en moverse una casilla,
    dependiendo de su tipo y rapidez.
    
    tipo: 'familia' o 'solo'
    rapidez: 'Rapido', 'Normal', 'Tranquilo'
    """
    # Rangos base según rapidez
    base_ranges = {
        "Rapido":   (1, 2),
        "Normal":   (2, 4),
        "Tranquilo":(4, 5)
    }

    low, high = base_ranges.get(rapidez, (2, 4))
    mean = (low + high) / 2
    std = (high - low) / 4  # Pequeña desviación

    # Penalización o ajuste por tipo de cliente
    if tipo == "familia":
        # Familias se mueven más lento (carreta, conversación, niños)
        mean *= 1.3
        std *= 1.2
    elif tipo == "solo":
        mean *= 1.0

    # Generar valor truncado
    value = int(np.clip(np.random.normal(mean, std), 1, 8))
    return max(1, value)
