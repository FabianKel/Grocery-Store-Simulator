from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import json
import uvicorn

from core.store_map import StoreMap
from entities.client import Client
from core.simulation import Simulation
from entities.cell import CellType
import os
import base64
from datetime import datetime

app = FastAPI(title="Grocery Store Simulator")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos Pydantic
class ClientConfig(BaseModel):
    patience: float
    tipo: str
    velocidad: str

class SimulationConfig(BaseModel):
    max_ticks: int = 100
    tick_delay: float = 0.5
    rows: int = 10
    cols: int = 12
    num_clients: int = 5
    clients: List[ClientConfig] = []

# Variable global para la simulación
current_simulation = None
simulation_running = False

def build_store(rows=10, cols=12):
    """Construye el mapa de la tienda"""
    sm = StoreMap(rows=rows, cols=cols)
    
    # Entrada y salida
    sm.grid[0][0].type = CellType.ENTRANCE
    sm.grid[rows - 1][0].type = CellType.EXIT
    
    # Estanterías lado izquierdo - Lácteos
    for i in range(1, min(8, rows-1)):
        sm.grid[i][2].type = CellType.SHELF
        sm.grid[i][2].category = "Lácteos"
        sm.grid[i][2].product_id = 100 + i
    
    # Estanterías lado derecho - Snacks
    for i in range(1, min(8, rows-1)):
        if cols > 9:
            sm.grid[i][9].type = CellType.SHELF
            sm.grid[i][9].category = "Snacks"
            sm.grid[i][9].product_id = 200 + i
    
    # Estanterías centrales
    if cols > 6:
        for i in range(2, min(7, rows-2)):
            sm.grid[i][5].type = CellType.SHELF
            sm.grid[i][5].category = "Bebidas"
            sm.grid[i][5].product_id = 300 + i
            
            if cols > 6:
                sm.grid[i][6].type = CellType.SHELF
                sm.grid[i][6].category = "Pan"
                sm.grid[i][6].product_id = 400 + i
    
    # Pasillos principales
    for i in range(rows):
        if cols > 4:
            sm.grid[i][4].capacity = 6
        if cols > 7:
            sm.grid[i][7].capacity = 6
    
    for j in range(cols):
        sm.grid[rows - 2][j].capacity = 6
    
    # Cajas
    if cols >= 2:
        sm.grid[rows - 1][cols - 2].type = CellType.CHECKOUT
        sm.grid[rows - 1][cols - 1].type = CellType.CHECKOUT
    
    return sm

def serialize_simulation_state(sim: Simulation):
    """Convierte el estado de la simulación a JSON"""
    rows, cols = sim.map.rows, sim.map.cols
    
    cells = []
    for i in range(rows):
        row = []
        for j in range(cols):
            cell = sim.map.grid[i][j]
            
            cell_data = {
                "type": cell.type.value,
                "clients": [],
                "queue": [],
                "capacity": cell.capacity,
                "occupancy": len(cell.clients) / cell.capacity if cell.capacity > 0 else 0
            }
            
            # Información de estanterías
            if cell.type == CellType.SHELF:
                cell_data["category"] = cell.category
                cell_data["product_id"] = cell.product_id
            
            # Clientes en la celda
            for client in cell.clients:
                client_data = {
                    "id": getattr(client, 'id', None),
                    "tipo": getattr(client, 'tipo', None),
                    "velocidad": getattr(client, 'velocidad', None),
                    "patience": getattr(client, 'patience', None),
                    "items_left": len(getattr(client, 'lista', [])),
                    "shopping_done": getattr(client, 'shopping_done', False),
                    "path": getattr(client, 'path', []) if getattr(client, 'path', None) else []
                }
                cell_data["clients"].append(client_data)
            
            # Cola de checkout
            if cell.type == CellType.CHECKOUT:
                for client in cell.queue:
                    client_data = {
                        "id": getattr(client, 'id', None),
                        "tipo": getattr(client, 'tipo', None),
                        "velocidad": getattr(client, 'velocidad', None),
                        "patience": getattr(client, 'patience', None),
                        "time_waited": getattr(client, 'time_waited', None)
                    }
                    cell_data["queue"].append(client_data)
            
            row.append(cell_data)
        cells.append(row)
    
    # Estadísticas
    stats = {
        "tick": sim.tick,
        "total_clients": len(sim.clients),
        "active_clients": sum(1 for c in sim.clients if not getattr(c,'shopping_done', False)),
        "clients_shopping": sum(1 for c in sim.clients if not getattr(c,'in_queue', False) and not getattr(c,'shopping_done', False)),
        "clients_in_queue": sum(1 for c in sim.clients if getattr(c,'in_queue', False)),
        "clients_done": sum(1 for c in sim.clients if getattr(c,'shopping_done', False))
    }
    # Console map (textual representation) - helpful for frontend display/logging
    console_map = ""
    try:
        console_map = sim.map.get_console_map()
    except Exception:
        console_map = None

    # Per-client metrics (start/finish ticks and computed total time when finished)
    client_metrics = []
    for c in getattr(sim, 'clients', []):
        start = getattr(c, 'start_tick', None)
        finish = getattr(c, 'finish_tick', None)
        total_time = None
        checkout_time = getattr(c, 'checkout_time', None)
        if start is not None and finish is not None:
            try:
                total_time = int(finish - start)
            except Exception:
                total_time = None

        client_metrics.append({
            "id": getattr(c, 'id', None),
            "tipo": getattr(c, 'tipo', None),
            "velocidad": getattr(c, 'velocidad', None),
            "patience": getattr(c, 'patience', None),
            "items_left": len(getattr(c, 'lista', [])) if getattr(c, 'lista', None) is not None else None,
            "items_total": getattr(c, 'items_total', None),
            "shopping_done": getattr(c, 'shopping_done', False),
            "in_queue": getattr(c, 'in_queue', False),
            "start_tick": start,
            "finish_tick": finish,
            "total_time": total_time,
            "checkout_time" : checkout_time
        })

    return {
        "cells": cells,
        "stats": stats,
        "rows": rows,
        "cols": cols,
        "console_map": console_map,
        "client_metrics": client_metrics
    }

@app.get("/", response_class=HTMLResponse)
async def get_interface():
    """Sirve la interfaz HTML (embed)"""
    # Redirigir al index estático
    return RedirectResponse(url="/static/index.html")

# montar archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.post("/api/save_gift")
async def save_gift(payload: dict):
    """Recibe un dataURL PNG en JSON y lo guarda en disk en static/exports.
    payload: { "filename": "optional.png", "data_url": "data:image/png;base64,..." }
    """
    try:
        data_url = payload.get('data_url')
        filename = payload.get('filename')
        if not data_url or not data_url.startswith('data:image/'):
            return {"error": "invalid data_url"}

        # detect mime and choose extension
        try:
            header, b64 = data_url.split(',', 1)
            mime = header.split(':', 1)[1].split(';', 1)[0]
        except Exception:
            return {"error": "invalid data_url format"}

        ext = 'png'
        if mime == 'image/gif':
            ext = 'gif'
        elif mime == 'image/jpeg' or mime == 'image/jpg':
            ext = 'jpg'
        elif mime == 'image/png':
            ext = 'png'

        # build filename if not provided
        if not filename:
            filename = f"sim_gift_{int(datetime.utcnow().timestamp())}.{ext}"
        else:
            # ensure extension matches mime if possible
            if not os.path.splitext(filename)[1]:
                filename = f"{filename}.{ext}"

        # ensure exports dir exists
        exports_dir = os.path.join('static', 'exports')
        os.makedirs(exports_dir, exist_ok=True)

        data = base64.b64decode(b64)
        safe_name = os.path.basename(filename)
        path = os.path.join(exports_dir, safe_name)
        with open(path, 'wb') as f:
            f.write(data)

        return {"saved": path}
    except Exception as e:
        return {"error": str(e)}
    

from core.distribuciones import (
    clientes_por_hora,
    calc_client_type,
    intervalo_entre_clientes,
    calc_speed,
    calc_paciencia,
    noise_caja,
    calc_move_delay,

)
import random

@app.websocket("/ws/simulate")
async def websocket_simulate(websocket: WebSocket):
    await websocket.accept()
    print(f"🔌 Nueva conexión WebSocket: {websocket.client}")
    
    try:
        # Recibir configuración inicial
        config_data = await websocket.receive_text()
        config = json.loads(config_data)
        print(f"📝 Config recibida: {config}")
        
        dia = config.get('day', 'lunes')
        hora = config.get('hour', 10)

        # Crear simulación
        rows = config.get('rows', 10)
        cols = config.get('cols', 12)
        store = build_store(rows=rows, cols=cols)
        sim = Simulation(store)

        # RESETEAR CONTADOR DE IDs ANTES DE CREAR CLIENTES
        Client._id_counter = 0
        print(f"✅ Contador de IDs reseteado a 0")

        # Determinar cuántos clientes crear
        clients_num = config.get('num_clients', None)
        if clients_num is None:
            clients_num = clientes_por_hora(dia, hora)
        
        print(f"👥 Se crearán {clients_num} clientes")

        # SIEMPRE CREAR CLIENTES NUEVOS 
        arrival_tick = 0
        pending_clients = []  
        
        for i in range(clients_num):
            new_tipo = calc_client_type(dia, hora)
            client = Client(
                patience=calc_paciencia(),
                tipo=new_tipo,
                velocidad=calc_speed(dia, hora, new_tipo)
            )
            client.move_delay = calc_move_delay(client.tipo, client.velocidad)
            client.assign_list(store)
            
            # Guardar total de items
            client.items_total = len(client.lista)
            
            # Programar llegada
            arrival_tick += intervalo_entre_clientes(lmbda=3)
            client.entry_tick = arrival_tick
            
            pending_clients.append(client)  # ✅ Agregar a lista temporal, NO a sim.clients
            print(f"  ✓ Cliente {client.id} creado: tipo={client.tipo}, items={client.items_total}, entrada_tick={arrival_tick}")

        print(f"📊 Total de clientes programados: {len(pending_clients)}")
        print(f"🕐 Ticks de entrada: {[c.entry_tick for c in pending_clients]}")
        
        # Valores de control
        max_ticks = config.get('max_ticks', 100)
        tick_delay = config.get('tick_delay', 0.5)

        # Cola de mensajes entrantes (comandos)
        msg_q: asyncio.Queue = asyncio.Queue()

        async def reader():
            try:
                while True:
                    txt = await websocket.receive_text()
                    await msg_q.put(txt)
            except WebSocketDisconnect:
                await msg_q.put('__ws_disconnect__')

        reader_task = asyncio.create_task(reader())

        paused = False
        stopped = False

        # pending_clients ya fue creada arriba con los clientes programados
        
        # Loop principal: ejecuta ticks cuando no esté en pausa; procesa comandos desde msg_q
        while sim.tick < max_ticks and not stopped:
            # Continuar si hay clientes pendientes de entrar O clientes activos en la simulación
            if not pending_clients and sim.all_done():
                print(f"✅ Todos los clientes terminaron en tick {sim.tick}")
                break
                
            # Procesar comandos pendientes (no bloqueante)
            while not msg_q.empty():
                raw = await msg_q.get()
                if raw == '__ws_disconnect__':
                    stopped = True
                    break
                try:
                    cmd = json.loads(raw)
                except Exception:
                    cmd = {'cmd': raw}

                action = cmd.get('cmd')
                if action == 'pause':
                    paused = True
                elif action == 'resume':
                    paused = False
                elif action == 'step':
                    # Force one step even if paused
                    paused = True
                    sim.step()
                    state = serialize_simulation_state(sim)
                    await websocket.send_text(json.dumps(state))
                elif action == 'stop':
                    stopped = True
                elif action == 'set_speed':
                    tick_delay = float(cmd.get('value', tick_delay))

            if stopped:
                break

            # Insertar clientes cuyo entry_tick coincide con el tick actual
            entering_now = [c for c in pending_clients if c.entry_tick == sim.tick]
            if entering_now:
                print(f"[Tick {sim.tick}] 🚪 {len(entering_now)} cliente(s) entrando ahora")
            for c in entering_now:
                sim.add_client(c, (0, 0))
                pending_clients.remove(c)
                print(f"  → Cliente {c.id} entró al supermercado")
            
            # Debug: mostrar pending cada 10 ticks
            if sim.tick % 10 == 0 and pending_clients:
                print(f"[Tick {sim.tick}] ⏳ Clientes pendientes: {len(pending_clients)}, próximos ticks: {sorted([c.entry_tick for c in pending_clients[:3]])}")

            if not paused:
                sim.step()
                state = serialize_simulation_state(sim)
                
                try:
                    await websocket.send_text(json.dumps(state))
                except Exception as e:
                    stopped = True
                    break
            else:
                # Still send current state occasionally so UI can show paused tick
                state = serialize_simulation_state(sim)
                try:
                    await websocket.send_text(json.dumps(state))
                except Exception as e:
                    stopped = True
                    break

            # Esperar por tick_delay o hasta que haya un comando nuevo
            try:
                await asyncio.wait_for(msg_q.get(), timeout=tick_delay)
            except asyncio.TimeoutError:
                # Normal timeout, continuar al siguiente tick
                pass
        try:
            print("📊 Generando gráficas...")
            from analytics import SimulationAnalytics
            
            # Recopilar datos
            analytics_data = sim.get_analytics_data()
            final_state_temp = serialize_simulation_state(sim)
            
            simulation_data = {
                'client_metrics': final_state_temp.get('client_metrics', []),
                'stats': final_state_temp.get('stats', {}),
                'checkout_utilization': analytics_data.get('checkout_utilization', {}),
                'queue_lengths': analytics_data.get('queue_lengths', {}),
                'occupancy_history': analytics_data.get('occupancy_history', [])
            }
            
            # Generar gráficas
            analytics = SimulationAnalytics(output_dir="resultados_simulacion")
            base_name = analytics.save_all_charts(simulation_data, prefix=f"{dia}_{hora}h")
            
            print(f"✅ Gráficas guardadas en: resultados_simulacion/{base_name}_*.png")
            
        except Exception as e:
            print(f"❌ Error generando gráficas: {e}")
            import traceback
            traceback.print_exc()
            
        # Enviar estado final
        try:
            final_state = serialize_simulation_state(sim)
            final_state['final'] = True
            await websocket.send_text(json.dumps(final_state))
            print(f"✅ Simulación terminada en tick {sim.tick}")
        except Exception as e:
            print(f"❌ Error enviando estado final: {e}")

        # Cerrar reader task
        reader_task.cancel()
        
    except WebSocketDisconnect:
        print("🔌 Cliente desconectado")
    
    except Exception as e:
        print(f"❌ Error en simulación: {e}")
        import traceback
        traceback.print_exc()
        try:
            await websocket.close()
        except Exception:
            pass
            pass

@app.get("/api/config/defaults")
async def get_defaults():
    """Retorna configuración por defecto"""
    return {
        "rows": 10,
        "cols": 12,
        "num_clients": 5,
        "max_ticks": 100,
        "tick_delay": 0.5
    }

if __name__ == "__main__":
    print("🚀 Iniciando servidor...")
    print("📱 Abre tu navegador en: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)