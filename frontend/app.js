/* ═══════════════════════════════════════════════════════════════
   Smart Logistics Intelligence — Frontend JavaScript v4.1
   Features: animated map, radar chart, Chart.js analytics, progress steps
   ═══════════════════════════════════════════════════════════════ */

const API_BASE = window.location.origin.startsWith("file") ? "http://localhost:8000" : window.location.origin;

let locationState = {
    source: null,
    destinations: [null]
};

let leafletMap = null;
let mapLayerGroup = null;
let mapTileLayer = null;
let radarChartInstance = null;
let donutChartInstance = null;
let lineChartInstance = null;

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

    const themeToggle = document.getElementById("themeToggle");
    if (themeToggle) {
        if (localStorage.getItem("theme") === "light") {
            document.body.classList.add("light-mode");
            themeToggle.textContent = "🌙";
        }
        themeToggle.addEventListener("click", () => {
            document.body.classList.toggle("light-mode");
            const isLight = document.body.classList.contains("light-mode");
            if (isLight) {
                localStorage.setItem("theme", "light");
                themeToggle.textContent = "🌙";
            } else {
                localStorage.setItem("theme", "dark");
                themeToggle.textContent = "☀️";
            }
            if (mapTileLayer) {
                mapTileLayer.setUrl(`https://{s}.basemaps.cartocdn.com/${isLight ? 'light_all' : 'dark_all'}/{z}/{x}/{y}{r}.png`);
            }
        });
    }
});

function initHourSelector() {
    const sel = document.getElementById("depHour");
    sel.innerHTML = "";
    for (let h = 0; h < 24; h++) {
        const opt = document.createElement("option");
        opt.value = h;
        const label = h === 0 ? "12 AM" : h < 12 ? `${h} AM` : h === 12 ? "12 PM" : `${h - 12} PM`;
        opt.textContent = label;
        if (h === new Date().getHours()) opt.selected = true;
        sel.appendChild(opt);
    }
}

function initDateSelector() {
    document.getElementById("depDate").value = new Date().toISOString().split("T")[0];
}

function updateHourBadge() {
    const hour = parseInt(document.getElementById("depHour").value);
    const badge = document.getElementById("hourBadge");
    if ([7, 8, 9, 17, 18, 19].includes(hour)) {
        badge.textContent = "Peak hour — higher delay risk";
        badge.className = "hour-badge peak";
    } else if (hour >= 0 && hour <= 5) {
        badge.textContent = "Night — low traffic";
        badge.className = "hour-badge night";
    } else {
        badge.textContent = "Off-peak — lower delay risk";
        badge.className = "hour-badge";
    }
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
    } catch {
        document.getElementById("statusText").textContent = "API offline";
    }
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
    HUB_LIST.sort((a, b) => a.city.localeCompare(b.city)).forEach(h => {
        const opt = document.createElement("option");
        opt.value = h.city;
        opt.textContent = `${h.city} (${h.type === "warehouse" ? "Warehouse" : "Hub"})`;
        selectEl.appendChild(opt);
    });
}

function renderDestinations() {
    const container = document.getElementById("destinationsContainer");
    container.innerHTML = `
        <div class="form-group dest-group" id="destGroup0">
            <label class="form-label" for="destInput0">Destination 1</label>
            <select id="destInput0" class="form-select dest-select"></select>
        </div>`;
    
    // Always bind and populate the first destination
    const sel0 = document.getElementById("destInput0");
    populateSelect(sel0);
    sel0.value = locationState.destinations[0];
    sel0.addEventListener("change", (e) => locationState.destinations[0] = e.target.value);

    // Render remaining destinations
    for (let i = 1; i < locationState.destinations.length; i++) {
        container.insertAdjacentHTML("beforeend", `
            <div class="form-group dest-group" id="destGroup${i}" style="display:flex; align-items:flex-end; gap:8px;">
                <div style="flex:1;">
                    <label class="form-label" for="destInput${i}">Destination ${i + 1}</label>
                    <select id="destInput${i}" class="form-select dest-select"></select>
                </div>
                <button type="button" onclick="removeStop(${i})" style="height:42px; width:42px; flex-shrink:0; background:rgba(239,68,68,0.1); color:#ef4444; border:1px solid rgba(239,68,68,0.2); border-radius:8px; display:flex; align-items:center; justify-content:center; cursor:pointer;" title="Remove this stop">-</button>
            </div>
        `);
        const sel = document.getElementById(`destInput${i}`);
        populateSelect(sel);
        sel.value = locationState.destinations[i];
        sel.addEventListener("change", (e) => locationState.destinations[i] = e.target.value);
    }
}

function addDestinationStop() {
    if (locationState.destinations.length >= 6) { showError("Maximum 6 stops supported."); return; }
    // Assign default hub for the new stop based on length, or an empty string
    locationState.destinations.push(HUB_LIST[locationState.destinations.length]?.city || "");
    renderDestinations();
}

function removeStop(index) {
    if (index === 0) return; // Never remove destination 1
    locationState.destinations.splice(index, 1);
    renderDestinations();
}

// ── Tab Management ───────────────────────────────────────────────────────
function switchTab(tab) {
    document.getElementById("analysisTab").style.display = tab === "analysis" ? "" : "none";
    document.getElementById("historyTab").style.display = tab === "history" ? "" : "none";
    document.getElementById("tabAnalysis").classList.toggle("active", tab === "analysis");
    document.getElementById("tabHistory").classList.toggle("active", tab === "history");
    if (tab === "history") loadAnalytics();
}

function loadExample(key) {
    const ex = EXAMPLES[key]; if (!ex) return;

    locationState.source = ex.source;
    document.getElementById("sourceInput").value = ex.source;

    locationState.destinations = [...ex.dests];
    renderDestinations();

    document.getElementById("depHour").value = ex.hour;
    document.getElementById("vehicleType").value = ex.vehicle;
    document.getElementById("cargoType").value = ex.cargo;
    document.getElementById("priority").value = ex.priority;
    document.getElementById("depDate").value = `2024-${String(ex.month).padStart(2, "0")}-${String(ex.day).padStart(2, "0")}`;
    updateHourBadge();
}

// ── Progress Steps ───────────────────────────────────────────────────────
let _progressTimer = null;

function startProgressSteps() {
    const steps = [
        { id: "pstep1", icon: "🔧", label: "Building feature vector" },
        { id: "pstep2", icon: "📡", label: "Scoring candidate routes via OSRM" },
        { id: "pstep3", icon: "🧮", label: "Running VRP optimizer" },
        { id: "pstep4", icon: "🗺️", label: "Rendering results" },
    ];
    let current = 0;

    // Reset all steps
    steps.forEach(s => {
        const el = document.getElementById(s.id);
        el.className = "progress-step";
        el.querySelector(".pstep-icon").textContent = "⏳";
        el.querySelector(".pstep-label").textContent = s.label;
    });

    function advance() {
        if (current > 0) {
            const prev = steps[current - 1];
            const el = document.getElementById(prev.id);
            el.className = "progress-step done";
            el.querySelector(".pstep-icon").textContent = "✅";
        }
        if (current < steps.length) {
            const cur = steps[current];
            const el = document.getElementById(cur.id);
            el.className = "progress-step active";
            el.querySelector(".pstep-icon").textContent = cur.icon;
            document.getElementById("loadingStepText").textContent = cur.label + "...";
            current++;
            // Step durations: 1.2s, 3s, 2s, 0.5s
            const delays = [1200, 3000, 2000, 500];
            _progressTimer = setTimeout(advance, delays[current - 1] || 1000);
        }
    }
    advance();
}

function stopProgressSteps() {
    if (_progressTimer) clearTimeout(_progressTimer);
    // Mark remaining steps as done
    for (let i = 1; i <= 4; i++) {
        const el = document.getElementById(`pstep${i}`);
        if (!el.classList.contains("done")) {
            el.className = "progress-step done";
            el.querySelector(".pstep-icon").textContent = "✅";
        }
    }
}

// ── API Calling ──────────────────────────────────────────────────────────
async function runAnalysis() {
    if (!locationState.source) { showError("Please select an Origin Location."); return; }
    const validDests = locationState.destinations.filter(d => d !== null);
    if (!validDests.length) { showError("Please select at least one Destination."); return; }

    const payload = {
        source: locationState.source,
        destinations: validDests,
        departure_time: `${document.getElementById("depDate").value}T${String(document.getElementById("depHour").value).padStart(2, "0")}:00:00`,
        vehicle_type: document.getElementById("vehicleType").value,
        cargo_type: document.getElementById("cargoType").value,
        priority_level: parseInt(document.getElementById("priority").value),
    };

    document.getElementById("placeholder").style.display = "none";
    document.getElementById("results").style.display = "none";
    document.getElementById("loading").style.display = "block";
    document.getElementById("runBtn").disabled = true;
    startProgressSteps();

    try {
        const res = await fetch(`${API_BASE}/predict-route`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            const errMsg = Array.isArray(err.detail) ? err.detail.map(d => d.msg).join(", ") : (err.detail || "Route prediction failed");
            throw new Error(errMsg);
        }

        const fleetData = await res.json();
        console.log("API RESPONSE:", fleetData);

        stopProgressSteps();
        await new Promise(r => setTimeout(r, 400)); // brief pause so user sees completion

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
                    const segT = s.predicted_delay_minutes || 0;
                    const segU = Math.max(1, Math.round(segT * (0.10 + 0.15 * (1 - s.delay_probability))));
                    totalDelayMin += segT;
                    totalDelayUncertainty += segU * segU;
                })
            );

            totalDelayUncertainty = Math.round(Math.sqrt(totalDelayUncertainty));
            const totalT = Math.round(totalDelayMin);

            animateGauge(maxRiskProb);

            const verdict = document.getElementById("verdictBadge");
            verdict.textContent = maxRiskProb > 0.5 ? "Contains High-Risk Segments" : "Route Optimized (Low Risk)";
            verdict.className = `verdict-badge ${maxRiskProb > 0.5 ? "delayed" : "on-time"}`;

            const risk = document.getElementById("riskBadge");
            const c = RISK_COLORS[maxRiskLev] || "#888";
            risk.textContent = `MAX RISK: ${maxRiskLev.replace("_", " ").toUpperCase()}`;
            risk.style.cssText = `background:${c}18;color:${c};border:1px solid ${c}30`;

            const delayEl = document.getElementById("delayEstimate");
            if (totalT < 5) {
                delayEl.innerHTML = `<div class="delay-value">< 5 min</div><div class="delay-label">Minimal Delay Expected</div>`;
            } else if (totalT > 60) {
                const hrs = Math.floor(totalT / 60);
                const mins = totalT % 60;
                delayEl.innerHTML = `<div class="delay-value">${hrs}h ${mins}m <span class="delay-pm">± ${totalDelayUncertainty} min</span></div><div class="delay-label">Estimated Route Delay</div>`;
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
                    <div class="value">~${Number(fleetData.best_plan.total_estimated_time_hr).toFixed(2)} hr</div>
                </div>
                <div class="context-item">
                    <div class="label">Stops</div>
                    <div class="value">${fleetData.best_plan.legs.length}</div>
                </div>`;

            renderShapBars(worstFactors);
            document.querySelector(".prediction-hero").style.display = "flex";
            document.querySelector(".shap-section").style.display = worstFactors.length ? "block" : "none";
        }

        renderFleetRoute(fleetData);
        renderRadarChart(fleetData);
        renderMapAnimated(fleetData.best_plan, payload);
        
        setTimeout(() => loadAnalytics(), 500);

    } catch (e) {
        stopProgressSteps();
        document.getElementById("loading").style.display = "none";
        document.getElementById("placeholder").style.display = "block";
        showError(e.message);
    } finally {
        document.getElementById("runBtn").disabled = false;
    }
}

// ── Render Results ───────────────────────────────────────────────────────
function renderShapBars(factors) {
    const max = Math.max(...factors.map(f => Math.abs(f.shap_value)), 0.01);
    document.getElementById("shapBars").innerHTML = factors.map(f => {
        const pos = f.shap_value > 0;
        const w = Math.max(5, (Math.abs(f.shap_value) / max) * 100);
        const c = pos ? RISK_COLORS.very_high : RISK_COLORS.low;
        return `<div class="shap-row"><div class="shap-label">${f.label}</div><div class="shap-bar-track"><div class="shap-bar-fill ${pos ? "positive" : "negative"}" style="width:${w}%"></div></div><div class="shap-value" style="color:${c}">${pos ? "↑" : "↓"} ${f.shap_value > 0 ? "+" : ""}${f.shap_value.toFixed(3)}</div></div>`;
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
    document.getElementById("bestRouteCard").innerHTML = `
        <div class="route-path">📍 ${plan.visit_order.map(n => `<span class="route-node">${n.split(",")[0]}</span>`).join('<span class="route-arrow">→</span>')}</div>
        <div class="route-metrics">
            <div class="route-metric"><div class="metric-value">${plan.total_distance_km} km</div><div class="metric-label">Total Distance</div></div>
            <div class="route-metric"><div class="metric-value">~${Number(plan.total_estimated_time_hr).toFixed(2)} hr</div><div class="metric-label">Total Est. Time</div></div>
            <div class="route-metric"><div class="metric-value" style="color:var(--accent-cyan)">${plan.total_score.toFixed(3)}</div><div class="metric-label">Total Score</div></div>
            <div class="route-metric"><div class="metric-value">${plan.visit_order.length - 1}</div><div class="metric-label">Total Deliveries</div></div>
        </div>`;

    let segHtml = "";
    plan.legs.forEach((leg, i) => {
        segHtml += `<div style="padding:12px;margin:12px 0 6px;background:rgba(0,0,0,0.2);border-radius:6px;font-weight:bold;border-left:3px solid var(--accent-cyan);">Leg ${i + 1}: ${leg.from_stop.split(",")[0]} → ${leg.to_stop.split(",")[0]} (Score: ${leg.leg_score.toFixed(3)})</div>`;
        leg.segments.forEach(s => {
            const c = RISK_COLORS[s.risk_level] || "#888";
            const T = Math.round(s.predicted_delay_minutes);
            const t = Math.max(1, Math.round(s.predicted_delay_minutes * (0.10 + 0.15 * (1 - s.delay_probability))));
            segHtml += `<div class="segment-card glass-card">
                <div class="segment-header">
                    <div class="segment-route"><span class="segment-risk-dot" style="background:${c}"></span>${s.from.split(",")[0]} → ${s.to.split(",")[0]}</div>
                    <div class="segment-meta">
                        <span>${s.distance_km} km</span>
                        <span>~${Number(s.estimated_time_hr).toFixed(2)} hr</span>
                        <span style="color:${c};font-weight:600">${Math.round(s.delay_probability * 100)}% risk</span>
                        <span style="font-style:italic">est_delay: ${T} ± ${t} min</span>
                    </div>
                </div>
                <div class="segment-header" style="justify-content:flex-end;padding-top:2px;">
                    <span style="font-size:0.7rem;color:#fff5">Cost: ${s.cost_per_segment.toFixed(3)} | Road: ${capitalize(s.road_type)}</span>
                </div>
            </div>`;
        });
    });
    document.getElementById("segmentBreakdown").innerHTML = segHtml;

    // Alternatives accordion
    let altHtml = "";
    let altTitle = "Alternative Paths";

    if (plan.legs.length === 1 && plan.legs[0].alternatives && plan.legs[0].alternatives.length > 0) {
        altTitle = "Alternative Paths (Single Leg)";
        plan.legs[0].alternatives.forEach((alt, i) => {
            const altC = RISK_COLORS[alt.mean_delay_risk < 0.25 ? "low" : alt.mean_delay_risk < 0.5 ? "medium" : alt.mean_delay_risk < 0.7 ? "high" : "very_high"];
            altHtml += `<div class="segment-card glass-card" style="border-left:3px solid #888;margin-bottom:8px;">
                <div class="segment-header">
                    <div class="segment-route">Alt ${i + 1}: ${alt.route.join(" → ")}</div>
                    <div class="segment-meta">
                        <span>${alt.total_distance_km} km</span>
                        <span>~${Number(alt.estimated_time_hr).toFixed(2)} hr</span>
                        <span style="color:${altC};font-weight:600">${Math.round(alt.mean_delay_risk * 100)}% risk</span>
                        <span>Score: ${alt.route_score}</span>
                    </div>
                </div>
            </div>`;
        });
    } else if (fleetData.alternatives && fleetData.alternatives.length > 0) {
        altTitle = "Alternative Unoptimized Sequences";
        fleetData.alternatives.forEach(alt => {
            altHtml += `<div class="segment-card glass-card" style="border-left:3px solid #e11d48;margin-bottom:8px;">
                <div class="segment-header">
                    <div class="segment-route" style="color:#cbd5e1">${alt.visit_order.join(" → ")}</div>
                    <div class="segment-meta">
                        <span>${alt.total_distance_km} km</span>
                        <span>~${Number(alt.total_estimated_time_hr).toFixed(2)} hr</span>
                        <span style="color:#ef4444;font-weight:600">Suboptimal Score: ${alt.total_score.toFixed(3)}</span>
                    </div>
                </div>
            </div>`;
        });
    }

    if (altHtml) {
        document.getElementById("alternatives").innerHTML = `
        <details style="margin-top:10px;">
            <summary style="cursor:pointer;padding:12px;background:rgba(255,255,255,0.05);border-radius:6px;font-weight:bold;border:1px solid rgba(255,255,255,0.1);">
                ${altTitle} (Click to expand)
            </summary>
            <div style="padding-top:15px;">${altHtml}</div>
        </details>`;
        document.getElementById("routeComparison").innerHTML = "";
    } else {
        document.getElementById("routeComparison").innerHTML = "";
        document.getElementById("alternatives").innerHTML = "";
    }
}

// ── Radar Chart — Route Comparison ───────────────────────────────────────
function renderRadarChart(fleetData) {
    const radarSection = document.getElementById("radarSection");

    // Only show for single-leg routes with alternatives
    const plan = fleetData.best_plan;
    if (!plan || plan.legs.length !== 1) {
        radarSection.style.display = "none";
        return;
    }

    const leg = plan.legs[0];
    const alts = leg.alternatives || [];
    if (alts.length === 0) {
        radarSection.style.display = "none";
        return;
    }

    radarSection.style.display = "block";

    // Build datasets: best route + up to 2 alternatives
    const allRoutes = [
        { label: "Best Route", data: leg, color: "#10b981", score: leg.leg_score },
        ...alts.slice(0, 2).map((alt, i) => ({
            label: `Alt ${i + 1}`,
            data: alt,
            color: i === 0 ? "#3b82f6" : "#8b5cf6",
            score: alt.route_score
        }))
    ];

    // 4 radar axes — normalize each to 0-100 (lower = better, so invert)
    const maxDist = Math.max(...allRoutes.map(r => r.data.total_distance_km || 0)) || 1;
    const maxTime = Math.max(...allRoutes.map(r => r.data.estimated_time_hr || 0)) || 1;
    const maxRisk = 1; // probability is already 0-1
    const maxScore = Math.max(...allRoutes.map(r => r.score || 0)) || 1;

    function normalize(val, max) { return Math.round((1 - val / max) * 100); }

    const datasets = allRoutes.map(r => ({
        label: r.label,
        data: [
            normalize(r.data.total_distance_km || 0, maxDist),
            normalize(r.data.estimated_time_hr || 0, maxTime),
            normalize(r.data.mean_delay_risk || 0, maxRisk),
            normalize(r.score || 0, maxScore),
        ],
        backgroundColor: r.color + "22",
        borderColor: r.color,
        pointBackgroundColor: r.color,
        borderWidth: 2,
        pointRadius: 4,
    }));

    if (radarChartInstance) radarChartInstance.destroy();

    const ctx = document.getElementById("radarChart").getContext("2d");
    radarChartInstance = new Chart(ctx, {
        type: "radar",
        data: {
            labels: ["Distance Score", "Time Score", "Delay Safety", "Overall Score"],
            datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${ctx.raw}/100`
                    }
                }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: "rgba(255,255,255,0.06)" },
                    angleLines: { color: "rgba(255,255,255,0.08)" },
                    pointLabels: { color: "#94a3b8", font: { family: "Inter", size: 11 } },
                    ticks: { color: "#64748b", backdropColor: "transparent", stepSize: 25 }
                }
            }
        }
    });
}

// ── Animated Map ──────────────────────────────────────────────────────────
function renderMapAnimated(plan, payload) {
    if (!leafletMap) {
        leafletMap = L.map("routeMap", { zoomControl: true, attributionControl: true }).setView([22.0, 79.0], 5);
        const isLight = document.body.classList.contains("light-mode");
        mapTileLayer = L.tileLayer(`https://{s}.basemaps.cartocdn.com/${isLight ? 'light_all' : 'dark_all'}/{z}/{x}/{y}{r}.png`, {
            attribution: "© CARTO", maxZoom: 18
        }).addTo(leafletMap);
        mapLayerGroup = L.layerGroup().addTo(leafletMap);
    }

    mapLayerGroup.clearLayers();
    const bounds = [];
    const getLL = (city) => HUB_LIST.find(h => h.city === city) || { lat: 0, lon: 0 };

    // Collect all segments in order
    const allSegments = [];
    plan.legs.forEach(leg => leg.segments.forEach(seg => allSegments.push(seg)));

    // Collect bounds immediately for fitBounds
    allSegments.forEach(seg => {
        if (seg.geometry) {
            seg.geometry.coordinates.forEach(c => bounds.push([c[1], c[0]]));
        } else {
            const f = getLL(seg.from.split(",")[0]);
            const t = getLL(seg.to.split(",")[0]);
            if (f.lat) bounds.push([f.lat, f.lon]);
            if (t.lat) bounds.push([t.lat, t.lon]);
        }
    });

    // Add node markers first (they appear immediately)
    const sLL = getLL(payload.source);
    const nodesMap = { [payload.source]: { lat: sLL.lat, lon: sLL.lon, type: "Origin" } };
    payload.destinations.forEach((d, i) => {
        const dLL = getLL(d);
        nodesMap[d] = { lat: dLL.lat, lon: dLL.lon, type: `Stop ${i + 1}` };
    });

    plan.visit_order.forEach((nodeName, i) => {
        const loc = nodesMap[nodeName];
        if (!loc || !loc.lat) return;
        const isStart = i === 0;
        const isEnd = i === plan.visit_order.length - 1;
        const color = isStart ? "#10b981" : isEnd ? "#ef4444" : "#3b82f6";
        const marker = L.circleMarker([loc.lat, loc.lon], {
            radius: isStart || isEnd ? 10 : 8,
            fillColor: color, color: "#fff", weight: 2, fillOpacity: 0.9
        });
        marker.bindTooltip(`<b>${loc.type}</b><br>${nodeName.split(",")[0]}`, {
            permanent: true, direction: "top", offset: [0, -12], className: "map-tooltip"
        });
        mapLayerGroup.addLayer(marker);
    });

    if (bounds.length > 0) leafletMap.fitBounds(bounds, { padding: [50, 50], maxZoom: 10 });
    setTimeout(() => leafletMap.invalidateSize(), 100);

    // Animate segments one-by-one with 350ms delay each
    allSegments.forEach((seg, idx) => {
        setTimeout(() => {
            const color = RISK_COLORS[seg.risk_level] || "#3b82f6";
            if (seg.geometry) {
                const layer = L.geoJSON(seg.geometry, {
                    style: { color, weight: 4, opacity: 0, dashArray: seg.risk_level === "very_high" ? "8 6" : null }
                });
                layer.bindPopup(
                    `<b>${seg.from.split(",")[0]} → ${seg.to.split(",")[0]}</b><br>` +
                    `📏 ${seg.distance_km} km<br>` +
                    `⚠️ Delay risk: <b style="color:${color}">${Math.round(seg.delay_probability * 100)}%</b>`
                );
                mapLayerGroup.addLayer(layer);
                // Fade in opacity
                let op = 0;
                const fade = setInterval(() => {
                    op = Math.min(op + 0.1, 0.85);
                    layer.setStyle({ opacity: op });
                    if (op >= 0.85) clearInterval(fade);
                }, 30);
            } else {
                const fromLL = getLL(seg.from.split(",")[0]);
                const toLL = getLL(seg.to.split(",")[0]);
                if (fromLL.lat && toLL.lat) {
                    const line = L.polyline(
                        [[fromLL.lat, fromLL.lon], [toLL.lat, toLL.lon]],
                        { color, weight: 3, opacity: 0, dashArray: "6 4" }
                    );
                    line.bindPopup(
                        `<b>${seg.from.split(",")[0]} → ${seg.to.split(",")[0]}</b><br>` +
                        `📏 ${seg.distance_km} km<br>` +
                        `⚠️ Delay risk: <b style="color:${color}">${Math.round(seg.delay_probability * 100)}%</b><br>` +
                        `<i>(Straight line — road geometry unavailable)</i>`
                    );
                    mapLayerGroup.addLayer(line);
                    let op = 0;
                    const fade = setInterval(() => {
                        op = Math.min(op + 0.1, 0.7);
                        line.setStyle({ opacity: op });
                        if (op >= 0.7) clearInterval(fade);
                    }, 30);
                }
            }
        }, idx * 350);
    });
}

// ── Analytics / History ──────────────────────────────────────────────────
async function resetAnalytics() {
    if (!confirm("Are you sure you want to permanently delete all prediction and route history?")) return;
    try {
        await fetch(`${API_BASE}/history`, { method: "DELETE" });
        await loadAnalytics(); // Refresh the tab counters to zero
        setTimeout(() => alert("Analytics database successfully reset!"), 100);
    } catch (e) {
        alert("Failed to reset history: " + e.message);
    }
}

async function loadAnalytics() {
    try {
        const [analyticsRes, historyRes] = await Promise.all([
            fetch(`${API_BASE}/analytics`),
            fetch(`${API_BASE}/history?limit=20`)
        ]);
        const analytics = await analyticsRes.json();
        const history = await historyRes.json();

        if (!analytics || (analytics.total_predictions === 0 && analytics.total_routes === 0)) {
            document.getElementById("analyticsContentWrapper").style.display = "none";
            document.getElementById("analyticsEmptyState").style.display = "block";
            return;
        }

        document.getElementById("analyticsContentWrapper").style.display = "block";
        document.getElementById("analyticsEmptyState").style.display = "none";

        // Summary cards
        document.getElementById("totalPredictions").textContent = analytics.total_predictions ?? "—";
        document.getElementById("totalRoutes").textContent = analytics.total_routes ?? "—";
        document.getElementById("avgDelay").textContent =
            analytics.avg_delay_probability != null
                ? `${Math.round(analytics.avg_delay_probability * 100)}%`
                : "—";
        document.getElementById("delayRate").textContent =
            analytics.delay_rate != null
                ? `${Math.round(analytics.delay_rate * 100)}%`
                : "—";

        // Risk donut chart
        renderRiskDonut(analytics.risk_distribution || {});

        // Hourly line chart
        renderHourlyLine(analytics.hourly_delay_trend || []);

        // Risky routes table
        renderRiskyRoutes(analytics.top_risky_routes || []);

        // Recent predictions table
        renderHistoryTable(history.predictions || []);

    } catch (e) {
        document.getElementById("historyTab").querySelector(".history-panel").insertAdjacentHTML(
            "beforeend",
            `<div class="empty-state">⚠️ Could not load analytics: ${e.message}</div>`
        );
    }
}

function renderRiskDonut(dist) {
    const labels = ["Low", "Medium", "High", "Very High"];
    const keys = ["low", "medium", "high", "very_high"];
    const data = keys.map(k => dist[k] || 0);
    const colors = [RISK_COLORS.low, RISK_COLORS.medium, RISK_COLORS.high, RISK_COLORS.very_high];

    if (donutChartInstance) donutChartInstance.destroy();

    const ctx = document.getElementById("riskDonutChart").getContext("2d");
    donutChartInstance = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: colors.map(c => c + "cc"),
                borderColor: colors,
                borderWidth: 2,
                hoverOffset: 6,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "65%",
            plugins: {
                legend: {
                    position: "bottom",
                    labels: { color: "#94a3b8", font: { family: "Inter", size: 11 }, padding: 14 }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ${ctx.label}: ${ctx.raw} predictions`
                    }
                }
            }
        }
    });
}

function renderHourlyLine(trend) {
    // trend: array of {hour, avg_delay_probability}
    const labels = Array.from({ length: 24 }, (_, i) => i % 3 === 0 ? `${i}h` : "");
    const fullData = Array(24).fill(null);
    trend.forEach(t => { if (t.hour >= 0 && t.hour < 24) fullData[t.hour] = t.avg_risk; });

    if (lineChartInstance) lineChartInstance.destroy();

    const ctx = document.getElementById("hourlyLineChart").getContext("2d");
    lineChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [{
                label: "Avg Delay Probability",
                data: fullData,
                borderColor: "#3b82f6",
                backgroundColor: "rgba(59,130,246,0.08)",
                borderWidth: 2,
                pointRadius: 3,
                pointBackgroundColor: "#3b82f6",
                tension: 0.4,
                fill: true,
                spanGaps: true,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ${(ctx.raw * 100).toFixed(1)}% delay probability`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: "rgba(255,255,255,0.04)" },
                    ticks: { color: "#64748b", font: { family: "Inter", size: 10 } }
                },
                y: {
                    beginAtZero: true,
                    max: 1,
                    grid: { color: "rgba(255,255,255,0.04)" },
                    ticks: {
                        color: "#64748b",
                        font: { family: "Inter", size: 10 },
                        callback: v => `${Math.round(v * 100)}%`
                    }
                }
            }
        }
    });
}

function renderRiskyRoutes(routes) {
    if (!routes.length) {
        document.getElementById("riskyRoutesTable").innerHTML = `<div class="empty-state">No route data yet. Run some analyses to populate this.</div>`;
        return;
    }
    const rows = routes.map(r => {
        const c = getRiskColor(r.avg_risk || 0);
        return `<tr>
            <td>${r.source || "—"}</td>
            <td>${r.destination || "—"}</td>
            <td><span class="risk-pill" style="background:${c}20;color:${c}">${Math.round((r.avg_risk || 0) * 100)}%</span></td>
            <td>${r.count || 0}</td>
        </tr>`;
    }).join("");
    document.getElementById("riskyRoutesTable").innerHTML = `
        <table class="data-table">
            <thead><tr><th>From</th><th>To</th><th>Avg Risk</th><th>Count</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
}

function renderHistoryTable(preds) {
    if (!preds.length) {
        document.getElementById("historyTable").innerHTML = `<div class="empty-state">No prediction history yet.</div>`;
        return;
    }
    const rows = preds.slice(0, 15).map(p => {
        const c = getRiskColor(p.delay_probability || 0);
        const ts = p.timestamp ? new Date(p.timestamp).toLocaleString() : "—";
        return `<tr>
            <td>${p.source || "—"}</td>
            <td>${p.destination || "—"}</td>
            <td><span class="risk-pill" style="background:${c}20;color:${c}">${Math.round((p.delay_probability || 0) * 100)}%</span></td>
            <td>${p.risk_level || "—"}</td>
            <td style="font-size:0.75rem;color:var(--text-muted)">${ts}</td>
        </tr>`;
    }).join("");
    document.getElementById("historyTable").innerHTML = `
        <table class="data-table">
            <thead><tr><th>From</th><th>To</th><th>Delay Prob</th><th>Risk</th><th>Time</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
}

// ── Shared Utils ─────────────────────────────────────────────────────────
function getRiskColor(p) { return p < 0.25 ? RISK_COLORS.low : p < 0.5 ? RISK_COLORS.medium : p < 0.7 ? RISK_COLORS.high : RISK_COLORS.very_high; }
function capitalize(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ""; }
function showError(msg) {
    const old = document.querySelector(".error-toast"); if (old) old.remove();
    const t = document.createElement("div"); t.className = "error-toast"; t.textContent = `❌ ${msg}`;
    document.body.appendChild(t); setTimeout(() => t.remove(), 5000);
}
