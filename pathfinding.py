import heapq


def can_access_shelf(client_pos, shelf_pos, shelf_direction):
    """Verifica si el cliente puede acceder a una shelf desde su dirección permitida.
    shelf_direction is expected to be entities.cell.Direction.
    """
    # local import to avoid circular dependency at module import time
    from entities.cell import Direction
    cr, cc = client_pos
    sr, sc = shelf_pos

    if shelf_direction == Direction.UP:
        return (cr == sr - 1 and cc == sc)  # arriba
    elif shelf_direction == Direction.DOWN:
        return (cr == sr + 1 and cc == sc)  # abajo
    elif shelf_direction == Direction.LEFT:
        return (cr == sr and cc == sc - 1)  # izquierda
    elif shelf_direction == Direction.RIGHT:
        return (cr == sr and cc == sc + 1)  # derecha
    return False

def heuristic(a, b):
    """Distancia Manhattan entre dos puntos (r1, c1) y (r2, c2)."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def a_star(grid, start, goal, is_walkable, target_shelf=None):
    """
    Algoritmo A* modificado para respetar dirección de estanterías.
    Si target_shelf != None, el goal se interpreta como celda adyacente accesible.
    
    target_shelf : (pos, direction)  -> ((rs, cs), Direction.UP/DOWN/LEFT/RIGHT)
    """
    rows = len(grid)
    cols = len(grid[0])

    open_set = []
    heapq.heappush(open_set, (0, start))

    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def is_valid_move(nr, nc):
        """Verifica si la celda es válida para caminar."""
        if not (0 <= nr < rows and 0 <= nc < cols):
            return False
        cell = grid[nr][nc]
        # No atravesar shelves ni obstáculos (cell.type is entities.cell.CellType)
        # local import to avoid circular import at module load
        from entities.cell import CellType
        if cell.type in (CellType.OBSTACLE, CellType.SHELF):
            return False
        return is_walkable(cell)

    while open_set:
        _, current = heapq.heappop(open_set)

        # --- condición de llegada ---
        if target_shelf:
            (rs, cs), direction = target_shelf
            if can_access_shelf(current, (rs, cs), direction):
                # llegamos a una posición accesible para interactuar
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                path.reverse()
                return path
        elif current == goal:
            # destino normal (no shelf)
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path

        for dr, dc in directions:
            nr, nc = current[0] + dr, current[1] + dc
            if not is_valid_move(nr, nc):
                continue

            tentative_g = g_score[current] + 1
            if (nr, nc) not in g_score or tentative_g < g_score[(nr, nc)]:
                came_from[(nr, nc)] = current
                g_score[(nr, nc)] = tentative_g
                f_score[(nr, nc)] = tentative_g + heuristic((nr, nc), goal)
                heapq.heappush(open_set, (f_score[(nr, nc)], (nr, nc)))

    return None  # no hay camino
