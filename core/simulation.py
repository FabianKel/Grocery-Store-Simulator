from typing import List, Tuple, Optional
from core.store_map import StoreMap
from entities.client import Client
from entities.cell import CellType
import time, random
from core.distribuciones import intervalo_entre_clientes


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

        # Para que entren con tiempo de por medio
        self.arrival_schedule: List[Tuple[int, Client]] = []  # (tick, client)
        self.entrance_pos: Optional[Tuple[int, int]] = self._find_entrance()

    def schedule_clients(self, clients: List[Client]):
        """
        Programa la entrada de cada cliente en función de una distribución de intervalo.
        """
        current_tick = 0
        for c in clients:
            delta = intervalo_entre_clientes()
            print("==="*30)
            print(f"[Scheduling] Cliente {getattr(c, 'id', None)} programado para entrar en tick {current_tick + delta} (delta: {delta})")
            print("==="*30)
            current_tick += delta
            self.arrival_schedule.append((current_tick, c))

        # Ordenamos por tick (por seguridad)
        self.arrival_schedule.sort(key=lambda x: x[0])

    def _spawn_clients_if_due(self):
        """
        Inserta los clientes que deben entrar en el tick actual.
        """
        to_spawn = [c for (t, c) in self.arrival_schedule if t == self.tick]
        for client in to_spawn:
            if self.entrance_pos:
                self.add_client(client, self.entrance_pos)
                print(f"[Tick {self.tick}] Cliente {getattr(client, 'id', None)} entra al supermercado.")
        # Removemos los que ya entraron
        self.arrival_schedule = [(t, c) for (t, c) in self.arrival_schedule if t > self.tick]

    def _find_entrance(self):
        for i in range(self.map.rows):
            for j in range(self.map.cols):
                if self.map.get_cell(i, j).type == CellType.ENTRANCE:
                    return (i, j)
        return None

    def add_client(self, client: Client, pos: Tuple[int, int]):
        self.clients.append(client)
        self.map.place_client(client, pos)
        # record start tick for performance metrics
        try:
            client.start_tick = self.tick
        except Exception:
            client.start_tick = None

    def step(self):
        # 1. Para cada cliente se ejecuta decide_next_action
        for cl in list(self.clients):
            cl.decide_next_action(self.map)

        # 2. Procesar checkouts: Si la fila no está vacía, se atiende al cliente del frente
        for i in range(self.map.rows):
            for j in range(self.map.cols):
                cell = self.map.get_cell(i, j)  # Se recorre cada celda del mapa

                # SI ES UNA CAJA Y HAY CLIENTES EN FILA
                if cell.type == CellType.CHECKOUT and cell.queue:
                    key = (i, j)
                    client_in_front = cell.queue[0] # Se obtiene el cliente que llegó primero a la caja
                    
                    # Si no hay timer o es 0, se calcula el tiempo de servicio
                    if key not in self.checkout_timers or self.checkout_timers[key] <= 0:
                        # 1. Definir parámetros
                        num_items = client_in_front.lista_len
                        base_time = 1
                        item_factor = 1
                        
                        # 2. Calcular el ruido y el tiempo total (SOLO UNA VEZ)
                        noise = random.randint(0, 2) 
                        calculated_service_time = base_time + num_items * item_factor + noise 
                        print(f"Tiempo calculado para cliente {getattr(client_in_front, 'id', None)} en caja {(i, j)}: {calculated_service_time} ticks (items: {num_items}, ruido: {noise})")
                        service_time_initial = max(1, calculated_service_time) # Tiempo inicial de servicio (ticks)

                        # 3. ASIGNAR EL TIEMPO CALCULADO AL CLIENTE (para recuperarlo al final)
                        client_in_front.checkout_time = service_time_initial
                        
                        # 4. INICIALIZAR EL TIMER
                        self.checkout_timers[key] = service_time_initial
                    
                    # OBTENER TIMER ACTUAL
                    timer = self.checkout_timers.get(key, 0)
                    
                    # decrement timer
                    timer -= 1
                    if timer <= 0:
                        # service customer: dequeue and move to EXIT (nearest)
                        served = cell.queue.pop(0)
                        
                        # RECUPERAMOS EL VALOR DEL CLIENTE
                        final_service_time = served.checkout_time
                        
                        print(f"[Simulation] Serving client {getattr(served, 'id', None)} at checkout {(i, j)}, service time: {final_service_time} ticks")
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
                            self.map.place_client(served, exit_pos)
                        # reset timer a 0 (para que el próximo tick se recalcule para el siguiente cliente)
                        self.checkout_timers[key] = 0 
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
        print("Programando clientes para la simulación ...")

        self.schedule_clients(self.clients)

        print("Simulación...")
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
            
            self._spawn_clients_if_due()

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
