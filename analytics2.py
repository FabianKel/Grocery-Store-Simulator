import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple
from matplotlib.patches import Patch
from pathlib import Path
import random

# Establecer estilo de matplotlib para mejor visualización
plt.style.use('ggplot')

# --- CONFIGURACIÓN Y MOCKS ---
# Estos valores deben coincidir con los que usas en tu sistema
BASE_RESULTS_DIR = "resultados_simulacion_combinados"
SOURCE_RESULTS_DIR = "resultados_simulacion"


SUBDIRS = {
    'comparacion_tipo': 'comparacion_tipo',
    'longitud_colas': 'longitud_colas',
    'utilizacion_cajeros': 'utilizacion_cajeros',
    'tiempos_cliente': 'tiempos_cliente'
}
COLORS = {
    'familia': '#3498db',    # Azul
    'solo': '#e74c3c',       # Rojo
    'cajero_izq': '#2ecc71', # Verde esmeralda
    'cajero_der': '#f39c12'  # Amarillo/Naranja
}

def mock_save_csv(data: List[Dict], filepath: str):
    """Implementación simulada de save_csv para fines de prueba."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(data).to_csv(filepath, index=False)
    # print(f"  [MOCK] CSV guardado en: {filepath}")

def mock_create_files(base_dir: str):
    """
    Crea archivos CSV simulados con la estructura de directorios del usuario.
    Esto permite probar la función de rastreo y combinación.
    """
    base_path = Path(SOURCE_RESULTS_DIR)

    print(f"Creando archivos de ejemplo en: {base_path}")
    
    # 2 Simulaciones diferentes
    simulations = [
        {'dia': 'domingo', 'hora': 10, 'timestamp': 'ts_dom_10'},
        {'dia': 'lunes', 'hora': 15, 'timestamp': 'ts_lun_15'}
    ]

    for sim in simulations:
        # --- Datos de Clientes (para comparacion_tipo) ---
        # Simulación 1: Familia tarda más
        df_clients1 = pd.DataFrame({
            'id': range(1, 11),
            'tipo': ['familia'] * 5 + ['solo'] * 5,
            'total_time': [random.uniform(100, 150) for _ in range(5)] + [random.uniform(50, 80) for _ in range(5)],
            'items_total': [15] * 5 + [5] * 5
        })
        # Simulación 2: Solo tarda más
        df_clients2 = pd.DataFrame({
            'id': range(11, 21),
            'tipo': ['familia'] * 5 + ['solo'] * 5,
            'total_time': [random.uniform(60, 90) for _ in range(5)] + [random.uniform(120, 180) for _ in range(5)],
            'items_total': [10] * 5 + [20] * 5
        })

        if sim['dia'] == 'domingo':
            df_clients = df_clients1
        else:
            df_clients = df_clients2

        path_comp_tipo = base_path / SUBDIRS['comparacion_tipo'] / f"{sim['dia']}_{sim['hora']}h_{sim['timestamp']}_comparacion_tipo.csv"
        path_long_colas = base_path / SUBDIRS['longitud_colas'] / f"{sim['dia']}_{sim['hora']}h_{sim['timestamp']}_longitud_colas.csv"
        path_util_cajeros = base_path / SUBDIRS['utilizacion_cajeros'] / f"{sim['dia']}_{sim['hora']}h_{sim['timestamp']}_utilizacion_cajeros.csv"

        # Guardar comparacion_tipo.csv
        mock_save_csv(df_clients.to_dict('records'), str(path_comp_tipo))
        
        # --- Datos de Colas y Utilización (para métricas de línea) ---
        ticks = np.arange(0, 100, 5)
        
        # Simulación 1: Cola izquierda más larga
        if sim['dia'] == 'domingo':
            len_izq = np.array([random.randint(1, 4) for _ in ticks])
            len_der = np.array([random.randint(0, 2) for _ in ticks])
            util_izq = np.array([random.choice([0, 1]) for _ in ticks])
            util_der = np.array([random.choice([0, 1]) for _ in ticks])
        # Simulación 2: Utilización derecha más alta
        else:
            len_izq = np.array([random.randint(0, 2) for _ in ticks])
            len_der = np.array([random.randint(1, 3) for _ in ticks])
            util_izq = np.array([0 if x < 0.3 else 1 for x in np.random.rand(len(ticks))]) # Utilización más baja
            util_der = np.array([0 if x < 0.7 else 1 for x in np.random.rand(len(ticks))]) # Utilización más alta


        # Guardar longitud_colas.csv
        df_queue = pd.DataFrame({
            'cajero': ['Cajero_1_5'] * len(ticks) + ['Cajero_1_10'] * len(ticks),
            'tick': list(ticks) * 2,
            'longitud': list(len_izq) + list(len_der)
        })
        mock_save_csv(df_queue.to_dict('records'), str(path_long_colas))
        
        # Guardar utilizacion_cajeros.csv
        df_util = pd.DataFrame({
            'cajero': ['Cajero_1_5'] * len(ticks) + ['Cajero_1_10'] * len(ticks),
            'tick': list(ticks) * 2,
            'utilizacion': list(util_izq) + list(util_der)
        })
        mock_save_csv(df_util.to_dict('records'), str(path_util_cajeros))


class MetricsPlotter:
    """Clase para generar y combinar gráficos de métricas de simulación."""
    def __init__(self, subdirs, colors, save_csv_func):
        self.subdirs = subdirs
        self.colors = colors
        self.save_csv = save_csv_func

    # --- UTILIDAD: Carga y Combinación de CSVs ---
    def _load_and_combine_csvs(self, filepaths: List[Path]) -> pd.DataFrame:
        """Carga y combina múltiples CSVs de métricas en un solo DataFrame."""
        all_data = []
        for fp in filepaths:
            try:
                # Usar la ruta relativa (o parte del nombre) como ID de simulación
                # Esto asume que el nombre del archivo contiene info única
                sim_label = fp.stem.replace("_comparacion_tipo", "").replace("_longitud_colas", "").replace("_utilizacion_cajeros", "")
                df = pd.read_csv(fp)
                df['simulacion_id'] = sim_label
                all_data.append(df)
            except FileNotFoundError:
                print(f"⚠️ Archivo no encontrado: {fp}")
            except Exception as e:
                print(f"⚠️ Error al leer el archivo {fp}: {e}")
        
        if not all_data:
            return pd.DataFrame()
            
        return pd.concat(all_data, ignore_index=True)

    # ----------------------------------------------------------------------
    # 1. FUNCIÓN DE COMPARACIÓN: Tiempo Promedio por Tipo de Cliente (Barras Agrupadas)
    # ----------------------------------------------------------------------
    
    def plot_combined_time_by_type(self, filepaths: List[Path], dia, hora, timestamp):
        """
        Gráfica de barras combinada: compara el tiempo promedio en tienda 
        por tipo de cliente (Solo vs Familia) a través de múltiples simulaciones.
        Cada simulación tendrá un grupo de barras (Familia y Solo).
        """
        if not filepaths:
            print("⚠️ No se proporcionaron rutas de archivos para combinar: comparacion_tipo.")
            return

        df = self._load_and_combine_csvs(filepaths)
        
        if df.empty or 'total_time' not in df.columns:
            print("⚠️ No hay datos válidos para la combinación de métricas de clientes.")
            return

        # 1. Limpieza y filtrado
        df = df.dropna(subset=['total_time'])
        
        # 2. Agrupación: Por simulación, luego por tipo de cliente
        grouped = df.groupby(['simulacion_id', 'tipo']).agg(
            promedio=('total_time', 'mean'),
            std=('total_time', 'std'),
            conteo=('total_time', 'count')
        ).reset_index()
        
        simulaciones = grouped['simulacion_id'].unique()
        n_sims = len(simulaciones)
        
        if n_sims == 0:
            print("⚠️ No hay simulaciones con datos completados para comparación de tipo.")
            return

        # --- Preparación de la Gráfica de Barras Agrupadas ---
        # Aseguramos que la carpeta de resultados combinados exista
        combined_output_dir = Path(BASE_RESULTS_DIR) / self.subdirs['comparacion_tipo']
        combined_output_dir.mkdir(parents=True, exist_ok=True)
        filename = combined_output_dir / f"{dia}_{hora}h_{timestamp}_COMPARACION_TIPO_COMBINADA.png"
        
        fig, ax = plt.subplots(figsize=(max(10, 2 * n_sims + 6), 7)) # Ajuste dinámico del tamaño
        
        # Parámetros de ploteo
        width = 0.35  # Ancho de las barras
        x = np.arange(n_sims) # Posiciones centrales de los grupos (simulaciones)

        # 3. Datos por tipo (Familia y Solo)
        solo_data = grouped[grouped['tipo'] == 'solo']
        familia_data = grouped[grouped['tipo'] == 'familia']
        
        # Reordenar y rellenar con 0 si faltan datos en alguna simulación
        solo_data = solo_data.set_index('simulacion_id').reindex(simulaciones).fillna({'promedio': 0, 'std': 0, 'conteo': 0}).reset_index()
        familia_data = familia_data.set_index('simulacion_id').reindex(simulaciones).fillna({'promedio': 0, 'std': 0, 'conteo': 0}).reset_index()

        # Ploteo de Barras
        
        # 3a. Barras Familia
        bars_familia = ax.bar(x - width/2, familia_data['promedio'], width, 
                              label='Familia', color=self.colors['familia'],
                              edgecolor='black', linewidth=1.5)
        ax.errorbar(x - width/2, familia_data['promedio'], yerr=familia_data['std'], 
                    fmt='none', ecolor='black', capsize=5)

        # 3b. Barras Solo
        bars_solo = ax.bar(x + width/2, solo_data['promedio'], width, 
                           label='Solo', color=self.colors['solo'],
                           edgecolor='black', linewidth=1.5)
        ax.errorbar(x + width/2, solo_data['promedio'], yerr=solo_data['std'], 
                    fmt='none', ecolor='black', capsize=5)
        
        # 4. Etiquetas y Títulos
        
        # Añadir valores y conteos encima de las barras (Familia)
        for bar, avg, count in zip(bars_familia, familia_data['promedio'], familia_data['conteo']):
            if avg > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                        f'{avg:.1f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
                ax.text(bar.get_x() + bar.get_width()/2, 1, 
                        f'n={int(count)}', ha='center', va='bottom', fontsize=8, color='black')

        # Añadir valores y conteos encima de las barras (Solo)
        for bar, avg, count in zip(bars_solo, solo_data['promedio'], solo_data['conteo']):
            if avg > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                        f'{avg:.1f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
                ax.text(bar.get_x() + bar.get_width()/2, 1, 
                        f'n={int(count)}', ha='center', va='bottom', fontsize=8, color='black')

        ax.set_ylabel('Tiempo promedio en tienda (ticks)', fontsize=13, fontweight='bold')
        ax.set_title('Comparación de Tiempo Promedio en Tienda por Tipo (Múltiples Simulaciones)', fontsize=16, fontweight='bold', pad=20)
        
        # Etiquetas de las simulaciones en el eje X
        ax.set_xticks(x)
        ax.set_xticklabels(simulaciones, rotation=45, ha="right", fontsize=11)
        ax.set_xlabel('Simulación ID (Día_Hora_Timestamp)', fontsize=13, fontweight='bold')
        
        ax.legend(loc='upper right', fontsize=12, framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Gráfica de comparación de tipo (barras) guardada: {filename}")
        
    # ----------------------------------------------------------------------
    # 2. FUNCIÓN DE COMPARACIÓN: Métricas de Línea (Colas y Utilización)
    # ----------------------------------------------------------------------

    def plot_combined_line_metrics(self, filepaths: List[Path], metric_name: str, y_label: str, title: str, path_subdir: str, dia, hora, timestamp):
        """
        Combina y grafica métricas de series de tiempo (longitud de cola o utilización)
        en subgráficos individuales (uno encima de otro) para cada simulación.
        
        Args:
            filepaths (List[Path]): Lista de rutas a los archivos CSV de la métrica (ej. longitud_colas.csv).
            metric_name (str): Nombre de la columna que contiene la métrica (ej. 'longitud' o 'utilizacion').
            y_label (str): Etiqueta del eje Y.
            title (str): Título principal del gráfico.
            path_subdir (str): Nombre de la subcarpeta donde guardar el resultado.
        """
        if not filepaths:
            print(f"⚠️ No se proporcionaron rutas de archivos para combinar la métrica '{metric_name}'.")
            return

        # --- Creación del DataFrame Combinado ---
        df = self._load_and_combine_csvs(filepaths)
        
        if df.empty or metric_name not in df.columns:
            print(f"⚠️ No hay datos válidos para la combinación de la métrica '{metric_name}'.")
            return
            
        simulaciones = df['simulacion_id'].unique()
        n_sims = len(simulaciones)
        
        if n_sims == 0:
            print(f"⚠️ No hay simulaciones con datos para '{metric_name}'.")
            return

        # --- Preparación de la Figura con Subgráficos ---
        combined_output_dir = Path(BASE_RESULTS_DIR) / self.subdirs[path_subdir]
        combined_output_dir.mkdir(parents=True, exist_ok=True)
        filename = combined_output_dir / f"{dia}_{hora}h_{timestamp}_COMPARACION_{metric_name.upper()}_COMBINADA.png"

        # Crear una figura con una columna y N filas (una fila por simulación)
        fig, axes = plt.subplots(n_sims, 1, figsize=(14, 5 * n_sims), sharex=True)
        # Si solo hay una simulación, axes no es un array, lo forzamos
        if n_sims == 1:
            axes = np.array([axes])
        
        fig.suptitle(title, fontsize=18, fontweight='bold', y=1.02)
        
        # --- Ploteo de Subgráficos ---
        
        for idx, sim_id in enumerate(simulaciones):
            ax = axes[idx]
            sim_df = df[df['simulacion_id'] == sim_id]
            
            cajeros = sim_df['cajero'].unique()
            
            # Ordenar cajeros por columna para identificar 'Izquierda' y 'Derecha'
            cajeros_sorted = []
            for cid in cajeros:
                try:
                    parts = cid.split('_')
                    # Asumiendo el formato Cajero_Fila_Columna, donde Columna define I/D
                    col = int(parts[2]) 
                    cajeros_sorted.append((col, cid))
                except Exception:
                    cajeros_sorted.append((0, cid)) # Fallback si el nombre no es el esperado
            cajeros_sorted.sort(key=lambda x: x[0])
            
            
            for c_idx, (col, cajero_id) in enumerate(cajeros_sorted):
                cajero_df = sim_df[sim_df['cajero'] == cajero_id]
                
                # Asignar color y etiqueta (asumiendo 2 cajeros)
                if c_idx == 0:
                    label = "Cajero Izquierda"
                    color = self.colors['cajero_izq']
                else:
                    label = "Cajero Derecha"
                    color = self.colors['cajero_der']
                
                ax.plot(cajero_df['tick'], cajero_df[metric_name], 
                        label=label, linewidth=2, color=color, alpha=0.8)

                # Calcular y mostrar estadísticas
                avg_metric = np.mean(cajero_df[metric_name])
                max_metric = np.max(cajero_df[metric_name])
                
                # Mostrar estadísticas en la esquina superior izquierda
                stat_text = f"{label}: Promedio={avg_metric:.2f}, Máximo={max_metric:.0f}"
                y_pos = 0.95 - c_idx * 0.1
                ax.text(0.01, y_pos, stat_text,
                        transform=ax.transAxes, fontsize=10, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.5', facecolor=color, alpha=0.3, edgecolor='black'))

            
            # Configuración del subgráfico
            ax.set_title(f'Simulación: {sim_id}', fontsize=14, fontweight='bold', loc='left', pad=10)
            ax.set_ylabel(y_label, fontsize=11)
            
            # Líneas de referencia específicas para Longitud de Colas
            if metric_name == 'longitud':
                ax.axhline(y=2, color='orange', linestyle=':', alpha=0.6, linewidth=1.5, label='Umbral 2')
                ax.axhline(y=4, color='red', linestyle=':', alpha=0.6, linewidth=1.5, label='Crítico 4')
            # Líneas de referencia específicas para Utilización
            elif metric_name == 'utilizacion':
                ax.set_ylim(-0.1, 1.1)
                ax.set_yticks([0, 1])
                ax.set_yticklabels(['Libre', 'Ocupado'])

            ax.legend(loc='upper right', fontsize=10, framealpha=0.9)
            ax.grid(alpha=0.3, linestyle='--')
            
        # Configuración del eje X global
        axes[-1].set_xlabel('Tick de simulación', fontsize=13, fontweight='bold')
        
        plt.tight_layout(rect=[0, 0, 1, 0.98]) # Ajustar para el suptitle
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Gráfica combinada de líneas guardada: {filename}")


def run_combined_plots(base_dir: str):
    """
    Función principal que rastrea los archivos CSV y llama a las funciones de ploteo combinadas.
    """
    base_path = Path(SOURCE_RESULTS_DIR)
    plotter = MetricsPlotter(SUBDIRS, COLORS, mock_save_csv)
    
    # Usar un timestamp genérico para el archivo combinado
    combined_dia = 'COMBINADO'
    combined_hora = 'ALL'
    combined_timestamp = 'SUMMARY' 

    print("\n--- INICIANDO RASTREO Y PLOTEO COMBINADO ---")
    
    # ----------------------------------------------------
    # 1. Comparación de Tipo (Barras Agrupadas)
    # ----------------------------------------------------
    # Busca recursivamente todos los archivos que terminen en *_comparacion_tipo.csv
    comp_tipo_files = list(base_path.glob(f"**/*_comparacion_tipo.csv"))
    print(f"\nEncontrados {len(comp_tipo_files)} archivos para Comparación de Tipo.")
    
    plotter.plot_combined_time_by_type(comp_tipo_files, combined_dia, combined_hora, combined_timestamp)

    # ----------------------------------------------------
    # 2. Longitud de Colas (Subgráficos)
    # ----------------------------------------------------
    # Busca recursivamente todos los archivos que terminen en *_longitud_colas.csv
    long_colas_files = list(base_path.glob(f"**/*_longitud_colas.csv"))
    print(f"\nEncontrados {len(long_colas_files)} archivos para Longitud de Colas.")
    
    plotter.plot_combined_line_metrics(
        filepaths=long_colas_files, 
        metric_name='longitud', 
        y_label='Número de clientes en fila', 
        title='Comparación de Longitud de Colas (Subgráficos por Simulación)', 
        path_subdir='longitud_colas', 
        dia=combined_dia, 
        hora=combined_hora, 
        timestamp=combined_timestamp
    )

    # ----------------------------------------------------
    # 3. Utilización de Cajeros (Subgráficos)
    # ----------------------------------------------------
    # Busca recursivamente todos los archivos que terminen en *_utilizacion_cajeros.csv
    util_cajeros_files = list(base_path.glob(f"**/*_utilizacion_cajeros.csv"))
    print(f"\nEncontrados {len(util_cajeros_files)} archivos para Utilización de Cajeros.")

    plotter.plot_combined_line_metrics(
        filepaths=util_cajeros_files, 
        metric_name='utilizacion', 
        y_label='Estado (1 = Ocupado, 0 = Libre)', 
        title='Comparación de Utilización de Cajeros (Subgráficos por Simulación)', 
        path_subdir='utilizacion_cajeros', 
        dia=combined_dia, 
        hora=combined_hora, 
        timestamp=combined_timestamp
    )
    
    print("\n--- PROCESO DE PLOTEO COMBINADO FINALIZADO ---")
    print(f"Los resultados combinados se guardaron en la carpeta: {BASE_RESULTS_DIR}")


if __name__ == '__main__':
    # 1. MOCK: Crear archivos de ejemplo para demostrar la funcionalidad
    # mock_create_files(BASE_RESULTS_DIR) 

    # 2. EJECUTAR: Encontrar y combinar los archivos
    run_combined_plots(BASE_RESULTS_DIR)

# La métrica 'tiempos_cliente' no se combinó porque no tiene una forma útil 
# de comparación directa entre simulaciones al nivel de cliente individual.