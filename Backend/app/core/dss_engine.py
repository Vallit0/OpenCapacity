"""
Wrapper del motor OpenDSS.

Principio fundamental: el motor NUNCA se inicializa fuera de los workers de
Celery. El proceso de FastAPI (app/) nunca importa este modulo directamente.
Cada worker de Celery instancia un DSSEngine propio e independiente.

Una instancia de DSSEngine = un motor OpenDSS aislado. Nunca compartir entre
threads ni entre requests.
"""

import os
import re
import shutil
import tempfile
from typing import Dict, List, Optional, Tuple

import opendssdirect as dss


class DSSEngineError(Exception):
    """Error base para fallos del motor OpenDSS."""


class CircuitNotLoadedError(DSSEngineError):
    """Se intento operar sin haber cargado un circuito primero."""


class CircuitDidNotConvergeError(DSSEngineError):
    """El solucionador de OpenDSS no convergio."""


class DSSEngine:
    """
    Encapsula completamente el motor OpenDSS.

    Uso esperado dentro de una tarea Celery:
        engine = DSSEngine()
        info = engine.load_circuit(dss_content, linecodes_content)
        voltages = engine.get_voltage_profile()
        ...
    """

    def __init__(self) -> None:
        self._dss = dss
        self._dss.Basic.Start(0)
        self._circuit_loaded: bool = False

    # ------------------------------------------------------------------
    # Carga de circuito
    # ------------------------------------------------------------------

    def load_circuit(
        self,
        dss_content: str,
        linecodes_content: Optional[str] = None,
    ) -> Dict:
        """
        Carga un circuito DSS desde string usando un directorio temporal.
        Siempre limpia los archivos temporales al salir.

        Raises:
            CircuitDidNotConvergeError: si el solucionador no converge.
            DSSEngineError: para cualquier otro fallo del motor.
        """
        temp_dir = tempfile.mkdtemp(prefix="dss_circuit_")
        try:
            processed = _preprocess(dss_content)

            if linecodes_content:
                lc_path = os.path.join(temp_dir, "linecodes.dss")
                with open(lc_path, "w", encoding="utf-8") as f:
                    f.write(linecodes_content)
                # LineCodes requieren un circuito activo en OpenDSS.
                # Insertar el redirect DESPUES del bloque "New Circuit.xxx"
                # (incluyendo sus lineas de continuacion "~ ...").
                circuit_block_re = re.compile(
                    r'(^\s*new\s+circuit\b[^\n]*(?:\n\s*~[^\n]*)*)',
                    re.IGNORECASE | re.MULTILINE,
                )
                processed, n_subs = circuit_block_re.subn(
                    lambda m: m.group(0) + f"\nRedirect {lc_path}",
                    processed,
                    count=1,
                )
                if n_subs == 0:
                    # Fallback: no se encontro "New Circuit" — prepend
                    processed = f"Redirect {lc_path}\n" + processed

            main_path = os.path.join(temp_dir, "circuit.dss")
            with open(main_path, "w", encoding="utf-8") as f:
                f.write(processed)

            self._dss.Text.Command("Clear")
            self._dss.Text.Command(f"Compile {main_path}")
            self._dss.Text.Command("Set MaxIter=100")
            self._dss.Text.Command("Set Tolerance=0.0001")
            self._dss.Solution.Solve()

            if not self._dss.Solution.Converged():
                raise CircuitDidNotConvergeError(
                    "El circuito no convergio. "
                    "Verifique que tenga una fuente definida y cargas validas."
                )

            self._circuit_loaded = True
            return self._get_circuit_info()

        except (CircuitDidNotConvergeError, DSSEngineError):
            raise
        except Exception as exc:
            raise DSSEngineError(
                f"Error al compilar el circuito: {exc}"
            ) from exc
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def reset_circuit(
        self,
        dss_content: str,
        linecodes_content: Optional[str] = None,
    ) -> None:
        """
        Recarga el circuito desde cero, garantizando estado limpio.
        Debe llamarse al inicio de cada iteracion de la busqueda binaria.
        """
        self.load_circuit(dss_content, linecodes_content)

    # ------------------------------------------------------------------
    # Consultas del circuito base
    # ------------------------------------------------------------------

    def get_circuit_info(self) -> Dict:
        self._assert_loaded()
        return self._get_circuit_info()

    def get_buses_phases(self) -> Dict[str, List[int]]:
        """Retorna un dict {bus: [fases disponibles]}."""
        self._assert_loaded()
        result: Dict[str, List[int]] = {}
        for bus in self._dss.Circuit.AllBusNames():
            self._dss.Circuit.SetActiveBus(bus)
            result[bus] = list(self._dss.Bus.Nodes())
        return result

    def get_voltage_profile(self) -> List[Dict]:
        """
        Voltajes PU de todas las barras y fases.
        Retorna una lista de dicts con bus_phase, bus, phase, voltage_pu, in_range.
        """
        self._assert_loaded()
        results: List[Dict] = []
        for bus in self._dss.Circuit.AllBusNames():
            self._dss.Circuit.SetActiveBus(bus)
            pu_mag_ang = self._dss.Bus.puVmagAngle()
            nodes = self._dss.Bus.Nodes()
            for idx, node in enumerate(nodes):
                mag = round(pu_mag_ang[2 * idx], 6)
                results.append(
                    {
                        "bus_phase": f"{bus}.{node}",
                        "bus": bus,
                        "phase": node,
                        "voltage_pu": mag,
                        "in_range": 0.95 <= mag <= 1.05,
                    }
                )
        return results

    def get_losses(self) -> Tuple[List[Dict], Dict]:
        """
        Perdidas por elemento (Lines, Transformers, Capacitors).

        Returns:
            (elements, summary)  — misma estructura que el contrato REST.
        """
        self._assert_loaded()
        total_kw = round(self._dss.Circuit.Losses()[0] / 1000, 6)
        total_kvar = round(self._dss.Circuit.Losses()[1] / 1000, 6)
        total_load_kw = abs(round(self._dss.Circuit.TotalPower()[0] / 1000, 6))
        total_load_kw = max(total_load_kw, 1e-3)

        elements: List[Dict] = []
        _collections = {
            "Lines": self._dss.Lines,
            "Transformers": self._dss.Transformers,
            "Capacitors": self._dss.Capacitors,
        }
        for tipo, col in _collections.items():
            try:
                names = list(col.AllNames())
            except Exception:
                names = []
            for name in names:
                try:
                    self._dss.Circuit.SetActiveElement(f"{tipo[:-1]}.{name}")
                    losses = self._dss.CktElement.Losses()
                    kw = round(losses[0] / 1000, 5)
                    kvar = round(losses[1] / 1000, 5)
                    pct = round((kw / total_load_kw) * 100, 2)
                except Exception:
                    kw = kvar = pct = 0.0
                elements.append(
                    {
                        "type": tipo,
                        "element": name,
                        "losses_kw": kw,
                        "losses_kvar": kvar,
                        "losses_pct": pct,
                    }
                )

        summary = {
            "total_losses_kw": total_kw,
            "total_losses_kvar": total_kvar,
            "total_load_kw": total_load_kw,
            "loss_percentage": round((total_kw / total_load_kw) * 100, 2),
        }
        return elements, summary

    def get_lines_info(self) -> List[Dict]:
        """
        Informacion de lineas: fases, limites de corriente y potencia nominal.
        """
        self._assert_loaded()
        results: List[Dict] = []
        for name in list(self._dss.Lines.AllNames()):
            self._dss.Lines.Name(name)
            self._dss.Circuit.SetActiveElement(f"Line.{name}")
            norm_amps = self._dss.Lines.EmergAmps() or 1.0
            n_phases = self._dss.Lines.Phases()
            bus1 = self._dss.Lines.Bus1().split(".")[0]
            bus2 = self._dss.Lines.Bus2().split(".")[0]
            self._dss.Circuit.SetActiveBus(bus1)
            kv_base = self._dss.Bus.kVBase() or 1.0
            kv = kv_base * 1.732 if n_phases > 1 else kv_base
            s_nom = round(kv * norm_amps, 2)

            # Corrientes actuales (magnitudes)
            mags = self._dss.CktElement.CurrentsMagAng()[::2]
            current_base = [round(m, 2) for m in mags]
            loading_pct = round(
                (max(mags) / norm_amps * 100) if mags else 0.0, 2
            )

            results.append(
                {
                    "name": name,
                    "phases": n_phases,
                    "bus1": bus1,
                    "bus2": bus2,
                    "norm_amps": round(norm_amps, 2),
                    "emerg_amps": round(self._dss.Lines.EmergAmps() or 0.0, 2),
                    "kv_base": round(kv_base, 4),
                    "s_nominal_kva": s_nom,
                    "current_base_amps": current_base,
                    "loading_pct_base": loading_pct,
                }
            )
        return results

    # ------------------------------------------------------------------
    # Simulacion con GD
    # ------------------------------------------------------------------

    def apply_gd(
        self,
        bus: str,
        phases: List[int],
        power_kw: float,
        power_kvar: float = 0.0,
    ) -> None:
        """
        Agrega un generador distribuido al circuito y resuelve.

        Raises:
            CircuitDidNotConvergeError: si el circuito no converge con la GD.
        """
        self._assert_loaded()
        self._dss.Circuit.SetActiveBus(bus)
        kv_ln = self._dss.Bus.kVBase()

        n_phases = len(phases)
        if n_phases == 3:
            kv = kv_ln * 1.732
            cmd = (
                f"New Generator.GD Bus1={bus} Phases=3 "
                f"kV={kv:.3f} kW={power_kw} kvar={power_kvar} Model=1"
            )
        elif n_phases == 2:
            kv = kv_ln * 2
            phases_str = ".".join(str(p) for p in phases)
            cmd = (
                f"New Generator.GD Bus1={bus}.{phases_str} Phases=2 "
                f"kV={kv:.3f} kW={power_kw} kvar={power_kvar} Model=1"
            )
        else:
            cmd = (
                f"New Generator.GD Bus1={bus}.{phases[0]} Phases=1 "
                f"kV={kv_ln:.3f} kW={power_kw} kvar={power_kvar} Model=1"
            )

        self._dss.Text.Command(cmd)
        self._dss.Text.Command("Solve")

        if not self._dss.Solution.Converged():
            raise CircuitDidNotConvergeError(
                f"El circuito no convergio con GD de {power_kw} kW en barra {bus}."
            )

    def remove_gd(self) -> None:
        """Elimina el generador GD si existe. Silencioso si no existe."""
        generators = [g.lower() for g in list(self._dss.Generators.AllNames())]
        if "gd" in generators:
            self._dss.Text.Command("Remove Generator.GD")

    def check_violations(self) -> Dict:
        """
        Verifica violaciones de voltaje, corriente y potencia del estado actual.

        Returns dict con claves "voltage", "current", "power", cada una siendo
        una lista de violaciones. Lista vacia = sin violaciones.
        """
        self._assert_loaded()
        voltage_violations: List[Dict] = []
        current_violations: List[Dict] = []
        power_violations: List[Dict] = []

        # --- Voltaje -------------------------------------------------------
        for bus in self._dss.Circuit.AllBusNames():
            self._dss.Circuit.SetActiveBus(bus)
            pu_mag_ang = self._dss.Bus.puVmagAngle()
            nodes = self._dss.Bus.Nodes()
            for idx, node in enumerate(nodes):
                mag = round(pu_mag_ang[2 * idx], 6)
                if mag < 0.95 or mag > 1.05:
                    voltage_violations.append(
                        {
                            "bus_phase": f"{bus}.{node}",
                            "voltage_pu": mag,
                            "limit_lower": 0.95,
                            "limit_upper": 1.05,
                            "exceeded": "lower" if mag < 0.95 else "upper",
                        }
                    )

        # --- Corriente y potencia ------------------------------------------
        for name in list(self._dss.Lines.AllNames()):
            self._dss.Lines.Name(name)
            self._dss.Circuit.SetActiveElement(f"Line.{name}")
            mags = self._dss.CktElement.CurrentsMagAng()[::2]

            norm_amps = self._dss.Lines.EmergAmps() or 1.0
            bus1 = self._dss.Lines.Bus1().split(".")[0]
            self._dss.Circuit.SetActiveBus(bus1)
            kv_base = self._dss.Bus.kVBase() or 1.0
            n_phases = self._dss.Lines.Phases()
            kv = kv_base * 1.732 if n_phases > 1 else kv_base
            s_nom = kv * norm_amps

            for i, mag in enumerate(mags):
                if mag > norm_amps:
                    current_violations.append(
                        {
                            "line": name,
                            "phase": i + 1,
                            "current_a": round(mag, 2),
                            "limit_a": round(norm_amps, 2),
                            "exceeded_pct": round(
                                (mag / norm_amps - 1) * 100, 2
                            ),
                        }
                    )
                s_real = (1.732 * kv * mag) if n_phases > 1 else (kv * mag)
                if s_real > s_nom:
                    power_violations.append(
                        {
                            "line": name,
                            "phase": i + 1,
                            "power_kva": round(s_real, 2),
                            "limit_kva": round(s_nom, 2),
                            "exceeded_pct": round(
                                (s_real / s_nom - 1) * 100, 2
                            ),
                        }
                    )

        return {
            "voltage": voltage_violations,
            "current": current_violations,
            "power": power_violations,
        }

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    def _assert_loaded(self) -> None:
        if not self._circuit_loaded:
            raise CircuitNotLoadedError(
                "No hay un circuito cargado. Llame a load_circuit() primero."
            )

    def _get_circuit_info(self) -> Dict:
        return {
            "name": self._dss.Circuit.Name(),
            "num_buses": len(self._dss.Circuit.AllBusNames()),
            "num_elements": self._dss.Circuit.NumCktElements(),
            "converged": bool(self._dss.Solution.Converged()),
            "total_power_kw": round(
                self._dss.Circuit.TotalPower()[0] / 1000, 4
            ),
            "total_power_kvar": round(
                self._dss.Circuit.TotalPower()[1] / 1000, 4
            ),
        }


# ---------------------------------------------------------------------------
# Funciones de preprocesamiento (nivel modulo, reutilizables sin instanciar)
# ---------------------------------------------------------------------------


def _preprocess(content: str) -> str:
    """
    Limpia el contenido DSS eliminando referencias externas no resolubles
    en el servidor (IEEELineCodes, buscoords) y parametros invalidos (basekv).
    """
    # Eliminar redirect a IEEELineCodes (se pasan por separado via linecodes_dss)
    content = re.sub(
        r"(?im)^.*redirect\s+.*ieeelinecodes.*\.dss.*$", "", content
    )
    # Eliminar referencia a archivos de coordenadas (no afecta la simulacion)
    content = re.sub(r"(?im)^.*buscoords.*\.csv.*$", "", content)
    # Eliminar el parametro 'basekv' invalido en definiciones de linecodes
    content = re.sub(
        r"(new\s+linecode[^\n]*)\bbasekv\s*=\s*[\d.]+\s*",
        r"\1",
        content,
        flags=re.IGNORECASE,
    )
    # Eliminar 'Clear' standalone — lo emitimos nosotros antes del Compile.
    # Si hay linecodes prependidos, un Clear interno borraria esas definiciones.
    content = re.sub(r"(?im)^\s*clear\s*$", "", content)
    # Eliminar 'Set DefaultBaseFrequency=...' — aparece antes de New Circuit en
    # archivos IEEE de referencia y OpenDSS (#265) requiere un circuito activo.
    # 60 Hz es el valor por defecto; lo sobreescribimos desde Python si es necesario.
    content = re.sub(
        r"(?im)^\s*set\s+defaultbasefrequency\s*=\s*[\d.]+\s*$", "", content
    )
    return content
