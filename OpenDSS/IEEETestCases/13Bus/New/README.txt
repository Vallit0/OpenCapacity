
# Modular OpenDSS Dash App (Skeleton)

1) Install dependencies:
   - dash, dash-bootstrap-components, plotly, pandas, dss_python (or opendssdirect if you adapt).

2) Run:
   ```bash
   python app.py
   ```

3) In the welcome screen:
   - Carga tu archivo `.dss`. Se guarda automáticamente en la carpeta temporal de Windows.
   - Se habilitará el botón **Analizar archivo** y el banner cambiará a verde.
   - Haz clic en **Analizar archivo** para ir a la pantalla de análisis.

4) La pantalla de análisis replica la estructura base de tu V3 (gráfico de voltaje y tabla de límites).
   Extiende `src/core_dss.py` y `src/callbacks.py` para cubrir el resto de interacciones (aplicar GD, pérdidas, etc.).
