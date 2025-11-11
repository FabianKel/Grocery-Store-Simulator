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
let giftSaved = false;
let lastConsoleMap = null;
let lastClientMetrics = null;
let gifEnabled = false; // capture an animated gift by default (disabled)
let saveEnabled = false; // overall saving disabled when false
let gifEncoder = null;
let gifFramesCaptured = 0;
let gifCaptureEvery = 3; // capture every N ticks
let gifMaxFrames = 60; // safety cap
let currentTick = 0;
let currentTickDelayMs = 500;

startBtn.addEventListener('click', startSimulation);
pauseBtn.addEventListener('click', togglePause);
stepBtn.addEventListener('click', stepSimulation);
stopBtn.addEventListener('click', stopSimulation);
addClientBtn.addEventListener('click', addClientUI);

function startSimulation() {
    // reset auto-save flag for a fresh run
    giftSaved = false;
    const config = {
        rows: parseInt(document.getElementById('rows').value),
        cols: parseInt(document.getElementById('cols').value),
        num_clients: parseInt(document.getElementById('num_clients').value),
        tick_delay: parseFloat(document.getElementById('tick_delay').value),
        max_ticks: parseInt(document.getElementById('max_ticks').value),
        day: "viernes",
        hour: 10
    };
    // attach custom clients if provided
    if (localClients.length > 0) config.clients = localClients;
    console.log("AAAA")
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
        // prepare GIF encoder if enabled
        currentTick = 0;
        currentTickDelayMs = Math.max(50, Math.round((config.tick_delay || 0.5) * 1000));
        gifFramesCaptured = 0;
        if (gifEnabled && typeof GIF === 'function') {
            try {
                gifEncoder = new GIF({ workers: 2, quality: 10, workerScript: 'https://cdnjs.cloudflare.com/ajax/libs/gif.js/0.2.0/gif.worker.js' });
                gifEncoder.on('finished', function(blob) {
                    // convert blob to dataURL and POST to server
                    const reader = new FileReader();
                    reader.onloadend = async function() {
                        const dataUrl = reader.result;
                        if (!saveEnabled) {
                            console.info('save disabled: not posting gif');
                            return;
                        }
                        try {
                            const resp = await fetch('/api/save_gift', {
                                method: 'POST', headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ filename: `sim_gift_${Date.now()}.gif`, data_url: dataUrl })
                            });
                            const j = await resp.json();
                            console.info('gif saved result', j);
                        } catch (e) {
                            console.warn('failed to POST gif', e);
                        }
                    };
                    reader.readAsDataURL(blob);
                });
            } catch (e) {
                console.warn('GIF encoder init failed', e);
                gifEncoder = null;
            }
        }
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        // store latest metrics for gift rendering
        lastClientMetrics = data.client_metrics || null;
        drawSimulation(data);
        updateStats(data.stats);
        renderConsoleMap(data.console_map);
        // debug: log client_metrics to help diagnose missing times
        console.debug('client_metrics received:', data.client_metrics);
        renderClientMetrics(data.client_metrics);
        renderRawClientMetrics(data.client_metrics);
    // increment tick counter from server state if available
    try { currentTick = (data.stats && typeof data.stats.tick === 'number') ? data.stats.tick : currentTick + 1; } catch(e) {}
        // render charts; if all finished, auto-post the combined PNG to the server once
        try {
            renderClientTimesChart(data.client_metrics);
            renderItemsVsTimeChart(data.client_metrics);
            const allFinished = (data.client_metrics || []).length > 0 && (data.client_metrics || []).every(c => c.total_time !== null && c.total_time !== undefined);
            if (allFinished && !giftSaved) {
                if (saveEnabled) {
                    try { requestGifSave(); } catch(e) { console.warn('requestGifSave failed', e); }
                    giftSaved = true;
                } else {
                    console.info('saving disabled: not saving gift on allFinished');
                }
            }
            // also respect explicit final flag from server (save snapshot even if not all finished)
            if (data.final && !giftSaved) {
                if (saveEnabled) {
                    try { requestGifSave(); } catch(e) { console.warn('requestGifSave failed (final)', e); }
                    giftSaved = true;
                } else {
                    console.info('saving disabled: not saving gift on final');
                }
            }
        } catch(e){ console.warn('chart render error', e); }
        // capture a GIF frame periodically
        try {
            if (saveEnabled && gifEnabled && gifEncoder && !giftSaved && gifFramesCaptured < gifMaxFrames && (currentTick % gifCaptureEvery) === 0) {
                const combined = createCombinedCanvas();
                if (combined) {
                    try {
                        gifEncoder.addFrame(combined, { copy: true, delay: currentTickDelayMs });
                        gifFramesCaptured += 1;
                    } catch (e) {
                        console.warn('gif addFrame failed', e);
                    }
                }
            }
        } catch(e) { /* ignore */ }
    };

    ws.onclose = () => {
        startBtn.disabled = false;
        pauseBtn.disabled = true;
        stepBtn.disabled = true;
        stopBtn.disabled = true;
        statusEl.innerHTML = '⏸️ Simulación detenida';
        statusEl.classList.remove('running');
        // if the connection closed and we haven't saved the gift yet, try to auto-save current charts
        if (!giftSaved) {
            if (saveEnabled) {
                try { requestGifSave(); } catch(e) { console.warn('requestGifSave failed (close)', e); }
                giftSaved = true;
            } else {
                console.info('saving disabled: not saving gift on close');
            }
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        statusEl.innerHTML = '❌ Error en la conexión';
    };
}

// Render leaderboard HTML-like table into a canvas and return the canvas
function renderLeaderboardToCanvas(metrics, targetWidth) {
    const cols = ['ID','Tipo','Velocidad','Items','Start','Finish','Total'];
    const rowHeight = 20;
    const headerHeight = 28;
    const padding = 8;
    const font = '12px Arial';

    const n = (metrics && metrics.length) ? metrics.length : 0;
    const colWidths = [50,80,80,50,50,50,50];
    const tableWidth = colWidths.reduce((a,b)=>a+b,0) + padding*2;
    const canvasWidth = Math.max(targetWidth || 640, tableWidth);
    const canvasHeight = padding*2 + headerHeight + n * rowHeight + 6;

    const c = document.createElement('canvas');
    c.width = canvasWidth;
    c.height = canvasHeight;
    const ctx = c.getContext('2d');
    // background
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0,0,c.width,c.height);
    // header
    ctx.fillStyle = '#f3f4f6';
    ctx.fillRect(padding, padding, canvasWidth - padding*2, headerHeight);
    ctx.fillStyle = '#333';
    ctx.font = 'bold 12px Arial';
    let x = padding;
    for (let i=0;i<cols.length;i++){
        ctx.fillText(cols[i], x + 4, padding + 18);
        x += colWidths[i];
    }

    // rows
    ctx.font = font;
    let y = padding + headerHeight + 4;
    if (metrics && metrics.length) {
        metrics.forEach(m => {
            x = padding;
            const values = [m.id || '', m.tipo || '', m.velocidad || '', String(m.items_left || 0), String(m.start_tick || ''), String(m.finish_tick || ''), m.total_time !== null && m.total_time !== undefined ? String(m.total_time) : ''];
            for (let i=0;i<values.length;i++){
                ctx.fillStyle = '#111';
                ctx.fillText(values[i], x + 4, y + 14);
                x += colWidths[i];
            }
            y += rowHeight;
        });
    } else {
        ctx.fillStyle = '#666';
        ctx.fillText('— sin datos —', padding + 6, padding + headerHeight + 18);
    }

    // border
    ctx.strokeStyle = '#e5e7eb';
    ctx.strokeRect(padding, padding, canvasWidth - padding*2, canvasHeight - padding*2);
    return c;
}

// --- Chart rendering for client times (simple bar chart) ---
function renderClientTimesChart(metrics) {
    const canvas = document.getElementById('client-times-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    // clear
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0,0,canvas.width,canvas.height);

    if (!metrics || metrics.length === 0) {
        ctx.fillStyle = '#666';
        ctx.font = '14px Arial';
        ctx.fillText('No hay datos para graficar todavía', 12, 30);
        return;
    }
    // build structured data: include tipo and items
    const data = metrics.map(m => ({
        id: m.id || '',
        time: (m.total_time !== null && m.total_time !== undefined) ? m.total_time : null,
        items: (m.items_total !== undefined && m.items_total !== null) ? m.items_total : (typeof m.items_left === 'number' ? m.items_left : 0),
        tipo: m.tipo || 'solo'
    }));

    const padding = 32;
    const w = canvas.width - padding * 2;
    const h = canvas.height - padding * 2;
    const barGap = 12;
    const n = data.length;
    const barW = Math.max(18, (w - (n - 1) * barGap) / n);

    // compute max time using finished clients only
    const maxTime = Math.max(1, ...data.map(d => d.time || 0));

    // draw baseline
    ctx.strokeStyle = '#eee';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding + h);
    ctx.lineTo(padding + w, padding + h);
    ctx.stroke();

    // draw bars: finished = solid colored, unfinished = light outline placeholder
    data.forEach((d, i) => {
        const bx = padding + i * (barW + barGap);
        const by = padding + h;
        const value = d.time;
        const barH = value ? Math.max(6, (value / maxTime) * (h - 40)) : 0;

        // color by tipo
        const color = d.tipo === 'familia' ? 'rgba(245,87,108,0.95)' : 'rgba(59,130,246,0.95)';

        if (value) {
            ctx.fillStyle = color;
            ctx.fillRect(bx, by - barH, barW, barH);
            // label value above bar
            ctx.fillStyle = '#111';
            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(String(d.time), bx + barW/2, by - barH - 8);
        } else {
            ctx.strokeStyle = '#e6e6e6';
            ctx.lineWidth = 2;
            ctx.strokeRect(bx, by - (h - 40), barW, h - 40);
            ctx.fillStyle = '#888';
            ctx.font = '11px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('pendiente', bx + barW/2, by - (h - 40) + 10);
        }

        // label: id and items below
        ctx.fillStyle = '#333';
        ctx.font = '12px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(`${d.id} (${d.items})`, bx + barW/2, by + 14);
    });

    // caption
    ctx.fillStyle = '#444';
    ctx.font = '13px Arial';
    ctx.textAlign = 'left';
    ctx.fillText('Tiempo total (s) — barras coloreadas por tipo; (items) debajo de cada barra', padding, 16);
}

async function autoSaveGift() {
    // Saving is disabled by default. Short-circuit to avoid any network activity.
    if (!saveEnabled) {
        return { error: 'saving disabled' };
    }
    const tmp = createCombinedCanvas();
    if (!tmp) return { error: 'no visual content' };
    const url = tmp.toDataURL('image/png');
    try {
        const resp = await fetch('/api/save_gift', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: `sim_gift_${Date.now()}.gif`, data_url: url })
        });
        return await resp.json();
    } catch (e) {
        return { error: String(e) };
    }
}

// requestGifSave: ensure a GIF encoder exists, add a frame if none captured, then render and let the finished handler POST the .gif
function requestGifSave() {
    if (!saveEnabled) {
        console.info('requestGifSave: saving disabled, skipping');
        return;
    }
    // if gif.js not available, fallback to posting a PNG but use .gif extension as requested
    if (!gifEnabled) {
    // still produce PNG but with .gif extension (filename only)
    createCombinedCanvas();
    autoSaveGift().then(r=>console.info('fallback png (as .gif) saved', r)).catch(e=>console.warn(e));
        return;
    }

    // ensure encoder exists
    if (!gifEncoder && typeof GIF === 'function') {
        try {
            gifEncoder = new GIF({ workers: 2, quality: 10, workerScript: 'https://cdnjs.cloudflare.com/ajax/libs/gif.js/0.2.0/gif.worker.js' });
            gifEncoder.on('finished', function(blob) {
                const reader = new FileReader();
                reader.onloadend = async function() {
                    const dataUrl = reader.result;
                    if (!saveEnabled) {
                        console.info('save disabled: not posting gif');
                        return;
                    }
                    try {
                        const resp = await fetch('/api/save_gift', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ filename: `sim_gift_${Date.now()}.gif`, data_url: dataUrl })
                        });
                        const j = await resp.json();
                        console.info('gif saved result', j);
                    } catch (e) {
                        console.warn('failed to POST gif', e);
                    }
                };
                reader.readAsDataURL(blob);
            });
        } catch (e) {
            console.warn('GIF encoder init failed in requestGifSave', e);
            gifEncoder = null;
        }
    }

    // add a frame if none captured yet
    if (gifEncoder && gifFramesCaptured === 0) {
        const combined = createCombinedCanvas();
        if (combined) {
            try {
                gifEncoder.addFrame(combined, { copy: true, delay: currentTickDelayMs });
                gifFramesCaptured += 1;
            } catch (e) {
                console.warn('gif addFrame failed in requestGifSave', e);
            }
        }
    }

    // if we have an encoder, render it; otherwise fallback to PNG POST with .gif suffix
    if (gifEncoder) {
        try {
            gifEncoder.render();
        } catch (e) {
            console.warn('gif render failed in requestGifSave', e);
            // fallback PNG
            autoSaveGift().then(r=>console.info('fallback png (as .gif) saved', r)).catch(e=>console.warn(e));
        }
    } else {
    autoSaveGift().then(r=>console.info('fallback png (as .gif) saved', r)).catch(e=>console.warn(e));
    }
}

// createCombinedCanvas: builds the combined snapshot (simulation + console + leaderboard + charts)
function createCombinedCanvas() {
    const simCanvas = document.querySelector('#simulation-canvas canvas');
    const c1 = document.getElementById('client-times-chart');
    const c2 = document.getElementById('items-vs-time-chart');
    if (!simCanvas && !c1 && !c2) return null;

    const widths = [simCanvas ? simCanvas.width : 0, c1 ? c1.width : 0, c2 ? c2.width : 0];
    const w = Math.max(...widths, 640);

    const simH = simCanvas ? simCanvas.height : 0;
    const consoleLines = lastConsoleMap ? String(lastConsoleMap).split('\n').slice(0,20) : [];
    const lineHeight = 14;
    const consoleH = consoleLines.length * lineHeight + (consoleLines.length > 0 ? 12 : 0);
    const c1h = c1 ? c1.height : 0;
    const c2h = c2 ? c2.height : 0;

    const leaderboardCanvas = typeof renderLeaderboardToCanvas === 'function' ? renderLeaderboardToCanvas(lastClientMetrics, w) : null;
    const lbH = leaderboardCanvas ? leaderboardCanvas.height : 0;

    const padding = 8;
    const totalH = simH + consoleH + lbH + c1h + c2h + padding * 6;

    const tmp = document.createElement('canvas');
    tmp.width = w;
    tmp.height = totalH;
    const tctx = tmp.getContext('2d');
    tctx.fillStyle = '#ffffff';
    tctx.fillRect(0,0,tmp.width,tmp.height);

    let y = padding;
    if (simCanvas) {
        const sx = Math.floor((w - simCanvas.width)/2);
        tctx.drawImage(simCanvas, sx, y);
        y += simCanvas.height + padding;
    }

    if (consoleLines.length > 0) {
        tctx.fillStyle = '#f6f6f6';
        tctx.fillRect(padding, y, w - padding*2, consoleH);
        tctx.fillStyle = '#111';
        tctx.font = `${lineHeight - 2}px monospace`;
        tctx.textBaseline = 'top';
        for (let i=0;i<consoleLines.length;i++) {
            const line = consoleLines[i];
            tctx.fillText(line, padding + 6, y + 6 + i * lineHeight);
        }
        y += consoleH + padding;
    }

    if (leaderboardCanvas) {
        const lx = Math.floor((w - leaderboardCanvas.width)/2);
        tctx.drawImage(leaderboardCanvas, lx, y);
        y += leaderboardCanvas.height + padding;
    }

    if (c1) {
        const cx = Math.floor((w - c1.width)/2);
        tctx.drawImage(c1, cx, y);
        y += c1.height + padding;
    }
    if (c2) {
        const cx2 = Math.floor((w - c2.width)/2);
        tctx.drawImage(c2, cx2, y);
        y += c2.height + padding;
    }

    return tmp;
}

// No manual download button: charts will be auto-saved to server when simulation finishes

// --- Chart B: Items vs Time scatter plot ---
function renderItemsVsTimeChart(metrics) {
    const canvas = document.getElementById('items-vs-time-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#fff';
    ctx.fillRect(0,0,canvas.width,canvas.height);

    if (!metrics || metrics.length === 0) {
        ctx.fillStyle = '#666';
        ctx.font = '14px Arial';
        ctx.fillText('No hay datos para graficar todavía', 12, 30);
        return;
    }

    // prepare points: x = items (prefer items_total), y = total_time (seconds)
    const pts = metrics.map(m => ({
        id: m.id || '',
        items: (m.items_total !== undefined && m.items_total !== null) ? m.items_total : (typeof m.items_left === 'number' ? m.items_left : 0),
        time: (m.total_time !== null && m.total_time !== undefined) ? m.total_time : null,
        tipo: m.tipo || 'solo'
    }));

    // layout
    const padding = 50;
    const w = canvas.width - padding * 2;
    const h = canvas.height - padding * 2;
    // compute domain using finished clients for time, but include items from all for domain
    const maxItems = Math.max(1, ...pts.map(p => (typeof p.items === 'number' ? p.items : 0)));
    const maxTime = Math.max(1, ...pts.map(p => (typeof p.time === 'number' ? p.time : 0)));

    // draw grid and axes
    ctx.strokeStyle = '#eee'; ctx.lineWidth = 1;
    // vertical grid lines (items)
    const itemSteps = Math.min(6, Math.max(2, Math.ceil(maxItems / 2)));
    for (let i=0;i<=itemSteps;i++){
        const xi = padding + (i / itemSteps) * w;
        ctx.beginPath(); ctx.moveTo(xi, padding); ctx.lineTo(xi, padding + h); ctx.stroke();
        const labelVal = Math.round((i / itemSteps) * maxItems);
        ctx.fillStyle = '#888'; ctx.font = '11px Arial'; ctx.textAlign = 'center'; ctx.fillText(labelVal, xi, padding + h + 18);
    }
    // horizontal grid lines (time)
    const timeSteps = Math.min(6, Math.max(2, Math.ceil(maxTime / 5)));
    for (let j=0;j<=timeSteps;j++){
        const yj = padding + (j / timeSteps) * h;
        ctx.beginPath(); ctx.moveTo(padding, yj); ctx.lineTo(padding + w, yj); ctx.stroke();
        const tval = Math.round(maxTime * (1 - j / timeSteps));
        ctx.fillStyle = '#888'; ctx.font = '11px Arial'; ctx.textAlign = 'right'; ctx.fillText(tval, padding - 8, yj + 4);
    }

    // draw points; add slight jitter to x-position to avoid exact overlaps and color by tipo
    pts.forEach((p, idx) => {
        if (p.time === null) return; // only plot finished ones
        const baseX = padding + (p.items / maxItems) * w;
        const jitter = ((idx * 37) % 10 - 5) / 100 * w * 0.02; // deterministic small jitter
        const x = baseX + jitter;
        const y = padding + h - ((p.time / Math.max(1, maxTime)) * h);
        const r = 6 + Math.min(10, p.items * 0.6);
        const color = p.tipo === 'familia' ? 'rgba(245,87,108,0.9)' : 'rgba(59,130,246,0.9)';
        ctx.fillStyle = color;
        ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI*2); ctx.fill();
        ctx.fillStyle = '#111'; ctx.font = '11px Arial'; ctx.textAlign = 'center'; ctx.fillText(`${p.id}`, x, y - r - 6);
        // small label with (items)
        ctx.fillStyle = '#333'; ctx.font = '10px Arial'; ctx.fillText(`(${p.items})`, x, y + r + 12);
    });

    // axis labels and caption
    ctx.fillStyle = '#444'; ctx.font = '13px Arial'; ctx.textAlign = 'center';
    ctx.fillText('Items →', padding + w/2, padding + h + 36);
    ctx.save(); ctx.translate(18, padding + h/2); ctx.rotate(-Math.PI/2); ctx.textAlign = 'center'; ctx.fillText('Tiempo (s)', 0, 0); ctx.restore();
    ctx.fillStyle = '#666'; ctx.font = '11px Arial'; ctx.textAlign = 'left';
    ctx.fillText('(Cada punto = cliente)', padding, 16);
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
        lastConsoleMap = null;
    } else {
        el.textContent = consoleMap;
        lastConsoleMap = consoleMap;
    }
    // update console control visibility after content changes
    requestAnimationFrame(updateConsoleControlsVisibility);
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

// Console scroll controls (for browsers that hide scrollbars)
function updateConsoleControlsVisibility() {
    const pre = document.getElementById('console-map');
    const hControls = document.querySelector('.console-controls');
    const vControls = document.querySelector('.console-controls-vertical');
    if (!pre) return;
    // detect overflow
    const overflowX = pre.scrollWidth > pre.clientWidth + 2;
    const overflowY = pre.scrollHeight > pre.clientHeight + 2;
    if (hControls) hControls.setAttribute('aria-hidden', overflowX ? 'false' : 'true');
    if (vControls) vControls.setAttribute('aria-hidden', overflowY ? 'false' : 'true');
}

function scrollConsoleBy(px) {
    const pre = document.getElementById('console-map');
    if (!pre) return;
    pre.scrollBy({ left: px, behavior: 'smooth' });
}

document.addEventListener('DOMContentLoaded', ()=>{
    const left = document.getElementById('console-scroll-left');
    const right = document.getElementById('console-scroll-right');
    const up = document.getElementById('console-scroll-up');
    const down = document.getElementById('console-scroll-down');
    if (left) left.addEventListener('click', ()=> scrollConsoleBy(-300));
    if (right) right.addEventListener('click', ()=> scrollConsoleBy(300));
    if (up) up.addEventListener('click', ()=> scrollConsoleBy(0, -200));
    if (down) down.addEventListener('click', ()=> scrollConsoleBy(0, 200));
    // also update on resize
    window.addEventListener('resize', updateConsoleControlsVisibility);
    // initial check
    setTimeout(updateConsoleControlsVisibility, 300);
});

// allow vertical scroll when passed explicitly; keep existing horizontal behavior
function scrollConsoleBy(px = 0, py = 0) {
    const pre = document.getElementById('console-map');
    if (!pre) return;
    // use smooth scrolling for both axes when supported
    pre.scrollBy({ left: px, top: py, behavior: 'smooth' });
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

