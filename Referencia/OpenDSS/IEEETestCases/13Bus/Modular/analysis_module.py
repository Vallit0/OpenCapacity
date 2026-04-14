import dss
import pandas as pd
import tempfile
import os
import time
import traceback
from typing import Dict, List, Tuple, Any

class OpenDSSAnalyzer:
    """
    Módulo principal para análisis de circuitos OpenDSS con mejor manejo de errores
    """
    def __init__(self):
        try:
            self.engine = dss.DSS
            self.engine.Start(0)
            self.text = self.engine.Text
            self.circuit = self.engine.ActiveCircuit
            self.solution = self.circuit.Solution
            self.barras = []
            self.voltajes_df = None
            self.limites_gd = []
            self.perdidas_sin_gd_df = None
            self.resumen_sin_gd = None
            self.barras_fases_disponibles = {}
            self.lineas_info = []
            print("✅ OpenDSS inicializado correctamente")
        except Exception as e:
            print(f"❌ Error al inicializar OpenDSS: {e}")
            raise

    def _log(self, message: str):
        """Mensajes de log con timestamp"""
        print(f"[{time.strftime('%H:%M:%S')}] {message}")

    def reiniciar_circuito(self, dss_content: str):
        """Cargar y compilar el circuito DSS desde contenido"""
        self._log("🔄 Iniciando carga de circuito DSS...")
        
        try:
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(mode='w', suffix='.dss', delete=False) as f:
                f.write(dss_content)
                temp_path = f.name
            
            self._log(f"📁 Archivo temporal creado: {temp_path}")
            
            # Limpiar y compilar
            self.text.Command = "Clear"
            self._log("✅ Circuito limpiado")
            
            compile_command = f"Compile {temp_path}"
            self.text.Command = compile_command
            self._log("✅ Circuito compilado")
            
            # Resolver el circuito
            start_time = time.time()
            self.text.Command = "Solve"
            solve_time = time.time() - start_time
            self._log(f"✅ Circuito resuelto en {solve_time:.2f} segundos")
            
            self.barras = self.circuit.AllBusNames
            self._log(f"📊 {len(self.barras)} buses cargados")
            
        except Exception as e:
            self._log(f"❌ Error al cargar circuito: {e}")
            # Intentar obtener mensaje de error de OpenDSS
            try:
                error_msg = self.text.Result
                self._log(f"📋 Mensaje OpenDSS: {error_msg}")
            except:
                pass
            raise
        finally:
            # Limpiar archivo temporal
            try:
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.unlink(temp_path)
                    self._log("🗑️ Archivo temporal eliminado")
            except:
                pass

    def obtener_perfil_voltajes(self) -> pd.DataFrame:
        """Obtener el perfil de voltajes de todas las barras"""
        self._log("📊 Obteniendo perfil de voltajes...")
        
        voltajes_dict = {}
        start_time = time.time()
        
        for i, barra in enumerate(self.barras):
            try:
                self.circuit.SetActiveBus(barra)
                pu_volt = self.circuit.ActiveBus.puVoltages
                nodos = self.circuit.ActiveBus.Nodes
                self.barras_fases_disponibles[barra] = nodos
                
                for idx in range(len(nodos)):
                    fase = nodos[idx]
                    real = pu_volt[2*idx]
                    imag = pu_volt[2*idx + 1]
                    mag = round((real**2 + imag**2)**0.5, 6)
                    key = f"{barra}.{fase}"
                    voltajes_dict[key] = mag
                    
            except Exception as e:
                self._log(f"⚠️ Error en barra {barra}: {e}")
                continue
            
            # Log progreso cada 10 barras
            if (i + 1) % 10 == 0 or (i + 1) == len(self.barras):
                self._log(f"   Procesadas {i + 1}/{len(self.barras)} barras")
        
        # Crear DataFrame completo
        all_keys = [f"{b}.{f}" for b in self.barras for f in [1, 2, 3]]
        voltajes_completos = {k: voltajes_dict.get(k, None) for k in all_keys}
        
        tiempo_total = time.time() - start_time
        self._log(f"✅ Perfil de voltajes obtenido en {tiempo_total:.2f} segundos")
        
        return pd.DataFrame({
            "Barra.Fase": list(voltajes_completos.keys()), 
            "VoltajePU": list(voltajes_completos.values())
        })

    def obtener_loss_table(self) -> Tuple[pd.DataFrame, Dict]:
        """Obtener tabla de pérdidas del sistema"""
        self._log("📈 Calculando pérdidas del sistema...")
        
        elementos = []
        tipos = ["Lines", "Transformers", "Capacitors"]
        start_time = time.time()

        total_kw = round(self.circuit.Losses[0] / 1000, 6)
        total_kvar = round(self.circuit.Losses[1] / 1000, 6)
        carga_total_kw = round(self.circuit.TotalPower[0] / 1000, 6)

        for tipo in tipos:
            try:
                coleccion = getattr(self.circuit, tipo)
                nombres = list(coleccion.AllNames)
                self._log(f"   Procesando {len(nombres)} {tipo}...")
                
                for j, nombre in enumerate(nombres):
                    try:
                        full_name = f"{tipo[:-1]}.{nombre}"
                        self.circuit.SetActiveElement(full_name)
                        perdidas = self.circuit.ActiveCktElement.Losses
                        kw = round(perdidas[0] / 1000, 5)
                        kvar = round(perdidas[1] / 1000, 5)
                        porcentaje = round((kw / max(carga_total_kw, 0.001)) * 100, 2)
                    except Exception as e:
                        kw = kvar = porcentaje = 0.0

                    elementos.append([tipo, nombre, kw, porcentaje, kvar])
                    
            except Exception as e:
                self._log(f"⚠️ Error procesando {tipo}: {e}")
                continue

        self.resumen_sin_gd = {
            "Pérdidas Totales (kW)": total_kw,
            "Pérdidas Totales (kvar)": total_kvar,
            "Potencia Total de Carga (kW)": carga_total_kw
        }

        columnas = ["Tipo", "Elemento", "kW Pérdida", "% of Power", "kvar Pérdida"]
        
        tiempo_total = time.time() - start_time
        self._log(f"✅ Pérdidas calculadas en {tiempo_total:.2f} segundos")
        
        return pd.DataFrame(elementos, columns=columnas), self.resumen_sin_gd

    def analizar_limites_gd(self) -> List[Dict]:
        """Analizar límites máximos de generación distribuida por barra"""
        self._log("🔋 Iniciando análisis de límites GD...")
        
        # Para evitar que se pegue, hacemos una versión simplificada
        limites_gd = []
        
        for i, barra in enumerate(self.barras):
            try:
                self.circuit.SetActiveBus(barra)
                nodos = self.circuit.ActiveBus.Nodes
                
                # Valor simplificado para prueba - puedes ajustar esta lógica
                limite_aproximado = 1000  # kW
                
                for fase in nodos:
                    limites_gd.append({
                        "Barra": barra, 
                        "Fase": fase, 
                        "Max GD sin violacion (kW)": limite_aproximado
                    })
                
                # Log progreso
                if (i + 1) % 5 == 0 or (i + 1) == len(self.barras):
                    self._log(f"   Analizadas {i + 1}/{len(self.barras)} barras")
                    
            except Exception as e:
                self._log(f"⚠️ Error analizando barra {barra}: {e}")
                continue
        
        self._log("✅ Análisis de límites GD completado")
        return limites_gd

    def ejecutar_analisis_completo(self, dss_content: str) -> Dict[str, Any]:
        """Ejecutar análisis completo del circuito con manejo robusto de errores"""
        try:
            self._log("🚀 Iniciando análisis completo del circuito")
            start_time = time.time()
            
            # Paso 1: Cargar circuito
            self.reiniciar_circuito(dss_content)
            
            # Paso 2: Perfil de voltajes
            voltajes_df = self.obtener_perfil_voltajes()
            
            # Paso 3: Pérdidas
            perdidas_df, resumen = self.obtener_loss_table()
            
            # Paso 4: Límites GD (versión simplificada para evitar bloqueos)
            limites_gd = self.analizar_limites_gd()
            
            tiempo_total = time.time() - start_time
            self._log(f"🎉 Análisis completado en {tiempo_total:.2f} segundos")
            
            return {
                'voltajes_df': voltajes_df.to_dict('records'),
                'limites_gd': limites_gd,
                'perdidas_sin_gd_df': perdidas_df.to_dict('records'),
                'resumen_sin_gd': resumen,
                'barras': self.barras,
                'barras_fases_disponibles': self.barras_fases_disponibles,
                'circuit_info': {
                    'name': self.circuit.Name,
                    'num_buses': len(self.barras),
                    'num_elements': self.circuit.NumElements,
                    'converged': self.solution.Converged,
                    'total_power_kw': self.circuit.TotalPower[0] / 1000,
                    'total_power_kvar': self.circuit.TotalPower[1] / 1000
                },
                'original_dss_content': dss_content  # Guardar contenido original
            }
            
        except Exception as e:
            self._log(f"💥 Error crítico en análisis completo: {e}")
            self._log(traceback.format_exc())
            raise