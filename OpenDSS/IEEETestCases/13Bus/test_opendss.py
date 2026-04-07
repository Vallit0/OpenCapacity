import opendssdirect as dss

# Inicializar OpenDSS
dss.Basic.Start(0)
print("OpenDSS inicializado correctamente.")

# Cargar el archivo DSS
dss.Text.Command("compile test_circuit.dss")
print("Circuito cargado correctamente.")

# Resolver el circuito
dss.Text.Command("solve")
print("Circuito resuelto correctamente.")

# Obtener resultados
total_power = dss.Circuit.TotalPower()
print(f"Potencia total del circuito: {total_power} kVA")

# Obtener información de las barras
buses = dss.Circuit.AllBusNames()
print("\nBarras en el circuito:")
for bus in buses:
    print(bus)

# Obtener información de las cargas
dss.Loads.First()
load_name = dss.Loads.Name()
load_kw = dss.Loads.kW()
load_kvar = dss.Loads.kvar()
print(f"\nCarga '{load_name}': {load_kw} kW, {load_kvar} kvar")