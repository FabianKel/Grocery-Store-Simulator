from core.store_map import StoreMap
from entities.client import Client
from core.simulation import Simulation
from entities.cell import CellType
import argparse
import uvicorn


def build_example_store():
    """
    Construye un mapa 10x12 con:
      - Entrada arriba a la izquierda
      - Salida abajo a la izquierda
      - Pasillos amplios
      - Estanterías a ambos lados
      - Cajas en la esquina inferior derecha
    """
    rows, cols = 10, 12
    sm = StoreMap(rows=rows, cols=cols)

    # --- Configurar entrada y salida ---
    sm.grid[0][0].type = CellType.ENTRANCE
    sm.grid[rows - 1][0].type = CellType.EXIT

    # --- Configurar estanterías (zonas de productos) ---
    # Lado izquierdo
    for i in range(1, 8):
        sm.grid[i][2].type = CellType.SHELF
        sm.grid[i][2].category = "Lácteos"
        sm.grid[i][2].product_id = 100 + i

    # Lado derecho
    for i in range(1, 8):
        sm.grid[i][9].type = CellType.SHELF
        sm.grid[i][9].category = "Snacks"
        sm.grid[i][9].product_id = 200 + i

    # Estanterías centrales (dos columnas)
    for i in range(2, 7):
        sm.grid[i][5].type = CellType.SHELF
        sm.grid[i][5].category = "Bebidas"
        sm.grid[i][5].product_id = 300 + i

        sm.grid[i][6].type = CellType.SHELF
        sm.grid[i][6].category = "Panadería"
        sm.grid[i][6].product_id = 400 + i

    # --- Aumentar capacidad de pasillos principales ---
    # Pasillo central vertical
    for i in range(rows):
        sm.grid[i][4].capacity = 6
        sm.grid[i][7].capacity = 6
    # Pasillo horizontal al fondo
    for j in range(cols):
        sm.grid[rows - 2][j].capacity = 6

    # --- Configurar cajas (CHECKOUT) ---
    sm.grid[rows - 1][cols - 2].type = CellType.CHECKOUT
    sm.grid[rows - 1][cols - 1].type = CellType.CHECKOUT

    return sm


def run_demo():
    store = build_example_store()
    sim = Simulation(store)

    # Crear clientes
    c1 = Client(patience=0.9, tipo="solo", velocidad="Rapido")
    c2 = Client(patience=0.7, tipo="solo", velocidad="Normal")
    c3 = Client(patience=0.6, tipo="familia", velocidad="Tranquilo")

    # Asignar listas de productos según las estanterías disponibles
    c1.assign_list(store)
    c2.assign_list(store)
    c3.assign_list(store)

    # Colocar clientes en la entrada
    sim.add_client(c1, (0, 0))
    sim.add_client(c2, (0, 0))
    sim.add_client(c3, (0, 0))

    sim.run(max_ticks=50, tick_delay=0.1, visualize=True, animate=True, save_animation='store_simulation.gif')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Grocery Store Simulator (server or demo)")
    parser.add_argument('--demo', action='store_true', help='Run local demo simulation instead of starting the server')
    parser.add_argument('--host', default='127.0.0.1', help='Host for server (uvicorn)')
    parser.add_argument('--port', type=int, default=8000, help='Port for server (uvicorn)')
    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        print(f"🚀 Starting server on http://{args.host}:{args.port}")
        uvicorn.run("api:app", host=args.host, port=args.port)
