from typing import List, Tuple
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

    def run(self, max_ticks: int = 500, tick_delay: float = 0.1, visualize: bool = True):
        self.max_ticks = max_ticks
        while self.tick < self.max_ticks and not self.all_done():
            if visualize:
                print(f"Tick {self.tick}")
                self.map.print_map()
            self.step()
            if tick_delay > 0:
                time.sleep(tick_delay)
        print("Simulación terminada en tick", self.tick)
        if visualize:
            self.map.print_map()
