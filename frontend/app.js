/* ═══════════════════════════════════════════════════════════════
   Smart Logistics Intelligence — Frontend JavaScript (Geocoding + VRP)
   ═══════════════════════════════════════════════════════════════ */

const API_BASE = window.location.origin.startsWith("file") ? "http://localhost:8080" : window.location.origin;

let locationState = {
    source: null,
    destinations: [null]
};

let leafletMap = null;
let mapLayerGroup = null;

const RISK_COLORS = { low: "#10b981", medium: "#f59e0b", high: "#f97316", very_high: "#ef4444" };

let HUB_LIST = [];

const EXAMPLES = {
    low:     { source: "Jaipur", dests: ["Ajmer"], hour: 14, month: 1, day: 15, vehicle: "van", cargo: "standard", priority: 2 },
    medium:  { source: "Delhi", dests: ["Agra"], hour: 8, month: 11, day: 15, vehicle: "truck", cargo: "standard", priority: 2 },
    high:    { source: "Jaipur", dests: ["Lucknow"], hour: 8, month: 7, day: 15, vehicle: "bike", cargo: "perishable", priority: 3 },
    extreme: { source: "Mumbai", dests: ["Pune", "Nashik"], hour: 17, month: 7, day: 15, vehicle: "truck", cargo: "perishable", priority: 3 },
};

document.addEventListener("DOMContentLoaded", () => {
    initHourSelector();
    initDateSelector();
    checkHealth();
    updateHourBadge();
    document.getElementById("depHour").addEventListener("change", updateHourBadge);
});

function initHourSelector() {
    const sel = document.getElementById("depHour");
    sel.innerHTML = "";
    for (let h = 0; h < 24; h++) {
        const opt = document.createElement("option");
        opt.value = h;
        const label = h === 0 ? "12 AM" : h < 12 ? `${h} AM` : h === 12 ? "12 PM" : `${h - 12} PM`;
        opt.textContent = `${label}`;
        if (h === new Date().getHours()) opt.selected = true;
        sel.appendChild(opt);
    }
}

function initDateSelector() { document.getElementById("depDate").value = new Date().toISOString().split("T")[0]; }

function updateHourBadge() {
    const hour = parseInt(document.getElementById("depHour").value);
    const badge = document.getElementById("hourBadge");
    if ([7, 8, 9, 17, 18, 19].includes(hour)) { badge.textContent = "Peak hour — higher delay risk"; badge.className = "hour-badge peak"; }
    else if (hour >= 0 && hour <= 5) { badge.textContent = "Night — low traffic"; badge.className = "hour-badge night"; }
    else { badge.textContent = "Off-peak — lower delay risk"; badge.className = "hour-badge"; }
}

async function checkHealth() {
    try {
        const [healthRes, hubsRes] = await Promise.all([
            fetch(`${API_BASE}/health`),
            fetch(`${API_BASE}/hubs`)
        ]);
        const data = await healthRes.json();
        const hubsData = await hubsRes.json();
        HUB_LIST = hubsData.hub_details;
        document.querySelector(".status-dot").classList.add("connected");
        document.getElementById("statusText").textContent = `${data.model_name.replace(/_/g, " ")} (${HUB_LIST.length} Hubs)`;
        
        initLocations();
    } catch { document.getElementById("statusText").textContent = "API offline"; }
}

// ── Hub Dropdown Setup ──────────────────────────────────────────
function initLocations() {
    populateSelect(document.getElementById("sourceInput"));
    populateSelect(document.getElementById("destInput0"));
    locationState.source = document.getElementById("sourceInput").value;
    locationState.destinations[0] = document.getElementById("destInput0").value;

    document.getElementById("sourceInput").addEventListener("change", (e) => locationState.source = e.target.value);
    document.getElementById("destInput0").addEventListener("change", (e) => locationState.destinations[0] = e.target.value);
}

function populateSelect(selectEl) {
    selectEl.innerHTML = "";
    HUB_LIST.sort((a,b) => a.city.localeCompare(b.city)).forEach(h => {
        const opt = document.createElement("option");
        opt.value = h.city;
        opt.textContent = `${h.city} (${h.type === 'warehouse' ? 'Warehouse' : 'Hub'})`;
        selectEl.appendChild(opt);
    });
}

function addDestinationStop() {
    if (locationState.destinations.length >= 6) { showError("Maximum 6 stops supported."); return; }
    const i = locationState.destinations.length;
    locationState.destinations.push(null);
    const container = document.getElementById("destinationsContainer");
    container.insertAdjacentHTML('beforeend', `
        <div class="form-group dest-group" id="destGroup${i}">
            <label class="form-label" for="destInput${i}">Destination ${i+1}</label>
            <select id="destInput${i}" class="form-select dest-select"></select>
        </div>`);
    
    const sel = document.getElementById(`destInput${i}`);
    populateSelect(sel);
    // Select the second city as default just to avoid duplicates initially
    if (HUB_LIST.length > i) sel.selectedIndex = i;
    locationState.destinations[i] = sel.value;
    
    sel.addEventListener("change", (e) => locationState.destinations[i] = e.target.value);
}

// ── Tab Management ───────────────────────────────────────────────────────
function switchTab(tab) {
    document.getElementById("analysisTab").style.display = tab === "analysis" ? "" : "none";
    document.getElementById("historyTab").style.display = tab === "history" ? "" : "none";
    document.getElementById("tabAnalysis").classList.toggle("active", tab === "analysis");
    document.getElementById("tabHistory").classList.toggle("active", tab === "history");
    if (tab === "history") loadHistory();
}

function loadExample(key) {
    const ex = EXAMPLES[key]; if (!ex) return;
    
    // Set source
    locationState.source = ex.source;
    document.getElementById("sourceInput").value = ex.source;

    // Reset destinations
    locationState.destinations = [ex.dests[0]];
    document.getElementById("destinationsContainer").innerHTML = `
        <div class="form-group dest-group" id="destGroup0">
            <label class="form-label" for="destInput0">Destination 1</label>
            <select id="destInput0" class="form-select dest-select"></select>
        </div>`;
    
    const sel0 = document.getElementById("destInput0");
    populateSelect(sel0);
    sel0.value = ex.dests[0];
    sel0.addEventListener("change", (e) => locationState.destinations[0] = e.target.value);

    // Add extra stops if VRB example
    for (let i = 1; i < ex.dests.length; i++) {
        addDestinationStop();
        locationState.destinations[i] = ex.dests[i];
        document.getElementById(`destInput${i}`).value = ex.dests[i];
    }

    document.getElementById("depHour").value = ex.hour;
    document.getElementById("vehicleType").value = ex.vehicle;
    document.getElementById("cargoType").value = ex.cargo;
    document.getElementById("priority").value = ex.priority;
    document.getElementById("depDate").value = `2024-${String(ex.month).padStart(2,"0")}-${String(ex.day).padStart(2,"0")}`;
    updateHourBadge();
}

// ── API Calling ──────────────────────────────────────────────────────────
async function runAnalysis() {

    if (!locationState.source) {
        showError("Please select an Origin Location.");
        return;
    }

    const validDests = locationState.destinations.filter(d => d !== null);

    if (!validDests.length) {
        showError("Please select at least one Destination.");
        return;
    }

    const payload = {
        source: locationState.source,
        destinations: validDests,
        departure_time: `${document.getElementById("depDate").value}T${String(document.getElementById("depHour").value).padStart(2,"0")}:00:00`,
        vehicle_type: document.getElementById("vehicleType").value,
        cargo_type: document.getElementById("cargoType").value,
        priority_level: parseInt(document.getElementById("priority").value),
    };

    document.getElementById("placeholder").style.display = "none";
    document.getElementById("results").style.display = "none";
    document.getElementById("loading").style.display = "block";
    document.getElementById("runBtn").disabled = true;

    try {

        const res = await fetch(`${API_BASE}/predict-route`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            const errMsg = Array.isArray(err.detail) ? err.detail.map(d => d.msg).join(", ") : (err.detail || "Route prediction failed");
            throw new Error(errMsg);
        }

        const fleetData = await res.json();

        console.log("API RESPONSE:", fleetData); // 🔥 DEBUG

        document.getElementById("loading").style.display = "none";
        document.getElementById("results").style.display = "block";

        if (fleetData && fleetData.best_plan) {

            let maxRiskProb = 0;
            let maxRiskLev = "low";
            let worstFactors = [];
            let totalDelayMin = 0;
            let totalDelayUncertainty = 0;

            fleetData.best_plan.legs.forEach(l =>
                l.segments.forEach(s => {
                    if (s.delay_probability > maxRiskProb) {
                        maxRiskProb = s.delay_probability;
                        maxRiskLev = s.risk_level;
                        worstFactors = s.top_factors || [];
                    }
                    // Accumulate total route delay
                    const segT = s.predicted_delay_minutes || 0;
                    const segU = Math.max(1, Math.round(segT * (0.10 + 0.15 * (1 - s.delay_probability))));
                    totalDelayMin += segT;
                    totalDelayUncertainty += segU * segU; // sum of squares for error propagation
                })
            );

            // Propagated uncertainty: sqrt(sum of squares)
            totalDelayUncertainty = Math.round(Math.sqrt(totalDelayUncertainty));
            const totalT = Math.round(totalDelayMin);

            animateGauge(maxRiskProb);

            const verdict = document.getElementById("verdictBadge");
            verdict.textContent =
                maxRiskProb > 0.5
                    ? "Contains High-Risk Segments"
                    : "Route Optimized (Low Risk)";
            verdict.className = `verdict-badge ${maxRiskProb > 0.5 ? "delayed" : "on-time"}`;

            const risk = document.getElementById("riskBadge");
            const c = RISK_COLORS[maxRiskLev] || "#888";
            risk.textContent = `MAX RISK: ${maxRiskLev.replace("_", " ").toUpperCase()}`;
            risk.style.cssText = `background:${c}18;color:${c};border:1px solid ${c}30`;

            // Show total route delay estimate in T ± t format
            const delayEl = document.getElementById("delayEstimate");
            if (totalT < 5) {
                delayEl.innerHTML = `<div class="delay-value">< 5 min</div><div class="delay-label">Minimal Delay Expected</div>`;
            } else if (totalT > 60) {
                const hrs = Math.floor(totalT / 60);
                const mins = totalT % 60;
                const uMins = totalDelayUncertainty;
                delayEl.innerHTML = `<div class="delay-value">${hrs}h ${mins}m <span class="delay-pm">± ${uMins} min</span></div><div class="delay-label">Estimated Route Delay</div>`;
            } else {
                delayEl.innerHTML = `<div class="delay-value">${totalT} <span class="delay-pm">± ${totalDelayUncertainty} min</span></div><div class="delay-label">Estimated Route Delay</div>`;
            }
            delayEl.style.display = "block";

            document.getElementById("contextGrid").innerHTML = `
                <div class="context-item">
                    <div class="label">Total Distance</div>
                    <div class="value">${Math.round(fleetData.best_plan.total_distance_km)} km</div>
                </div>
                <div class="context-item">
                    <div class="label">Total Time</div>
                    <div class="value">~${Math.round(fleetData.best_plan.total_estimated_time_hr)} hr</div>
                </div>
                <div class="context-item">
                    <div class="label">Stops</div>
                    <div class="value">${fleetData.best_plan.legs.length}</div>
                </div>
            `;

            renderShapBars(worstFactors);

            document.querySelector(".prediction-hero").style.display = "flex";
            document.querySelector(".shap-section").style.display =
                worstFactors.length ? "block" : "none";
        }

        renderFleetRoute(fleetData);
        renderMap(fleetData.best_plan, payload); // ✅ uses origin now

    } catch (e) {
        document.getElementById("loading").style.display = "none";
        document.getElementById("placeholder").style.display = "block";
        showError(e.message);
    } finally {
        document.getElementById("runBtn").disabled = false;
    }
}

// ── Render Results ───────────────────────────────────────────────────────
function renderPrediction(pred) {
    animateGauge(pred.delay_probability);
    const verdict = document.getElementById("verdictBadge");
    verdict.textContent = pred.delayed ? "⚠️ Likely Delayed" : "✅ Likely On Time";
    verdict.className = `verdict-badge ${pred.delayed ? "delayed" : "on-time"}`;

    const risk = document.getElementById("riskBadge");
    const c = RISK_COLORS[pred.risk_level] || "#888";
    risk.textContent = pred.risk_level.replace("_", " ").toUpperCase();
    risk.style.cssText = `background:${c}18;color:${c};border:1px solid ${c}30`;

    const ctx = pred.context;
    document.getElementById("contextGrid").innerHTML = `
        <div class="context-item"><div class="label">Distance</div><div class="value">${ctx.distance_km} km</div></div>
        <div class="context-item"><div class="label">Traffic</div><div class="value">${capitalize(ctx.traffic_level)}</div></div>
        <div class="context-item"><div class="label">Weather</div><div class="value">${capitalize(ctx.weather)}</div></div>
        <div class="context-item"><div class="label">Temperature</div><div class="value">${ctx.temperature}°C</div></div>
        <div class="context-item"><div class="label">Est. Wait</div><div class="value">${ctx.waiting_min} min</div></div>
        <div class="context-item"><div class="label">Peak Hour</div><div class="value">${ctx.is_peak_hour ? "Yes ⚠️" : "No ✅"}</div></div>`;
    
    renderShapBars(pred.top_factors);
}

function renderShapBars(factors) {
    const max = Math.max(...factors.map(f => Math.abs(f.shap_value)), 0.01);
    document.getElementById("shapBars").innerHTML = factors.map(f => {
        const pos = f.shap_value > 0;
        const w = Math.max(5, (Math.abs(f.shap_value) / max) * 100);
        const c = pos ? RISK_COLORS.very_high : RISK_COLORS.low;
        return `<div class="shap-row"><div class="shap-label">${f.label}</div><div class="shap-bar-track"><div class="shap-bar-fill ${pos?"positive":"negative"}" style="width:${w}%"></div></div><div class="shap-value" style="color:${c}">${pos?"↑":"↓"} ${f.shap_value>0?"+":""}${f.shap_value.toFixed(3)}</div></div>`;
    }).join("");
}

function animateGauge(prob) {
    const pct = Math.round(prob * 100);
    const color = getRiskColor(prob);
    const totalLength = Math.PI * 80;
    const arc = document.getElementById("gaugeArc");
    arc.style.transition = "stroke-dasharray 1.2s cubic-bezier(0.4,0,0.2,1), stroke 0.5s";
    arc.setAttribute("stroke", color);
    arc.setAttribute("stroke-dasharray", `${totalLength * prob} ${totalLength}`);
    const el = document.getElementById("gaugeValue");
    el.style.color = color;
    let cur = 0; const step = pct / 30;
    const iv = setInterval(() => { cur = Math.min(cur + step, pct); el.textContent = `${Math.round(cur)}%`; if (cur >= pct) clearInterval(iv); }, 30);
}

function renderFleetRoute(fleetData) {
    const plan = fleetData.best_plan;
    // Collect all unique risk segments and their total distances
    document.getElementById("bestRouteCard").innerHTML = `
        <div class="route-path">📍 ${plan.visit_order.map(n=>`<span class="route-node">${n.split(',')[0]}</span>`).join('<span class="route-arrow">→</span>')}</div>
        <div class="route-metrics">
            <div class="route-metric"><div class="metric-value">${plan.total_distance_km} km</div><div class="metric-label">Total Distance</div></div>
            <div class="route-metric"><div class="metric-value">~${plan.total_estimated_time_hr} hr</div><div class="metric-label">Total Est. Time</div></div>
            <div class="route-metric"><div class="metric-value" style="color:var(--accent-cyan)">${plan.total_score.toFixed(3)}</div><div class="metric-label">Total Score</div></div>
            <div class="route-metric"><div class="metric-value">${plan.visit_order.length - 1}</div><div class="metric-label">Total Deliveries</div></div>
        </div>`;
    
    // Render legs
    let segHtml = "";
    plan.legs.forEach((leg, i) => {
        segHtml += `<div style="padding: 12px; margin: 12px 0 6px; background: rgba(0,0,0,0.2); border-radius: 6px; font-weight: bold; border-left: 3px solid var(--accent-cyan);">Leg ${i+1}: ${leg.from_stop.split(',')[0]} → ${leg.to_stop.split(',')[0]} (Score: ${leg.leg_score.toFixed(3)})</div>`;
        leg.segments.forEach((s, j) => {
            const c = RISK_COLORS[s.risk_level]||"#888";
            
            // Error-form: T ± t  where T = predicted delay, t = uncertainty (10-25% of T scaled by confidence)
            const T = Math.round(s.predicted_delay_minutes);
            const t = Math.max(1, Math.round(s.predicted_delay_minutes * (0.10 + 0.15 * (1 - s.delay_probability))));
            
            segHtml += `<div class="segment-card glass-card">
                          <div class="segment-header">
                            <div class="segment-route"><span class="segment-risk-dot" style="background:${c}"></span>${s.from.split(',')[0]} → ${s.to.split(',')[0]}</div>
                            <div class="segment-meta">
                                <span>${s.distance_km} km</span>
                                <span>~${s.estimated_time_hr} hr</span>
                                <span style="color:${c};font-weight:600">${Math.round(s.delay_probability*100)}% risk</span>
                                <span style="font-style:italic">est_delay: ${T} ± ${t} min</span>
                            </div>
                          </div>
                          <div class="segment-header" style="justify-content:flex-end; padding-top:2px;">
                                <span style="font-size:0.7rem; color: #fff5;">Cost Equation: ${s.cost_per_segment.toFixed(3)} | Road: ${capitalize(s.road_type)}</span>
                          </div>
                        </div>`;
        });
    });
    document.getElementById("segmentBreakdown").innerHTML = segHtml;
    
    // Render alternatives globally using a proper HTML <details> Accordion block positioned strictly under the legs
    let altHtml = "";
    let altTitle = "Alternative Paths";
    
    if (plan.legs.length === 1 && plan.legs[0].alternatives && plan.legs[0].alternatives.length > 0) {
        altTitle = "Alternative Paths (Single Leg)";
        plan.legs[0].alternatives.forEach((alt, i) => {
            const altC = RISK_COLORS[alt.mean_delay_risk < 0.25 ? 'low' : alt.mean_delay_risk < 0.5 ? 'medium' : alt.mean_delay_risk < 0.7 ? 'high' : 'very_high'];
            altHtml += `
            <div class="segment-card glass-card" style="border-left: 3px solid #888; margin-bottom: 8px;">
                <div class="segment-header">
                    <div class="segment-route">Alt ${i+1}: ${alt.route.join(' → ')}</div>
                    <div class="segment-meta">
                        <span>${alt.total_distance_km} km</span>
                        <span>~${Math.round(alt.estimated_time_hr*10)/10} hr</span>
                        <span style="color:${altC};font-weight:600">${Math.round(alt.mean_delay_risk*100)}% risk</span>
                        <span>Score: ${alt.route_score}</span>
                    </div>
                </div>
            </div>`;
        });
    } else if (fleetData.alternatives && fleetData.alternatives.length > 0) {
        altTitle = "Alternative Unoptimized Sequences";
        fleetData.alternatives.forEach((alt, i) => {
            altHtml += `
            <div class="segment-card glass-card" style="border-left: 3px solid #e11d48; margin-bottom: 8px;">
                <div class="segment-header">
                    <div class="segment-route" style="color: #cbd5e1">${alt.visit_order.join(' → ')}</div>
                    <div class="segment-meta">
                        <span>${alt.total_distance_km} km</span>
                        <span>~${Math.round(alt.total_estimated_time_hr)} hr</span>
                        <span style="color:#ef4444;font-weight:600">Suboptimal Score: ${alt.total_score.toFixed(3)}</span>
                    </div>
                </div>
            </div>`;
        });
    }

    if (altHtml) {
        // Embed Native Header/Accordion
        document.getElementById("alternatives").innerHTML = `
        <details style="margin-top: 10px;">
            <summary style="cursor: pointer; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 6px; font-weight: bold; border: 1px solid rgba(255,255,255,0.1);">
                ${altTitle} (Click to collapse/expand)
            </summary>
            <div style="padding-top: 15px;">
                ${altHtml}
            </div>
        </details>`;
        document.getElementById("routeComparison").innerHTML = "";
    } else {
        document.getElementById("routeComparison").innerHTML = "";
        document.getElementById("alternatives").innerHTML = "";
    }
}

// ── Leaflet Map ──────────────────────────────────────────────────────────
function renderMap(plan, payload) {
    if (!leafletMap) {
        leafletMap = L.map("routeMap", { zoomControl: true, attributionControl: true }).setView([22.0, 79.0], 5);
        L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { attribution: '&copy; CARTO', maxZoom: 18 }).addTo(leafletMap);
        mapLayerGroup = L.layerGroup().addTo(leafletMap);
    }

    mapLayerGroup.clearLayers();
    const bounds = [];

    // 1. Draw route segments
    plan.legs.forEach(leg => {
        leg.segments.forEach(seg => {
            if (!seg.geometry) return;
            const color = RISK_COLORS[seg.risk_level] || "#3b82f6";
            const layer = L.geoJSON(seg.geometry, {
                style: { color, weight: 4, opacity: 0.85, dashArray: seg.risk_level === "very_high" ? "8 6" : null }
            });
            seg.geometry.coordinates.forEach(c => bounds.push([c[1], c[0]]));
            
            layer.bindPopup(`<b>${seg.from.split(',')[0]} → ${seg.to.split(',')[0]}</b><br>📏 ${seg.distance_km} km <br>⚠️ Delay risk: <b style="color:${color}">${Math.round(seg.delay_probability*100)}%</b>`);
            mapLayerGroup.addLayer(layer);
        });
    });

    // 2. Draw node markers (Origin + Dest stops)
    // Build a map of node names to their GPS to draw markers
    const getLL = (city) => HUB_LIST.find(h => h.city === city) || {lat: 0, lon: 0};
    const sLL = getLL(payload.source);
    const nodesMap = { [payload.source]: {lat: sLL.lat, lon: sLL.lon, type: "Origin"} };
    payload.destinations.forEach((d, i) => { 
        const dLL = getLL(d);
        nodesMap[d] = {lat: dLL.lat, lon: dLL.lon, type: `Stop ${i+1}`} 
    });

    plan.visit_order.forEach((nodeName, i) => {
        const loc = nodesMap[nodeName];
        if (!loc) return;
        
        const isStart = i === 0;
        const isEnd = i === plan.visit_order.length - 1;
        const color = isStart ? "#10b981" : isEnd ? "#ef4444" : "#3b82f6";
        
        const marker = L.circleMarker([loc.lat, loc.lon], { radius: isStart||isEnd ? 10 : 8, fillColor: color, color: "#fff", weight: 2, fillOpacity: 0.9 });
        marker.bindTooltip(`<b>${loc.type}</b><br>${nodeName.split(',')[0]}`, { permanent: true, direction: "top", offset: [0, -12], className: "map-tooltip" });
        mapLayerGroup.addLayer(marker);
        bounds.push([loc.lat, loc.lon]);
    });

    if (bounds.length > 0) leafletMap.fitBounds(bounds, { padding: [50, 50], maxZoom: 10 });
    setTimeout(() => leafletMap.invalidateSize(), 100);
}

// ── Shared Utils ─────────────────────────────────────────────────────────
function getRiskColor(p) { return p < 0.25 ? RISK_COLORS.low : p < 0.5 ? RISK_COLORS.medium : p < 0.7 ? RISK_COLORS.high : RISK_COLORS.very_high; }
function capitalize(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ""; }
function showError(msg) {
    const old = document.querySelector(".error-toast"); if (old) old.remove();
    const t = document.createElement("div"); t.className = "error-toast"; t.textContent = `❌ ${msg}`;
    document.body.appendChild(t); setTimeout(() => t.remove(), 5000);
}

// History loader omitted for brevity - VRP responses don't match the old table schema perfectly.
async function loadHistory() { document.getElementById("historyTab").innerHTML = "<div style='padding:40px;text-align:center;'>History is temporarily disabled while migrating to VRP schemas.</div>"; }
