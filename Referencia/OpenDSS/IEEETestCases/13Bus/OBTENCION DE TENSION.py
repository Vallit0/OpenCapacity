import opendssdirect as dss
from tabulate import tabulate  # Importar tabulate para mostrar la tabla

# Cargar el circuito
dss.Text.Command("redirect IEEE13Nodeckt.dss")

# Resolver el circuito
dss.Text.Command("solve")

# Obtener nombres de barras y voltajes en PU
barras = dss.Circuit.AllBusNames()
voltajes_pu = dss.Circuit.AllBusMagPu()

# Crear una lista de listas para los datos de la tabla
datos_tabla = [[barra, voltaje] for barra, voltaje in zip(barras, voltajes_pu)]

# Mostrar la tabla usando tabulate
print("\nTabla de Voltajes en PU:")
print(tabulate(datos_tabla, headers=["Barra", "Voltaje (PU)"], tablefmt="pretty"))
