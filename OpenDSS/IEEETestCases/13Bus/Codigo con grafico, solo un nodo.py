import opendssdirect as dss
import numpy as np
import random
import matplotlib.pyplot as plt

# Número de puntos de inserción de PV
num_pvs = 3  # Puedes ajustar este valor

# Inicializar OpenDSS y obtener voltajes iniciales sin generación PV
dss.Text.Command("clear")
dss.Text.Command("redirect IEEE13Nodeckt.dss")
dss.Text.Command("solve")

buses = np.array(dss.Circuit.AllBusNames())  # Asegurar que es un array
voltajes_iniciales = np.array(dss.Circuit.AllBusMagPu())  # Convertir a array

# Función para evaluar las pérdidas de potencia en la red
def evaluar_perdidas(ubicaciones_potencias):
    dss.Text.Command("clear")
    dss.Text.Command("redirect IEEE13Nodeckt.dss")
    
    for i, (ubicacion, potencia) in enumerate(ubicaciones_potencias):
        dss.Text.Command(f"New Generator.PV{i} Bus1={ubicacion} Phases=3 kV=4.16 kW={potencia} kvar=0.0 Model=1")
    
    dss.Text.Command("solve")
    return dss.Circuit.Losses()[0] / 1000  # Convertir a kW

# Parámetros del PSO
num_particulas = 20
num_iteraciones = 50
nodos_candidatos = ["632", "633", "634", "645", "646", "671", "684", "692"]
pot_min, pot_max = 100, 6000

# Inicializar partículas y velocidades
particulas = [[(random.choice(nodos_candidatos), random.uniform(pot_min, pot_max)) for _ in range(num_pvs)] for _ in range(num_particulas)]
velocidades = [[random.uniform(-1000, 1000) for _ in range(num_pvs)] for _ in range(num_particulas)]
mejor_personal = particulas[:]
mejor_global = min(particulas, key=evaluar_perdidas)

# Parámetros del PSO
w, c1, c2 = 0.5, 1.2, 1.2  

# PSO Loop
for _ in range(num_iteraciones):
    for i in range(num_particulas):
        perdida_actual = evaluar_perdidas(particulas[i])
        if perdida_actual < evaluar_perdidas(mejor_personal[i]):
            mejor_personal[i] = particulas[i]
        if perdida_actual < evaluar_perdidas(mejor_global):
            mejor_global = particulas[i]

        for j in range(num_pvs):
            ubicacion, potencia = particulas[i][j]
            mejor_personal_pv = mejor_personal[i][j]
            mejor_global_pv = mejor_global[j]
            
            r1, r2 = random.random(), random.random()
            nueva_velocidad = (
                w * velocidades[i][j] +
                c1 * r1 * (mejor_personal_pv[1] - potencia) +
                c2 * r2 * (mejor_global_pv[1] - potencia)
            )
            
            nueva_potencia = max(pot_min, min(pot_max, potencia + nueva_velocidad))
            nueva_ubicacion = ubicacion if random.random() > 0.2 else random.choice(nodos_candidatos)
            
            particulas[i][j] = (nueva_ubicacion, nueva_potencia)
            velocidades[i][j] = nueva_velocidad

# Resultado óptimo
ubicaciones_optimas = mejor_global
print("Ubicaciones óptimas y potencias de los PV:")
for i, (ubicacion, potencia) in enumerate(ubicaciones_optimas):
    print(f"PV{i+1} -> Ubicación: {ubicacion}, Potencia: {potencia:.2f} kW")

# Insertar los PVs óptimos en OpenDSS
dss.Text.Command("clear")
dss.Text.Command("redirect IEEE13Nodeckt.dss")
for i, (ubicacion, potencia) in enumerate(ubicaciones_optimas):
    dss.Text.Command(f"New Generator.PV{i} Bus1={ubicacion} Phases=3 kV=4.16 kW={potencia} kvar=0.0 Model=1")
dss.Text.Command("solve")

# Obtener voltajes finales y asegurar que sean arrays de NumPy
voltajes_finales = np.array(dss.Circuit.AllBusMagPu())

# Ordenar voltajes según los buses
orden = np.argsort(buses)
buses_ordenados = buses[orden]
voltajes_ini_ordenados = voltajes_iniciales[orden]
voltajes_fin_ordenados = voltajes_finales[orden]

# Graficar resultados
plt.figure(figsize=(10, 5))
plt.plot(buses_ordenados, voltajes_ini_ordenados, marker='o', linestyle='-', color='blue', label="Voltajes Iniciales")
plt.plot(buses_ordenados, voltajes_fin_ordenados, marker='s', linestyle='--', color='red', label="Voltajes Finales")

plt.xlabel("Buses")
plt.ylabel("Voltaje (pu)")
plt.title("Comparación de Voltajes Antes y Después de la Optimización")
plt.xticks(rotation=45)
plt.legend()
plt.grid(linestyle="--", alpha=0.7)

plt.show()
