import opendssdirect as dss
import numpy as np
import random

# Función para evaluar las pérdidas de potencia en la red
def evaluar_perdidas(ubicacion, potencia):
    dss.Text.Command("clear")
    dss.Text.Command("redirect IEEE13Nodeckt.dss")
    
    # Insertar generador fotovoltaico en la ubicación especificada
    dss.Text.Command(f"New Generator.PV Bus1={ubicacion} Phases=3 kV=4.16 kW={potencia} kvar=0.0 Model=1")
    
    # Resolver sistema
    dss.Text.Command("solve")
    
    # Obtener pérdidas totales del sistema
    perdidas = dss.Circuit.Losses()[0] / 1000  # Convertir a kW
    return perdidas

# Parámetros del PSO
num_particulas = 10
num_iteraciones = 20
nodos_candidatos = ["632", "633", "634", "645", "646", "671", "684", "692"]  # Nodos disponibles
pot_min, pot_max = 100, 5000  # Rango de potencia del PV en kW

# Inicializar partículas (ubicación y potencia del PV)
particulas = [(random.choice(nodos_candidatos), random.uniform(pot_min, pot_max)) for _ in range(num_particulas)]
velocidades = [(0, 0) for _ in range(num_particulas)]
mejor_personal = particulas[:]
mejor_global = min(particulas, key=lambda p: evaluar_perdidas(p[0], p[1]))

# PSO Loop
w = 0.7  # Factor de inercia
c1, c2 = 1.5, 1.5  # Coeficientes de aceleración

for _ in range(num_iteraciones):
    for i in range(num_particulas):
        ubicacion, potencia = particulas[i]
        perdida_actual = evaluar_perdidas(ubicacion, potencia)
        
        if perdida_actual < evaluar_perdidas(mejor_personal[i][0], mejor_personal[i][1]):
            mejor_personal[i] = (ubicacion, potencia)
        
        if perdida_actual < evaluar_perdidas(mejor_global[0], mejor_global[1]):
            mejor_global = (ubicacion, potencia)
        
        # Actualizar velocidad y posición de la partícula
        r1, r2 = random.random(), random.random()
        nueva_velocidad = (
            w * velocidades[i][0] + c1 * r1 * (mejor_personal[i][1] - potencia) + c2 * r2 * (mejor_global[1] - potencia),
        )
        nueva_potencia = max(pot_min, min(pot_max, potencia + nueva_velocidad[0]))
        particulas[i] = (random.choice(nodos_candidatos), nueva_potencia)
        velocidades[i] = nueva_velocidad

# Resultado óptimo
ubicacion_optima, potencia_optima = mejor_global
print(f"Ubicación óptima: {ubicacion_optima}, Potencia óptima: {potencia_optima:.2f} kW")

# Insertar el PV óptimo en OpenDSS
dss.Text.Command("clear")
dss.Text.Command("redirect IEEE13Nodeckt.dss")
dss.Text.Command(f"New Generator.PV_opt Bus1={ubicacion_optima} Phases=3 kV=4.16 kW={potencia_optima} kvar=0.0 Model=1")
dss.Text.Command("solve")

# Obtener voltajes finales
voltages = dss.Circuit.AllBusMagPu()
buses = dss.Circuit.AllBusNames()

for bus, voltage in zip(buses, voltages):
    print(f"Bus: {bus}, Voltaje (pu): {voltage:.4f}")

dss.Text.Command("show powers kVA elem")
