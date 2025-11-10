let ws = null;
let canvas = null;
let ctx = null;
let cellSize = 50;

const startBtn = document.getElementById('startBtn');
const pauseBtn = document.getElementById('pauseBtn');
const stepBtn = document.getElementById('stepBtn');
const stopBtn = document.getElementById('stopBtn');
const addClientBtn = document.getElementById('addClientBtn');
const clientListUI = document.getElementById('client-list-ui');
const statusEl = document.getElementById('status');

let localClients = [];

startBtn.addEventListener('click', startSimulation);
pauseBtn.addEventListener('click', togglePause);
stepBtn.addEventListener('click', stepSimulation);
stopBtn.addEventListener('click', stopSimulation);
addClientBtn.addEventListener('click', addClientUI);

function startSimulation() {
    const config = {
        rows: parseInt(document.getElementById('rows').value),
        cols: parseInt(document.getElementById('cols').value),
        num_clients: parseInt(document.getElementById('num_clients').value),
        tick_delay: parseFloat(document.getElementById('tick_delay').value),
        max_ticks: parseInt(document.getElementById('max_ticks').value)
    };
    // attach custom clients if provided
    if (localClients.length > 0) config.clients = localClients;

    const canvasContainer = document.getElementById('simulation-canvas');
    canvasContainer.innerHTML = '';
    canvas = document.createElement('canvas');
    canvas.width = config.cols * cellSize;
    canvas.height = config.rows * cellSize;
    canvasContainer.appendChild(canvas);
    ctx = canvas.getContext('2d');

    ws = new WebSocket(`ws://${location.host}/ws/simulate`);

    ws.onopen = () => {
        startBtn.disabled = true;
        pauseBtn.disabled = false;
        stepBtn.disabled = false;
        stopBtn.disabled = false;
        statusEl.innerHTML = '▶️ Simulación en progreso...';
        statusEl.classList.add('running');
        ws.send(JSON.stringify(config));
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        drawSimulation(data);
        updateStats(data.stats);
        renderConsoleMap(data.console_map);
        // debug: log client_metrics to help diagnose missing times
        console.debug('client_metrics received:', data.client_metrics);
        renderClientMetrics(data.client_metrics);
        renderRawClientMetrics(data.client_metrics);
    };

    ws.onclose = () => {
        startBtn.disabled = false;
        pauseBtn.disabled = true;
        stepBtn.disabled = true;
        stopBtn.disabled = true;
        statusEl.innerHTML = '⏸️ Simulación detenida';
        statusEl.classList.remove('running');
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        statusEl.innerHTML = '❌ Error en la conexión';
    };
}

function stopSimulation() {
    if (ws) ws.close();
}

function drawSimulation(data) {
    if (!ctx) return;
    const { cells, rows, cols } = data;
    cellSize = Math.min(800 / cols, 600 / rows, 60);
    canvas.width = cols * cellSize;
    canvas.height = rows * cellSize;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < rows; i++) {
        for (let j = 0; j < cols; j++) {
            const cell = cells[i][j];
            const x = j * cellSize;
            const y = i * cellSize;

            let color = '#e5e7eb';
            if (cell.type === 'entrance') color = '#4ade80';
            else if (cell.type === 'exit') color = '#f87171';
            else if (cell.type === 'shelf') color = '#fbbf24';
            else if (cell.type === 'checkout') color = '#60a5fa';
            else if (cell.type === 'obstacle') color = '#6b7280';

            if (cell.type === 'aisle' && cell.occupancy > 0) {
                ctx.fillStyle = '#e5e7eb';
                ctx.fillRect(x, y, cellSize, cellSize);
                const darkness = Math.min(0.6, cell.occupancy * 0.6);
                ctx.fillStyle = `rgba(0,0,0,${darkness})`;
                ctx.fillRect(x, y, cellSize, cellSize);
            } else {
                ctx.fillStyle = color;
                ctx.fillRect(x, y, cellSize, cellSize);
            }

            ctx.strokeStyle = '#d1d5db';
            ctx.lineWidth = 1;
            ctx.strokeRect(x, y, cellSize, cellSize);

            if (cell.type === 'shelf' && cell.category) {
                ctx.fillStyle = 'white';
                ctx.font = `bold ${Math.max(10, cellSize * 0.16)}px Arial`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(cell.category.substring(0, 3), x + cellSize/2, y + cellSize/2);
            }

            if (cell.clients && cell.clients.length > 0) {
                cell.clients.forEach((client, idx) => {
                    const offsetX = (idx % 2) * (cellSize * 0.3) - cellSize * 0.15;
                    const offsetY = Math.floor(idx / 2) * (cellSize * 0.3) - cellSize * 0.15;
                    const clientColor = client.tipo === 'familia' ? '#f5576c' : '#667eea';
                    const radius = cellSize * 0.18;

                    ctx.fillStyle = clientColor;
                    ctx.beginPath();
                    ctx.arc(x + cellSize/2 + offsetX, y + cellSize/2 + offsetY, radius, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.strokeStyle = 'white';
                    ctx.lineWidth = 2;
                    ctx.stroke();

                    // Emoji for family/solo and small ID below
                    ctx.font = `${Math.max(12, cellSize * 0.14)}px serif`;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    const emoji = client.tipo === 'familia' ? '👪' : '🙂';
                    ctx.fillText(emoji, x + cellSize/2 + offsetX, y + cellSize/2 + offsetY - 2);
                    ctx.font = `${Math.max(10, cellSize * 0.12)}px Arial`;
                    ctx.fillText(client.id ?? '', x + cellSize/2 + offsetX, y + cellSize/2 + offsetY + cellSize*0.18);
                });
            }

            if (cell.queue && cell.queue.length > 0) {
                cell.queue.forEach((client, idx) => {
                    const queueY = y - (idx + 1) * cellSize * 0.25;
                    if (queueY >= 0) {
                        const clientColor = client.tipo === 'familia' ? '#f5576c' : '#667eea';
                        const radius = cellSize * 0.12;
                        ctx.fillStyle = clientColor;
                        ctx.globalAlpha = 0.9;
                        ctx.beginPath();
                        ctx.arc(x + cellSize/2, queueY, radius, 0, Math.PI * 2);
                        ctx.fill();
                        ctx.globalAlpha = 1;
                        ctx.strokeStyle = 'white';
                        ctx.lineWidth = 2;
                        ctx.stroke();
                        ctx.font = `${Math.max(10, cellSize * 0.12)}px serif`;
                        ctx.fillStyle = 'white';
                        ctx.fillText(client.tipo === 'familia' ? '👪' : '🙂', x + cellSize/2, queueY + 1);
                    }
                });
            }
        }
    }
}

function updateStats(stats) {
    document.getElementById('tick-count').textContent = stats.tick;
    document.getElementById('active-count').textContent = stats.active_clients;
    document.getElementById('shopping-count').textContent = stats.clients_shopping;
    document.getElementById('queue-count').textContent = stats.clients_in_queue;
}

function renderConsoleMap(consoleMap) {
    const el = document.getElementById('console-map');
    if (!el) return;
    if (consoleMap === null || consoleMap === undefined) {
        el.textContent = '-- mapa no disponible --';
    } else {
        el.textContent = consoleMap;
    }
}

function renderClientMetrics(metrics) {
    const table = document.getElementById('client-metrics-table');
    if (!table) return;
    const tbody = table.querySelector('tbody');
    tbody.innerHTML = '';
    if (!metrics || metrics.length === 0) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td colspan="7" style="padding:12px; text-align:center; color:#666">— sin datos aún —</td>`;
        tbody.appendChild(tr);
        return;
    }

    // Sort: finished first by total_time asc, then by start_tick
    const sorted = metrics.slice().sort((a,b)=>{
        const ta = a.total_time !== null ? a.total_time : 1e9;
        const tb = b.total_time !== null ? b.total_time : 1e9;
        if (ta !== tb) return ta - tb;
        return (a.start_tick || 0) - (b.start_tick || 0);
    });

    sorted.forEach(c=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="padding:6px">${c.id ?? ''}</td>
            <td style="padding:6px">${c.tipo ?? ''}</td>
            <td style="padding:6px">${c.velocidad ?? ''}</td>
            <td style="padding:6px; text-align:right">${c.items_left ?? ''}</td>
            <td style="padding:6px; text-align:right">${c.start_tick ?? ''}</td>
            <td style="padding:6px; text-align:right">${c.finish_tick ?? ''}</td>
            <td style="padding:6px; text-align:right">${c.total_time !== null && c.total_time !== undefined ? c.total_time : ''}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderRawClientMetrics(metrics) {
    const el = document.getElementById('raw-client-metrics');
    if (!el) return;
    try {
        el.textContent = JSON.stringify(metrics || [], null, 2);
    } catch (e) {
        el.textContent = String(metrics);
    }
}

// UI: add client
function addClientUI() {
    const id = localClients.length + 1;
    const tipo = prompt('Tipo de cliente (solo/familia)', 'solo') || 'solo';
    const velocidad = prompt('Velocidad (Rapido/Normal/Tranquilo)', 'Normal') || 'Normal';
    const patience = parseFloat(prompt('Patience (0.1-1.0)', '0.8') || '0.8');
    const c = { id, tipo, velocidad, patience };
    localClients.push(c);
    renderClientList();
}

function renderClientList() {
    clientListUI.innerHTML = '';
    localClients.forEach((c, idx) => {
        const el = document.createElement('div');
        el.style.padding = '6px';
        el.style.borderBottom = '1px solid #eee';
        el.innerHTML = `<strong>#${c.id}</strong> ${c.tipo} • ${c.velocidad} • p=${c.patience.toFixed(2)} <button data-idx="${idx}" style="float:right">❌</button>`;
        clientListUI.appendChild(el);
        el.querySelector('button').addEventListener('click', (e)=>{ localClients.splice(idx,1); renderClientList(); });
    });
}

// control commands
function togglePause(){ if(!ws) return; ws.send(JSON.stringify({cmd:'pause'})); statusEl.innerText='⏸️ Pausado'; }
function stepSimulation(){ if(!ws) return; ws.send(JSON.stringify({cmd:'step'})); statusEl.innerText='⏭️ Paso'; }
function stopSimulation(){ if(ws){ ws.send(JSON.stringify({cmd:'stop'})); ws.close(); } }

