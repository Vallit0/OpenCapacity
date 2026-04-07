import streamlit as st
from streamlit_echarts import st_echarts

# Título de la aplicación
st.title("Mi Aplicación de Gráficos Interactivos")

# Entrada de texto para el título del gráfico
titulo = st.text_input("Introduce el título del gráfico", "Gráfico de líneas apiladas")

# Datos para el gráfico
options = {
    "title": {"text": titulo},  # Título dinámico
    "tooltip": {"trigger": "axis"},
    "legend": {"data": ["Marketing por correo", "Publicidad en alianza", "Publicidad en video", "Acceso directo", "Motores de búsqueda"]},
    "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
    "toolbox": {"feature": {"saveAsImage": {}}},
    "xAxis": {
        "type": "category",
        "boundaryGap": False,
        "data": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
    },
    "yAxis": {"type": "value"},
    "series": [
        {
            "name": "Marketing por correo",
            "type": "line",
            "stack": "Total",
            "data": [120, 132, 101, 134, 90, 230, 210],
        },
        {
            "name": "Publicidad en alianza",
            "type": "line",
            "stack": "Total",
            "data": [220, 182, 191, 234, 290, 330, 310],
        },
        {
            "name": "Publicidad en video",
            "type": "line",
            "stack": "Total",
            "data": [150, 232, 201, 154, 190, 330, 410],
        },
        {
            "name": "Acceso directo",
            "type": "line",
            "stack": "Total",
            "data": [320, 332, 301, 334, 390, 330, 320],
        },
        {
            "name": "Motores de búsqueda",
            "type": "line",
            "stack": "Total",
            "data": [820, 932, 901, 934, 1290, 1330, 1320],
        },
    ],
}

# Mostrar gráfico interactivo
st_echarts(options=options, height="400px")

# Puedes agregar más interactividad, como sliders, selectores de fecha, etc.



