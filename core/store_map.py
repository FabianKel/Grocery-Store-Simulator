import os
import json
from typing import List, Tuple, Dict, Optional
from entities.cell import Cell, CellType, Direction
from entities.client import Client


class StoreMap:
    def __init__(self, rows: int = None, cols: int = None, from_file: str = None, symbol_file: str = "symbol_map.json"):
        self.symbol_config: Dict[str, dict] = {}
        self._setup_symbol_map(symbol_file)

        if from_file:
            self.load_from_file(from_file)
        else:
            if rows is None or cols is None:
                raise ValueError("rows y cols deben ser especificados si no se carga desde archivo.")
            self.rows = rows
            self.cols = cols
            self.grid = [[Cell(CellType.AISLE, i, j, capacity=4) for j in range(cols)] for i in range(rows)]

    def _setup_symbol_map(self, file_path='symbol_map.json'):
        if not os.path.exists(file_path):
            # default minimal map if file not found
            self.symbol_config = {
                ".": {"type": "AISLE", "capacity": 4},
                "S": {"type": "SHELF", "cat": "GEN", "id": 0, "dir": "NONE"},
                "C": {"type": "CHECKOUT"},
                "E": {"type": "ENTRANCE"},
                "X": {"type": "EXIT"},
                "#": {"type": "OBSTACLE"}
            }
            return
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.symbol_config = data

    def load_from_file(self, filepath: str):
        if not os.path.exists(filepath):
            raise FileNotFoundError(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip() and not ln.startswith("#")]
        self.rows = len(lines)
        self.cols = max(len(ln) for ln in lines)
        self.grid: List[List[Cell]] = []
        for i, ln in enumerate(lines):
            row: List[Cell] = []
            for j, ch in enumerate(ln):
                cfg = self.symbol_config.get(ch, self.symbol_config.get(".", {"type": "AISLE"}))
                ctype = CellType[cfg["type"]]
                if ctype == CellType.AISLE:
                    cap = cfg.get("capacity", 4)
                    cell = Cell(CellType.AISLE, i, j, capacity=cap)
                elif ctype == CellType.SHELF:
                    cell = Cell(CellType.SHELF, i, j, capacity=0)
                    cell.category = cfg.get("cat")
                    cell.product_id = cfg.get("id")
                    dir_str = cfg.get("dir", "NONE")
                    cell.direction = Direction[dir_str] if dir_str in Direction.__members__ else Direction.NONE
                elif ctype == CellType.CHECKOUT:
                    cell = Cell(CellType.CHECKOUT, i, j, capacity=0)
                elif ctype == CellType.ENTRANCE:
                    cell = Cell(CellType.ENTRANCE, i, j, capacity=999)
                elif ctype == CellType.EXIT:
                    cell = Cell(CellType.EXIT, i, j, capacity=999)
                else:
                    cell = Cell(CellType.OBSTACLE, i, j, capacity=0)
                row.append(cell)
            # pad if line shorter than cols
            while len(row) < self.cols:
                row.append(Cell(CellType.AISLE, i, len(row), capacity=4))
            self.grid.append(row)

    # helpers
    def in_bounds(self, pos: Tuple[int, int]) -> bool:
        r, c = pos
        return 0 <= r < self.rows and 0 <= c < self.cols

    def get_cell(self, row: int, col: int) -> Optional[Cell]:
        if not self.in_bounds((row, col)):
            return None
        return self.grid[row][col]

    def get_neighbors(self, row: int, col: int) -> List[Tuple[int, int]]:
        neighbors = []
        for d in [Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT]:
            nr, nc = row + d.value[0], col + d.value[1]
            if self.in_bounds((nr, nc)):
                # allow movement into AISLE, SHELF (to pick), CHECKOUT, ENTRANCE, EXIT
                if self.grid[nr][nc].type != CellType.OBSTACLE:
                    neighbors.append((nr, nc))
        return neighbors

    def is_cell_free(self, row: int, col: int) -> bool:
        cell = self.get_cell(row, col)
        if not cell:
            return False
        if cell.type == CellType.AISLE:
            return not cell.is_full()
        if cell.type == CellType.CHECKOUT:
            # we allow standing in a checkout queue cell always (queue deals with it)
            return True
        return True

    def move_client(self, client: 'Client', from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
        """
        Intenta mover un cliente: actualiza lists en celdas, aplica capacidades.
        Retorna True si se movió, False si no fue posible.
        """
        if not self.in_bounds(from_pos) or not self.in_bounds(to_pos):
            return False
        from_cell = self.get_cell(*from_pos)
        to_cell = self.get_cell(*to_pos)
        if to_cell.type == CellType.AISLE:
            if to_cell.is_full():
                return False
            # mover
            if client in from_cell.clients:
                from_cell.remove_client(client)
            to_cell.add_client(client)
            client.pos = to_pos
            return True
        elif to_cell.type == CellType.SHELF:
            # allow stepping into shelf cell for picking (no capacity limit assumed)
            if client in from_cell.clients:
                from_cell.remove_client(client)
            to_cell.add_client(client)
            client.pos = to_pos
            return True
        elif to_cell.type == CellType.CHECKOUT:
            # join queue
            if client in from_cell.clients:
                from_cell.remove_client(client)
            to_cell.queue.append(client)
            print(f"[StoreMap] Client {getattr(client,'id',None)} joined checkout queue at {to_pos}")
            client.pos = to_pos
            client.in_queue = True
            return True
        elif to_cell.type in (CellType.ENTRANCE, CellType.EXIT):
            if client in from_cell.clients:
                from_cell.remove_client(client)
            to_cell.add_client(client)
            client.pos = to_pos
            return True
        return False

    def place_client(self, client: 'Client', pos: Tuple[int, int]):
        cell = self.get_cell(*pos)
        if not cell:
            raise ValueError("Posición fuera de rango")
        # don't strictly check capacity here; use move_client in simulation loop
        cell.add_client(client)
        client.pos = pos

    def get_products(self) -> List[Tuple[str, int, Tuple[int, int]]]:
        """
        Regresa lista de (category, product_id, (row,col)) de todas las estanterías con producto_id.
        """
        products = []
        for i in range(self.rows):
            for j in range(self.cols):
                c = self.grid[i][j]
                if c.type == CellType.SHELF and c.product_id is not None:
                    products.append((c.category, c.product_id, (i, j)))
        return products

    #def find_nearest_checkout(self, row: int, col: int) -> Optional[Tuple[int, int]]:
        # busca celda CHECKOUT más cercana (BFS simple)
        #from collections import deque
        #visited = set()
        #q = deque([(row, col)])
        #while q:
            #r, c = q.popleft()
            #if (r, c) in visited:
                #continue
            #visited.add((r, c))
            #cell = self.get_cell(r, c)
            #if cell.type == CellType.CHECKOUT:
                #return (r, c)
            #for n in self.get_neighbors(r, c):
                #if n not in visited:
                    #q.append(n)
        #return None

    def find_best_checkout(self, row: int, col: int) -> Optional[Tuple[int, int]]:
        """
        Encuentra el mejor cajero considerando:
        - Gente en fila
        - Gente caminando hacia ese cajero
        - Distancia
        """
        checkouts = []
        
        # Obtener todos los clientes del mapa
        all_clients = []
        for i in range(self.rows):
            for j in range(self.cols):
                all_clients.extend(self.get_cell(i, j).clients)
        
        for i in range(self.rows):
            for j in range(self.cols):
                cell = self.get_cell(i, j)
                if cell.type == CellType.CHECKOUT:
                    queue_length = len(cell.queue)
                    
                    # Contar clientes que van hacia este cajero
                    clients_heading_here = sum(
                        1 for c in all_clients 
                        if (hasattr(c, 'target') and 
                            c.target == (i, j) and 
                            not getattr(c, 'in_queue', False))
                    )
                    
                    # Carga total = en fila + en camino
                    total_load = queue_length + clients_heading_here
                    distance = abs(i - row) + abs(j - col)
                    
                    checkouts.append((total_load, distance, (i, j)))
        
        if not checkouts:
            return None
        
        checkouts.sort(key=lambda x: (x[0], x[1]))
        
        print(f"[StoreMap] Mejor cajero en {checkouts[0][2]}: "
            f"carga_total={checkouts[0][0]}, distancia={checkouts[0][1]}")
        
        return checkouts[0][2]

    def get_map_status(self) -> dict:
        """
        Resumen compacto del mapa: posiciones de clientes, estantes, colas, ocupación por celda.
        """
        clients = []
        for i in range(self.rows):
            for j in range(self.cols):
                c = self.grid[i][j]
                for cl in c.clients:
                    clients.append({"id": getattr(cl, "id", None), "pos": (i, j), "tipo": cl.tipo})
                # checkout queue items
                if c.type == CellType.CHECKOUT:
                    for qidx, cl in enumerate(c.queue):
                        clients.append({"id": getattr(cl, "id", None), "pos": (i, j), "queue_pos": qidx, "tipo": cl.tipo})
        shelves = [{"pos": (i, j), "cat": c.category, "id": c.product_id} for i in range(self.rows) for j in range(self.cols) if self.grid[i][j].type == CellType.SHELF]
        occupancy = [[len(self.grid[i][j].clients) / (self.grid[i][j].capacity if self.grid[i][j].capacity>0 else 1) for j in range(self.cols)] for i in range(self.rows)]
        return {
            "rows": self.rows,
            "cols": self.cols,
            "clients": clients,
            "shelves": shelves,
            "occupancy": occupancy
        }

    def print_map(self):
        for i in range(self.rows):
            row_repr = []
            for j in range(self.cols):
                cell = self.grid[i][j]

                # Caso 1: si hay clientes en la celda
                if cell.clients:
                    # Mostrar los símbolos de los clientes
                    if len(cell.clients) == 1:
                        cl = cell.clients[0]
                        cell_repr = f"[{cl.symbol}]"
                    else:
                        # Varios clientes: agrupar en []
                        symbols = ",".join(cl.symbol for cl in cell.clients)
                        cell_repr = f"[{symbols}]"

                # Caso 2: si hay clientes en una cola de checkout
                elif cell.type == CellType.CHECKOUT and cell.queue:
                    queue_symbols = ",".join(cl.symbol for cl in cell.queue)
                    cell_repr = f"Q[{queue_symbols}]"

                # Caso 3: celda vacía normal → mostrar ocupación como antes
                else:
                    if cell.type == CellType.AISLE:
                        # Mostrar capacidad ocupada (ejemplo: ".2/4")
                        cell_repr = f".{len(cell.clients)}/{cell.capacity}"
                    elif cell.type == CellType.SHELF:
                        pid = getattr(cell, 'product_id', None)
                        if isinstance(pid, int):
                            cell_repr = f"SL{pid:03d}"
                        else:
                            cell_repr = "SL---"
                    elif cell.type == CellType.CHECKOUT:
                        cell_repr = "SB201"
                    elif cell.type == CellType.ENTRANCE:
                        cell_repr = "EN"
                    elif cell.type == CellType.EXIT:
                        cell_repr = "EX"
                    else:
                        cell_repr = "###"  # obstáculo

                row_repr.append(f"{cell_repr:>6}")
            print(" ".join(row_repr))
        print()

    def get_console_map(self) -> str:
        """Return the textual representation of the map as a multi-line string (same format as print_map)."""
        lines = []
        for i in range(self.rows):
            row_repr = []
            for j in range(self.cols):
                cell = self.grid[i][j]

                if cell.clients:
                    if len(cell.clients) == 1:
                        cl = cell.clients[0]
                        cell_repr = f"[{cl.symbol}]"
                    else:
                        symbols = ",".join(cl.symbol for cl in cell.clients)
                        cell_repr = f"[{symbols}]"
                elif cell.type == CellType.CHECKOUT and cell.queue:
                    queue_symbols = ",".join(cl.symbol for cl in cell.queue)
                    cell_repr = f"Q[{queue_symbols}]"
                else:
                    if cell.type == CellType.AISLE:
                        cell_repr = f".{len(cell.clients)}/{cell.capacity}"
                    elif cell.type == CellType.SHELF:
                        pid = getattr(cell, 'product_id', None)
                        if isinstance(pid, int):
                            cell_repr = f"SL{pid:03d}"
                        else:
                            cell_repr = "SL---"
                    elif cell.type == CellType.CHECKOUT:
                        cell_repr = "SB201"
                    elif cell.type == CellType.ENTRANCE:
                        cell_repr = "EN"
                    elif cell.type == CellType.EXIT:
                        cell_repr = "EX"
                    else:
                        cell_repr = "###"

                row_repr.append(f"{cell_repr:>6}")
            lines.append(" ".join(row_repr))
        return "\n".join(lines)
