import py_dss_interface
import networkx as nx
import matplotlib.pyplot as plt

# Crear una instancia de OpenDSS
dss = py_dss_interface.DSS()

# Cargar el archivo .dss
dss.text("Compile IEEE13Nodeckt.dss")

# Crear un grafo para visualizar la red
G = nx.DiGraph()

# Acceder a los transformadores, líneas y barras
# Agregar transformadores
dss.transformers.first()
while True:
    bus1 = dss.transformers.bus1()
    bus2 = dss.transformers.bus2()
    G.add_node(bus1)
    G.add_node(bus2)
    G.add_edge(bus1, bus2)
    if not dss.transformers.next():
        break

# Agregar líneas (conexiones entre barras)
dss.lines.first()
while True:
    bus1 = dss.lines.bus1()
    bus2 = dss.lines.bus2()
    G.add_node(bus1)
    G.add_node(bus2)
    G.add_edge(bus1, bus2)
    if not dss.lines.next():
        break

# Definir las posiciones de los nodos para el gráfico
pos = nx.spring_layout(G, seed=42)  # Establece la disposición de los nodos

# Dibujar el grafo
plt.figure(figsize=(10, 8))
nx.draw(G, pos, with_labels=True, node_size=2000, node_color='skyblue', font_size=10, font_weight='bold', edge_color='gray')

# Título del gráfico
plt.title('Red Eléctrica - Diagrama desde OpenDSS')

# Mostrar el gráfico
plt.show()
