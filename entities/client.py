import random
from typing import List, Tuple, Optional
from pathfinding import a_star
from entities.cell import CellType, Direction
from core.distribuciones import calc_move_delay


class Client:
    """
    Agente que se mueve por el mapa, tiene lista de compras y comportamiento simple.
    """
    _id_counter = 0

    @classmethod
    def reset_counter(cls):
        """Resetea el contador de IDs a 0"""
        cls._id_counter = 0

    def __init__(self, patience: float, tipo: str, velocidad: str):
        # parametros básicos
        if not (0 <= patience <= 1):
            raise ValueError("patience must be between 0 and 1")
        if tipo not in ['familia', 'solo']:
            raise ValueError("tipo debe ser 'familia' o 'solo'")
        if velocidad not in ['Rapido', 'Normal', 'Tranquilo']:
            raise ValueError("velocidad debe ser 'Rapido', 'Normal' o 'Tranquilo'")

        # Incrementar contador y asignar ID
        Client._id_counter += 1
        self.id = Client._id_counter
        
        self.patience = patience
        self.tipo = tipo
        self.velocidad = velocidad
        # decide delay entre movimientos (ticks)
        self.symbol = f"C{self.id}"
        self.position = None
        self.move_delay = {'Rapido': 1, 'Normal': 2, 'Tranquilo': 3}[velocidad]
        self._delay_counter = 0
        self.moving_first_try = True

        self.lista: List[Tuple[str, int, Tuple[int, int]]] = []  # (cat, pid, pos)
        self.lista_len = 0
        self.items_total = 0  # Total de items al inicio
        self.pos: Optional[Tuple[int, int]] = None
        self.target: Optional[Tuple[int, int]] = None
        self.path: Optional[List[Tuple[int, int]]] = None
        self.shopping_done = False
        self.in_queue = False
        self.time_waited = 0
        self.checkout_time = 0
        self.entry_tick = 0
        self.start_tick = None
        self.finish_tick = None

    def assign_list(self, store_map):
        products = store_map.get_products()
        if not products:
            self.lista = []
            self.items_total = 0
            return
        # número de items basado en tipo
        if self.tipo == 'familia':
            num = random.randint(8, 14)
        else:
            num = max(1, min(10, int(random.gauss(5, 2))))
        num = min(num, len(products))
        # ensure at least one item if products are available
        if len(products) > 0 and num < 1:
            num = 1
        picks = random.sample(products, num)
        # products are (cat, id, pos)
        self.lista_len = len(picks)
        self.lista = picks
        self.items_total = len(picks)  # Guardar el total inicial

    def observe_environment(self, store_map):
        # información resumida (vecinos y ocupación)
        r, c = self.pos
        neighbors = store_map.get_neighbors(r, c)
        occ = store_map.get_map_status()["occupancy"]
        return {"neighbors": neighbors, "occupancy": occ}

    def choose_next_target(self, store_map):
        # si tiene lista, elegir el producto más cercano (por Manhattan) entre los que quedan
        if not self.lista:
            # si no hay lista, objetivo: checkout nearest
            chk = store_map.find_best_checkout(*self.pos)
            self.target = chk
            return self.target
        # elegir el producto en lista más cercano
        min_d = None
        chosen = None
        for (cat, pid, pos) in self.lista:
            d = abs(pos[0] - self.pos[0]) + abs(pos[1] - self.pos[1])
            if min_d is None or d < min_d:
                min_d = d
                chosen = pos
        self.target = chosen
        return self.target


    def plan_path(self, store_map):
        """
        Planea un camino hacia el objetivo actual.
        Si el objetivo es una shelf, el cliente planea hasta una celda adyacente accesible según su dirección.
        """
        if self.target is None or self.pos is None:
            self.path = None
            return None

        target_cell = store_map.get_cell(*self.target)

        # --- Caso 1: objetivo es una shelf ---
        if target_cell and target_cell.type == CellType.SHELF:
            shelf_pos = self.target
            shelf_dir = target_cell.direction

            # Si la estantería no tiene dirección definida, permitir acceso desde cualquier lado.
            if shelf_dir is None or shelf_dir == Direction.NONE:
                # probar caminos a cada celda adyacente válida y escoger el más corto
                neighbors = store_map.get_neighbors(shelf_pos[0], shelf_pos[1])
                best_path = None
                best_nb = None
                for nb in neighbors:
                    path = a_star(
                        grid=store_map.grid,
                        start=self.pos,
                        goal=nb,
                        is_walkable=lambda cell: cell.type not in {CellType.OBSTACLE, CellType.SHELF}
                    )
                    if path:
                        if best_path is None or len(path) < len(best_path):
                            best_path = path
                            best_nb = nb
                path = best_path
                # if we found a path to an adjacent cell, set the target to that adjacent cell
                if best_nb is not None:
                    self.target = best_nb
            else:
                # Buscar camino hasta una celda adyacente accesible (según dirección)
                path = a_star(
                    grid=store_map.grid,
                    start=self.pos,
                    goal=shelf_pos,
                    is_walkable=lambda cell: cell.type not in {CellType.OBSTACLE, CellType.SHELF},
                    target_shelf=(shelf_pos, shelf_dir)
                )
                # if A* returned a path to an adjacent access cell, update the target
                if path:
                    # path[-1] is the reachable adjacent cell
                    self.target = path[-1]

        # --- Caso 2: objetivo normal (checkout, salida, entrada, etc.) ---
        else:
            path = a_star(
                grid=store_map.grid,
                start=self.pos,
                goal=self.target,
                is_walkable=lambda cell: cell.type not in {CellType.OBSTACLE, CellType.SHELF}
            )

        self.path = path or []
        print(f"[Client {self.id}] plan_path target={self.target} computed_path={self.path}")
        return self.path


    def move_one_step(self, store_map) -> bool:
        """
        Se mueve un paso en la ruta planificada si el siguiente paso está libre.
        Retorna True si se movió.
        """

        if self.moving_first_try:
            # Se define el move_delay para el movimiento a la siguiente casilla
            self.move_delay = calc_move_delay(tipo = self.tipo, rapidez=self.velocidad)
            self.moving_first_try = False

        # control de velocidad por ticks
        if self._delay_counter < self.move_delay - 1:
            self._delay_counter += 1
            return False
        self._delay_counter = 0

        if not self.path:
            return False
        next_pos = self.path[0]
        # intentar mover via store_map.move_client (que verifica capacidad)
        moved = store_map.move_client(self, self.pos, next_pos)
        if moved:
            # consumir paso en path
            self.path.pop(0)
            self.moving_first_try = True
            return True
        else:
            # si no puede moverse (celda ocupada), intentar re-planificar ocasionalmente
            if random.random() < 0.2:
                self.plan_path(store_map)
            return False

    def attempt_purchase(self, store_map):
        """
        Si está sobre una estantería y el producto está en lista, lo compra.
        """
        cell = store_map.get_cell(*self.pos)
        # Si está exactamente en la shelf, comprar por posición
        if cell.type == CellType.SHELF:
            for idx, (cat, pid, pos) in enumerate(self.lista):
                if pos == self.pos:
                    # "comprar": eliminar de la lista
                    self.lista.pop(idx)
                    print(f"[Client {self.id}] bought item at shelf {pos}; items_left={len(self.lista)}")
                    return True
            return False

        # Si no está sobre la estantería, permitir compra desde una celda adyacente
        neighbors = store_map.get_neighbors(self.pos[0], self.pos[1])
        for nb in neighbors:
            ncell = store_map.get_cell(*nb)
            if ncell and ncell.type == CellType.SHELF:
                for idx, (cat, pid, pos) in enumerate(self.lista):
                    if pos == nb:
                        self.lista.pop(idx)
                        print(f"[Client {self.id}] bought item from adjacent shelf {nb}; items_left={len(self.lista)}")
                        return True
        return False

    def decide_next_action(self, store_map):
        """
        Lógica por frame:
        - si en queue: aumentar time_waited
        - si path vacío y no target: elegir target y plan
        - intentar moverse
        - si en shelf: comprar
        - si lista vacía y no en queue: dirigirse a checkout
        """
        if self.shopping_done:
            return

        if self.in_queue:
            self.time_waited += 1
            # simplified: if reaches front of queue and checkout processes it,
            # Simulation will mark client as finished by removing from queue and moving to EXIT.
            return

        # if no position assigned yet -> nothing to do (placement handled externally)
        if self.pos is None:
            return

        # choose target if none
        if self.target is None:
            self.choose_next_target(store_map)
            print(f"[Client {self.id}] chose target={self.target}")
            self.plan_path(store_map)

        # Reevaluación de cajero basada en paciencia
        # Si va hacia un cajero y no está en fila, considerar cambiar de opinión
        if self.target and not self.in_queue:
            target_cell = store_map.get_cell(*self.target)
            if target_cell and target_cell.type == CellType.CHECKOUT:
                # Clientes impacientes (patience < 0.5) reevalúan con más frecuencia
                reevaluate_prob = (1 - self.patience) * 0.3  # Max 30% de prob por tick
                
                if random.random() < reevaluate_prob:
                    new_chk = store_map.find_best_checkout(*self.pos)
                    
                    # Solo cambiar si el nuevo cajero es significativamente mejor
                    if new_chk and new_chk != self.target:
                        current_load = len(store_map.get_cell(*self.target).queue)
                        new_load = len(store_map.get_cell(*new_chk).queue)
                        
                        # Cambiar si el nuevo tiene al menos 2 personas menos
                        if new_load < current_load - 1:
                            self.target = new_chk
                            self.plan_path(store_map)
                            print(f"[Client {self.id}] cambió de cajero (paciencia={self.patience:.2f})")

        # if arrived at target
        if self.target == self.pos:
            # if shelf -> attempt purchase
            cell = store_map.get_cell(*self.pos)
            if cell.type == CellType.SHELF:
                bought = self.attempt_purchase(store_map)
                if bought:
                    # reset target
                    self.target = None
                    self.path = None
                    if not self.lista:
                        # go to checkout
                        chk = store_map.find_best_checkout(*self.pos)
                        self.target = chk
                        self.plan_path(store_map)
                    return
            # if checkout and in queue handled elsewhere
        # else try move
        moved = self.move_one_step(store_map)
        if moved:
            # if reached and it's a shelf or adjacent access -> attempt to buy immediately
            if self.target == self.pos:
                bought = self.attempt_purchase(store_map)
                if bought:
                    # reset target/path and head to checkout if list is empty
                    self.target = None
                    self.path = None
                    if not self.lista:
                        chk = store_map.find_best_checkout(*self.pos)
                        self.target = chk
                        self.plan_path(store_map)
                    return
            # if reached checkout cell (queue) `move_client` sets in_queue True
        return

    def mark_finished(self):
        self.shopping_done = True