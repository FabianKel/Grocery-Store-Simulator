from typing import List, Tuple, Optional
from core.store_map import StoreMap
from entities.client import Client
from entities.cell import CellType
import time


class Simulation:
    def __init__(self, store_map: StoreMap):
        self.map = store_map
        self.clients: List[Client] = []
        self.tick = 0
        self.max_ticks = 1000
        # Checkout processing speed (clients per ticks) simple model
        self.checkout_service_time = 3  # ticks per customer at checkout

        # keep per-checkout timers (position -> remaining time for current client)
        self.checkout_timers = {}

    def add_client(self, client: Client, pos: Tuple[int, int]):
        self.clients.append(client)
        self.map.place_client(client, pos)
        # record start tick for performance metrics
        try:
            client.start_tick = self.tick
        except Exception:
            client.start_tick = None

    def step(self):
        # 1. for each client, perform decide_next_action
        for cl in list(self.clients):
            cl.decide_next_action(self.map)

        # 2. process checkouts: if queue not empty, service front client
        for i in range(self.map.rows):
            for j in range(self.map.cols):
                cell = self.map.get_cell(i, j)
                if cell.type == CellType.CHECKOUT and cell.queue:
                    key = (i, j)
                    timer = self.checkout_timers.get(key, self.checkout_service_time)
                    # decrement timer
                    timer -= 1
                    if timer <= 0:
                        # service customer: dequeue and move to EXIT (nearest)
                        served = cell.queue.pop(0)
                        # place served client to exit cell if possible
                        exit_pos = self._find_exit_or_entrance()
                        if exit_pos:
                            # mark client as finished
                            served.in_queue = False
                            served.mark_finished()
                            # record finish tick for metrics
                            try:
                                served.finish_tick = self.tick
                            except Exception:
                                served.finish_tick = None
                            # remove client from anywhere and place at exit (no capacity handling for exit)
                            # Note: ensure they aren't duplicated in clients lists in cells
                            # Place at exit cell
                            self.map.place_client(served, exit_pos)
                        # reset timer
                        self.checkout_timers[key] = self.checkout_service_time
                    else:
                        self.checkout_timers[key] = timer

        # 3. increment global tick
        self.tick += 1

    def _find_exit_or_entrance(self):
        # busca primera EXIT, si no, ENTRANCE
        for i in range(self.map.rows):
            for j in range(self.map.cols):
                if self.map.get_cell(i, j).type == CellType.EXIT:
                    return (i, j)
        for i in range(self.map.rows):
            for j in range(self.map.cols):
                if self.map.get_cell(i, j).type == CellType.ENTRANCE:
                    return (i, j)
        return None

    def all_done(self):
        # todos los clientes finished?
        return all(getattr(c, "shopping_done", False) for c in self.clients)

    def run(self, max_ticks: int = 500, tick_delay: float = 0.1, visualize: bool = True,
            animate: bool = False, save_animation: Optional[str] = None):
        """
        Ejecuta la simulación.

        Params:
          - max_ticks: número máximo de ticks
          - tick_delay: demora entre ticks (en segundos). Si `animate` es True, este delay solo afecta la velocidad de la animación (intervalo).
          - visualize: si True, imprime el mapa en consola cada tick
          - animate: si True, intenta capturar cada tick y construir una animación con matplotlib
          - save_animation: si se provee, guarda la animación en ese archivo (por ejemplo 'sim.gif')
        """
        self.max_ticks = max_ticks

        frames = []  # lista de matrices de ocupación por tick (floats 0..1)
        labels = None  # etiquetas estáticas (estanterías, cajas, EN/EX)

        if animate:
            try:
                import matplotlib.pyplot as plt
                import matplotlib.animation as animation
                import numpy as np
            except Exception as e:
                print("matplotlib no está disponible o falló la importación:", e)
                print("Continuando sin animación. Para animar instale: pip install matplotlib pillow")
                animate = False

        while self.tick < self.max_ticks and not self.all_done():
            if visualize:
                print(f"Tick {self.tick}")
                self.map.print_map()

            if animate:
                # capturar occupancy matrix
                status = self.map.get_map_status()
                occ = status.get("occupancy")
                # copy to simple list of lists
                frames.append([row[:] for row in occ])
                # prepare labels once
                if labels is None:
                    labels = [[None for _ in range(self.map.cols)] for __ in range(self.map.rows)]
                    for i in range(self.map.rows):
                        for j in range(self.map.cols):
                            c = self.map.get_cell(i, j)
                            if c.type == CellType.SHELF:
                                pid = getattr(c, "product_id", None)
                                labels[i][j] = f"SL{pid:03d}" if pid is not None else "SL---"
                            elif c.type == CellType.CHECKOUT:
                                labels[i][j] = "CB"
                            elif c.type == CellType.ENTRANCE:
                                labels[i][j] = "EN"
                            elif c.type == CellType.EXIT:
                                labels[i][j] = "EX"

            self.step()

            # si estamos grabando animación, no dormimos para no ralentizar la captura
            if tick_delay > 0 and not animate:
                time.sleep(tick_delay)

        # fin del loop
        print(f"Simulación terminada en tick {self.tick}")
        if visualize:
            self.map.print_map()
        if animate and frames:
            try:
                import matplotlib.pyplot as plt
                import matplotlib.animation as animation
                import numpy as np

                fig, ax = plt.subplots(figsize=(self.map.cols / 2, self.map.rows / 2))
                arr0 = np.array(frames[0])
                im = ax.imshow(arr0, cmap="YlGn", vmin=0, vmax=1)
                ax.set_xticks([])
                ax.set_yticks([])

                # dibujar etiquetas estáticas pequeñas
                text_objs = []
                for i in range(self.map.rows):
                    for j in range(self.map.cols):
                        lab = labels[i][j]
                        if lab:
                            t = ax.text(j, i, lab, ha="center", va="center", fontsize=6, color="black")
                            text_objs.append(t)

                def _update(k):
                    im.set_data(np.array(frames[k]))
                    return [im] + text_objs

                interval = int(tick_delay * 1000) if tick_delay > 0 else 200
                ani = animation.FuncAnimation(fig, _update, frames=len(frames), interval=interval, blit=False)

                if save_animation:
                    try:
                        ani.save(save_animation, writer="pillow")
                        print("Animación guardada en", save_animation)
                    except Exception as e:
                        print("Error guardando animación:", e)
                else:
                    plt.show()

            except Exception as e:
                print("Error al crear/mostrar la animación:", e)
