"""
Módulo de análisis y visualización para la simulación de supermercado.
Genera gráficas después de correr la simulación.
VERSIÓN MEJORADA - Solo gráficas útiles y claras
"""

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Para generar sin display
import numpy as np
from typing import List, Dict, Any
from datetime import datetime
import os, csv
from glob import glob

class SimulationAnalytics:
    """
    Clase para analizar y visualizar resultados de la simulación.
    """
    
    def __init__(self, output_dir: str = "simulation_results"):
        """
        Inicializa el analizador.
        
        Args:
            output_dir: Directorio donde guardar las gráficas
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        

        self.subdirs = {
            "comparacion_tipo": os.path.join(output_dir, "comparacion_tipo"),
            "longitud_colas": os.path.join(output_dir, "longitud_colas"),
            "tiempos_cliente": os.path.join(output_dir, "tiempos_cliente"),
            "utilizacion_cajeros": os.path.join(output_dir, "utilizacion_cajeros")
        }
        for path in self.subdirs.values():
            os.makedirs(path, exist_ok=True)

        # Configuración de estilo
        plt.style.use('seaborn-v0_8-darkgrid')
        self.colors = {
            'familia': '#FF6B6B',
            'solo': '#4ECDC4',
            'primary': '#2E86DE',
            'secondary': '#FF7675',
            'cajero_izq': '#3498db',  # Azul
            'cajero_der': '#e74c3c'   # Rojo
        }
    
    def save_all_charts(self, simulation_data: Dict[str, Any], dia: str, hora: int):
        """
        Genera y guarda todas las gráficas.
        
        Args:
            simulation_data: Diccionario con datos de la simulación
            prefix: Prefijo para nombres de archivos
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"{dia}_{hora}h_{timestamp}"
        # base_name = f"{prefix}_{timestamp}" if prefix else timestamp
        
        print(f"📊 Generando gráficas en {self.output_dir}/...")
        
        # 1. Tiempo total por cliente
        self.plot_client_times(
            simulation_data.get('client_metrics', []),
            dia, hora, timestamp
        )
        
        # 2. Utilización de cajeros
        if 'checkout_utilization' in simulation_data:
            self.plot_checkout_utilization(
                simulation_data['checkout_utilization'],
            dia, hora, timestamp
        )
        
        # 3. Longitud de colas
        if 'queue_lengths' in simulation_data:
            self.plot_queue_lengths(
                simulation_data['queue_lengths'],
                dia, hora, timestamp
            )
        
        # 4. Comparación por tipo (solo barras, sin boxplot)
        self.plot_time_by_type(
            simulation_data.get('client_metrics', []),
            dia, hora, timestamp
        )

        self.generate_combined_charts(timestamp)
        print(f"✅ Gráficas generadas para {dia} {hora}:00 (timestamp {timestamp})")
        return timestamp
        
        # print(f"✅ Gráficas guardadas con prefijo: {base_name}")
        # return base_name

    def save_csv(self, data: List[Dict], filename: str):
        """Guarda lista de diccionarios en CSV."""
        if not data:
            return
        keys = sorted(data[0].keys())
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)

    def plot_client_times(self, client_metrics: List[Dict], dia, hora, timestamp):
        """
        Gráfica de barras: tiempo total por cliente.
        """

        path_dir = self.subdirs['tiempos_cliente']
        filename = os.path.join(path_dir, f"{dia}_{hora}h_{timestamp}_tiempos_cliente.png")
        csvname = filename.replace(".png", ".csv")
        self.save_csv(client_metrics, csvname)

        # Filtrar clientes que terminaron
        completed = [c for c in client_metrics if c.get('total_time') is not None]
        
        if not completed:
            print("⚠️  No hay clientes completados para graficar")
            return
        
        fig, ax = plt.subplots(figsize=(14, 7))
        
        ids = [c['id'] for c in completed]
        times = [c['total_time'] for c in completed]
        items = [c.get('items_total', 0) for c in completed]
        tipos = [c.get('tipo', 'solo') for c in completed]
        
        # Colores según tipo
        colors = [self.colors.get(t, '#95a5a6') for t in tipos]
        
        bars = ax.bar(range(len(ids)), times, color=colors, alpha=0.85, edgecolor='black', linewidth=1.5)
        
        # Añadir labels con número de items
        for i, (bar, item_count) in enumerate(zip(bars, items)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                   f'{item_count} items',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')
        
        ax.set_xlabel('Cliente ID', fontsize=13, fontweight='bold')
        ax.set_ylabel('Tiempo total en tienda (ticks)', fontsize=13, fontweight='bold')
        ax.set_title('Tiempo Total en Tienda por Cliente', fontsize=16, fontweight='bold', pad=20)
        ax.set_xticks(range(len(ids)))
        ax.set_xticklabels([f"Cliente {id}" for id in ids], fontsize=10, rotation=45, ha='right')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Leyenda
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=self.colors['familia'], edgecolor='black', label='Familia'),
            Patch(facecolor=self.colors['solo'], edgecolor='black', label='Solo')
        ]
        ax.legend(handles=legend_elements, loc='upper left', fontsize=11, framealpha=0.9)
        
        # Estadística en el gráfico
        avg_time = np.mean(times)
        ax.axhline(y=avg_time, color='red', linestyle='--', linewidth=2, alpha=0.7, label=f'Promedio: {avg_time:.1f} ticks')
        ax.legend(handles=legend_elements + [plt.Line2D([0], [0], color='red', linestyle='--', linewidth=2, label=f'Promedio: {avg_time:.1f}')], 
                 loc='upper left', fontsize=11, framealpha=0.9)
        
        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ {filename}")
    
    def plot_checkout_utilization(self, utilization_data: Dict, dia, hora, timestamp):
        """
        Gráfica de línea: utilización de cajeros en el tiempo.
        MEJORADO: Identifica claramente cajero izquierdo vs derecho
        """
        if not utilization_data:
            print("⚠️  No hay datos de cajeros")
            return
        
        path_dir = self.subdirs['utilizacion_cajeros']
        filename = os.path.join(path_dir, f"{dia}_{hora}h_{timestamp}_utilizacion_cajeros.png")
        csvname = filename.replace(".png", ".csv")

        # Aplanar datos para CSV
        flat_data = []
        for cid, d in utilization_data.items():
            for tick, util in zip(d['ticks'], d['utilization']):
                flat_data.append({'cajero': cid, 'tick': tick, 'utilizacion': util})
        self.save_csv(flat_data, csvname)

        fig, ax = plt.subplots(figsize=(14, 7))
        
        # Ordenar cajeros por columna (izquierda = menor col, derecha = mayor col)
        cajeros_sorted = []
        for checkout_id, data in utilization_data.items():
            # Extraer posición del nombre "Cajero_9_10" -> fila=9, col=10
            parts = checkout_id.split('_')
            if len(parts) >= 3:
                fila = int(parts[1])
                col = int(parts[2])
                cajeros_sorted.append((col, checkout_id, data))
        
        cajeros_sorted.sort(key=lambda x: x[0])  # Ordenar por columna
        
        # Asignar nombres claros
        labels = []
        for idx, (col, checkout_id, data) in enumerate(cajeros_sorted):
            if idx == 0:
                label = f"Cajero Izquierda (col {col})"
                color = self.colors['cajero_izq']
            else:
                label = f"Cajero Derecha (col {col})"
                color = self.colors['cajero_der']
            
            labels.append(label)
            ticks = data['ticks']
            utilization = data['utilization']
            
            ax.plot(ticks, utilization, label=label, linewidth=2.5, 
                   color=color, marker='o', markersize=4, markevery=5)
        
        ax.set_xlabel('Tick de simulación', fontsize=13, fontweight='bold')
        ax.set_ylabel('Estado (1 = Ocupado, 0 = Libre)', fontsize=13, fontweight='bold')
        ax.set_title('Utilización de Cajeros en el Tiempo', fontsize=16, fontweight='bold', pad=20)
        ax.set_ylim(-0.1, 1.1)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(['Libre', 'Ocupado'])
        ax.legend(loc='upper right', fontsize=12, framealpha=0.95)
        ax.grid(alpha=0.3, linestyle='--')
        
        # Calcular % de utilización y mostrarlo
        for idx, (col, checkout_id, data) in enumerate(cajeros_sorted):
            util_pct = np.mean(data['utilization']) * 100
            y_pos = 0.95 - idx * 0.08
            color = self.colors['cajero_izq'] if idx == 0 else self.colors['cajero_der']
            
            ax.text(0.02, y_pos, f'{labels[idx]}: {util_pct:.1f}% ocupado',
                   transform=ax.transAxes, fontsize=11, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor=color, alpha=0.3, edgecolor='black'))
        
        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ {filename}")
    
    def plot_queue_lengths(self, queue_data: Dict, dia, hora, timestamp):
        """
        Gráfica de línea: longitud de colas en el tiempo.
        MEJORADO: Identifica claramente cajero izquierdo vs derecho
        """
        if not queue_data:
            print("⚠️  No hay datos de colas")
            return
        
        path_dir = self.subdirs['longitud_colas']
        filename = os.path.join(path_dir, f"{dia}_{hora}h_{timestamp}_longitud_colas.png")
        csvname = filename.replace(".png", ".csv")

        flat_data = []
        for cid, d in queue_data.items():
            for tick, length in zip(d['ticks'], d['queue_length']):
                flat_data.append({'cajero': cid, 'tick': tick, 'longitud': length})
        self.save_csv(flat_data, csvname)

        fig, ax = plt.subplots(figsize=(14, 7))
        
        # Ordenar cajeros por columna
        cajeros_sorted = []
        for checkout_id, data in queue_data.items():
            parts = checkout_id.split('_')
            if len(parts) >= 3:
                fila = int(parts[1])
                col = int(parts[2])
                cajeros_sorted.append((col, checkout_id, data))
        
        cajeros_sorted.sort(key=lambda x: x[0])
        
        # Graficar
        for idx, (col, checkout_id, data) in enumerate(cajeros_sorted):
            if idx == 0:
                label = f"Cajero Izquierda (col {col})"
                color = self.colors['cajero_izq']
            else:
                label = f"Cajero Derecha (col {col})"
                color = self.colors['cajero_der']
            
            ticks = data['ticks']
            lengths = data['queue_length']
            
            ax.plot(ticks, lengths, label=label, linewidth=2.5, 
                   color=color, marker='s', markersize=4, markevery=5)
            
            # Calcular estadísticas
            avg_queue = np.mean(lengths)
            max_queue = np.max(lengths)
            
            # Mostrar estadísticas
            y_pos = 0.95 - idx * 0.08
            ax.text(0.02, y_pos, f'{label}: Promedio = {avg_queue:.1f}, Máximo = {max_queue}',
                   transform=ax.transAxes, fontsize=11, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor=color, alpha=0.3, edgecolor='black'))
        
        ax.set_xlabel('Tick de simulación', fontsize=13, fontweight='bold')
        ax.set_ylabel('Número de clientes en fila', fontsize=13, fontweight='bold')
        ax.set_title('Longitud de Colas en el Tiempo', fontsize=16, fontweight='bold', pad=20)
        ax.legend(loc='upper right', fontsize=12, framealpha=0.95)
        ax.grid(alpha=0.3, linestyle='--')
        
        # Líneas de referencia
        ax.axhline(y=2, color='orange', linestyle='--', alpha=0.6, linewidth=2, label='Umbral: 2 personas')
        ax.axhline(y=4, color='red', linestyle='--', alpha=0.6, linewidth=2, label='Crítico: 4 personas')
        
        # Actualizar leyenda
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles, labels, loc='upper right', fontsize=11, framealpha=0.95)
        
        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ {filename}")
    
    def plot_time_by_type(self, client_metrics: List[Dict],dia, hora, timestamp):
        """
        Gráfica de barras: comparación de tiempos por tipo de cliente.
        SIMPLIFICADO: Solo barras con promedios, sin boxplot
        """

        path_dir = self.subdirs['comparacion_tipo']
        filename = os.path.join(path_dir, f"{dia}_{hora}h_{timestamp}_comparacion_tipo.png")
        csvname = filename.replace(".png", ".csv")
        self.save_csv(client_metrics, csvname)
        completed = [c for c in client_metrics if c.get('total_time') is not None]
        
        if not completed:
            print("⚠️  No hay clientes completados")
            return
        
        # Separar por tipo
        familia_times = [c['total_time'] for c in completed if c.get('tipo') == 'familia']
        solo_times = [c['total_time'] for c in completed if c.get('tipo') == 'solo']
        
        fig, ax = plt.subplots(figsize=(10, 7))
        
        # Preparar datos
        tipos = []
        promedios = []
        errors = []
        counts = []
        
        if familia_times:
            tipos.append('Familia')
            promedios.append(np.mean(familia_times))
            errors.append(np.std(familia_times))
            counts.append(len(familia_times))
        
        if solo_times:
            tipos.append('Solo')
            promedios.append(np.mean(solo_times))
            errors.append(np.std(solo_times))
            counts.append(len(solo_times))
        
        if not tipos:
            print("⚠️  No hay datos para comparar")
            return
        
        # Crear barras
        x_pos = np.arange(len(tipos))
        colors_list = [self.colors['familia'], self.colors['solo']][:len(tipos)]
        
        bars = ax.bar(x_pos, promedios, 
                     color=colors_list,
                     alpha=0.85, edgecolor='black', linewidth=2, width=0.6)
        
        # Añadir barras de error
        ax.errorbar(x_pos, promedios, yerr=errors, 
                   fmt='none', ecolor='black', capsize=10, capthick=2, elinewidth=2)
        
        # Añadir valores encima de las barras
        for i, (bar, val, err, count) in enumerate(zip(bars, promedios, errors, counts)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + err + 2,
                   f'{val:.1f} ticks\n(n={count})',
                   ha='center', va='bottom', fontsize=12, fontweight='bold')
        
        ax.set_ylabel('Tiempo promedio en tienda (ticks)', fontsize=13, fontweight='bold')
        ax.set_title('Comparación: Tiempo Promedio por Tipo de Cliente', fontsize=16, fontweight='bold', pad=20)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(tipos, fontsize=13, fontweight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Añadir leyenda con interpretación
        ax.text(0.98, 0.97, 'Las barras de error\nmuestran la desviación\nestándar', 
               transform=ax.transAxes, fontsize=10, 
               verticalalignment='top', horizontalalignment='right',
               bbox=dict(boxstyle='round,pad=0.8', facecolor='wheat', alpha=0.7, edgecolor='black'))
        
        plt.tight_layout()
        plt.savefig(filename, dpi=300)
        plt.close()
        print(f"  ✓ {filename}")

    def generate_combined_charts(self, timestamp):
        """
        Busca gráficas con distinto día/hora pero mismo timestamp y genera una general.
        """
        for tipo, path in self.subdirs.items():
            csvs = glob(os.path.join(path, f"*_{timestamp}_*.csv"))
            if len(csvs) <= 1:
                continue

            print(f"🔁 Combinando {len(csvs)} CSVs en {tipo} ({timestamp})...")
            combined_data = []
            for csvfile in csvs:
                with open(csvfile, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    combined_data.extend(list(reader))

            # Guardar combinado
            combined_csv = os.path.join(path, f"{timestamp}_general.csv")
            self.save_csv(combined_data, combined_csv)

            # Generar gráfica combinada básica
            fig, ax = plt.subplots(figsize=(10, 6))
            if tipo == 'comparacion_tipo':
                tipos = {}
                for row in combined_data:
                    tipo_cliente = row.get('tipo', 'desconocido')
                    if row.get('total_time'):
                        tipos.setdefault(tipo_cliente, []).append(float(row['total_time']))
                means = {t: np.mean(v) for t, v in tipos.items()}
                ax.bar(means.keys(), means.values(), color='gray')
                ax.set_title(f"Comparación general ({timestamp})")
            elif tipo == 'longitud_colas':
                for row in combined_data[:3000]:
                    ax.scatter(row['tick'], row['longitud'], alpha=0.3)
                ax.set_title(f"Longitud de colas (general)")
            elif tipo == 'utilizacion_cajeros':
                for row in combined_data[:3000]:
                    ax.scatter(row['tick'], row['utilizacion'], alpha=0.3)
                ax.set_title(f"Utilización general")
            elif tipo == 'tiempos_cliente':
                if 'total_time' in combined_data[0]:
                    times = [float(r['total_time']) for r in combined_data if r.get('total_time')]
                    ax.hist(times, bins=20, color='gray', alpha=0.7)
                    ax.set_title(f"Distribución de tiempos cliente (general)")
            plt.tight_layout()
            plt.savefig(os.path.join(path, f"{timestamp}_general.png"), dpi=300)
            plt.close()
            print(f"  ✅ {tipo}: general combinada generada")
            
# Función auxiliar para usar desde la API
def generate_charts_from_simulation(sim, dia, hora, output_dir="simulation_results"):
    """
    Genera todas las gráficas desde un objeto Simulation.
    
    Args:
        sim: Objeto Simulation después de correr
        output_dir: Directorio de salida
        prefix: Prefijo para archivos
    
    Returns:
        str: Nombre base de los archivos generados
    """
    from api import serialize_simulation_state
    analytics = SimulationAnalytics(output_dir=output_dir)
    state = serialize_simulation_state(sim)

    # Recopilar datos
    data = {
        'client_metrics': state.get('client_metrics', []),
        'stats': state.get('stats', {}),
        'checkout_utilization': state.get('checkout_utilization', {}),
        'queue_lengths': state.get('queue_lengths', {})
    }
    
    # Generar gráficas
    return analytics.save_all_charts(data, dia, hora)


def collect_simulation_data(sim) -> Dict[str, Any]:
    """
    Recopila todos los datos necesarios de la simulación.
    """
    from api import serialize_simulation_state
    
    # Obtener métricas de clientes
    state = serialize_simulation_state(sim)
    
    data = {
        'client_metrics': state.get('client_metrics', []),
        'stats': state.get('stats', {}),
    }
    
    return data