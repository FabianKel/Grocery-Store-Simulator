from enum import Enum
from typing import List, Optional, Dict, TYPE_CHECKING
import os
if TYPE_CHECKING:
    from entities.client import Client


class CellType(Enum):
    AISLE = "aisle"
    SHELF = "shelf"
    CHECKOUT = "checkout"
    ENTRANCE = "entrance"
    EXIT = "exit"
    OBSTACLE = "obstacle"


class Direction(Enum):
    UP = (-1, 0)
    DOWN = (1, 0)
    LEFT = (0, -1)
    RIGHT = (0, 1)
    NONE = (0, 0)


class Cell:
    """
    Representa una celda del mapa. Puede contener múltiples clientes (hasta capacity)
    o ser una estantería (SHELF) con categoría y product_id.
    """
    def __init__(self, cell_type: CellType, row: int, col: int, capacity: int = 1):
        self.type = cell_type
        self.row = row
        self.col = col
        self.capacity = capacity if cell_type == CellType.AISLE else 0
        self.clients: List['Client'] = []
        # atributos para SHELF
        self.category: Optional[str] = None
        self.product_id: Optional[int] = None
        self.direction: Optional[Direction] = None
        # para checkout
        self.queue: List['Client'] = []

    def is_full(self) -> bool:
        if self.type == CellType.AISLE:
            return len(self.clients) >= self.capacity
        return False

    def add_client(self, client: 'Client'):
        if self.type == CellType.AISLE:
            if not self.is_full():
                self.clients.append(client)
            else:
                raise RuntimeError("Celda de pasillo llena")
        elif self.type in (CellType.CHECKOUT,):
            self.queue.append(client)
        else:
            # para SHELF o ENTRANCE/EXIT: client stands on cell (no capacity limit assumed)
            self.clients.append(client)

    def remove_client(self, client: 'Client'):
        if client in self.clients:
            self.clients.remove(client)
        elif client in self.queue:
            self.queue.remove(client)

    def __repr__(self):
        if self.type == CellType.AISLE:
            return f".{len(self.clients)}/{self.capacity}"
        if self.type == CellType.SHELF:
            cat = self.category[0] if self.category else "?"
            pid = self.product_id if self.product_id is not None else ""
            return f"S{cat}{pid}"
        if self.type == CellType.CHECKOUT:
            return f"Q{len(self.queue)}"
        if self.type == CellType.ENTRANCE:
            return "EN"
        if self.type == CellType.EXIT:
            return "EX"
        return "##"
