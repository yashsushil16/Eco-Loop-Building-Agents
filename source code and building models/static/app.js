let chartInstance = null;
let activeTab = 'temp';
let currentSeason = 'winter';

document.addEventListener('DOMContentLoaded', () => {
    const seasonSelect = document.getElementById('seasonSelect');
    const iterSlider = document.getElementById('iterSlider');
    const iterVal = document.getElementById('iterVal');
    const btnRun = document.getElementById('btnRun');
    const tabBtns = document.querySelectorAll('.tab-btn');

    // Sync slider value
    iterSlider.addEventListener('input', (e) => {
        iterVal.textContent = e.target.value;
    });

    // Season switch
    seasonSelect.addEventListener('change', (e) => {
        currentSeason = e.target.value;
        fetchTimeseries(currentSeason);
        fetchStatus();
    });

    // Tab buttons
    tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            tabBtns.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            activeTab = e.target.dataset.tab;
            fetchTimeseries(currentSeason);
        });
    });

    // Run Optimization button
    btnRun.addEventListener('click', () => {
        triggerOptimization(seasonSelect.value, parseInt(iterSlider.value));
    });

    // Initial load
    fetchStatus();
    fetchTimeseries(currentSeason);

    // Poll status every 1.5 seconds
    setInterval(fetchStatus, 1500);
});

async function triggerOptimization(season, iterations) {
    try {
        const btnRun = document.getElementById('btnRun');
        btnRun.disabled = true;
        btnRun.innerHTML = '<span>Optimization Running...</span>';

        const res = await fetch('/api/optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ season, iterations })
        });
        const data = await res.json();
        console.log('Optimization triggered:', data);
    } catch (err) {
        console.error('Error triggering optimization:', err);
    }
}

async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        // Update status indicators
        const statusIndicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        const topNavStatus = document.getElementById('topNavStatus');
        const btnRun = document.getElementById('btnRun');
        
        if (data.running) {
            statusIndicator.className = 'status-badge running';
            statusText.textContent = `Status: ${data.status_text}`;
            if (topNavStatus) topNavStatus.textContent = data.status_text;
            btnRun.disabled = true;
            btnRun.innerHTML = `<span>Optimization Running...</span>`;
        } else {
            statusIndicator.className = 'status-badge idle';
            statusText.textContent = `Status: ${data.status_text}`;
            if (topNavStatus) topNavStatus.textContent = 'System Ready';
            btnRun.disabled = false;
            btnRun.innerHTML = `
                <span>Initialize Optimization Loop</span>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
            `;
        }

        // Update Terminal Logs (Chronological Stream with Auto-Scroll)
        const terminalLog = document.getElementById('terminalLog');
        if (data.logs && data.logs.length > 0) {
            const wasAtBottom = terminalLog.scrollTop + terminalLog.clientHeight >= terminalLog.scrollHeight - 40;
            terminalLog.innerHTML = data.logs.map(line => {
                const parts = line.split(']');
                const time = (parts[0] + ']').trim();
                const text = parts.slice(1).join(']').trim();
                return `<div class="terminal-line"><span class="terminal-time">${time}</span><span class="terminal-text">${text}</span></div>`;
            }).join('');
            if (wasAtBottom || data.running) {
                terminalLog.scrollTop = terminalLog.scrollHeight;
            }
        }

        // Update KPI Cards
        const base = data.baseline_metrics;
        const opt = data.optimal_metrics || (data.history && data.history.length > 0 ? data.history[data.history.length - 1] : null);

        if (base) {
            // Energy
            const kpiEnergy = document.getElementById('kpiEnergy');
            const kpiEnergyDelta = document.getElementById('kpiEnergyDelta');
            if (opt) {
                kpiEnergy.textContent = `${opt.total_energy_kwh.toFixed(1)} kWh`;
                kpiEnergyDelta.textContent = `-${opt.savings_pct.toFixed(1)}% vs Baseline (${base.total_energy_kwh.toFixed(1)} kWh)`;
            } else {
                kpiEnergy.textContent = `${base.total_energy_kwh.toFixed(1)} kWh`;
                kpiEnergyDelta.textContent = `Baseline Active`;
            }

            // Comfort Violations
            const kpiComfort = document.getElementById('kpiComfort');
            const kpiComfortDelta = document.getElementById('kpiComfortDelta');
            if (opt) {
                const deltaViolations = base.comfort_violations_hours - opt.comfort_violations_hours;
                const sign = deltaViolations >= 0 ? '-' : '+';
                kpiComfort.textContent = `${opt.comfort_violations_hours} Hours`;
                kpiComfortDelta.textContent = `${sign}${Math.abs(deltaViolations)} Hours vs Baseline (${base.comfort_violations_hours} hrs)`;
            } else {
                kpiComfort.textContent = `${base.comfort_violations_hours} Hours`;
                kpiComfortDelta.textContent = `Baseline Active`;
            }

            // Carbon Footprint
            const kpiCo2 = document.getElementById('kpiCo2');
            const kpiCo2Delta = document.getElementById('kpiCo2Delta');
            if (opt) {
                const co2Pct = ((1.0 - (opt.co2_kg / base.co2_kg)) * 100.0).toFixed(1);
                kpiCo2.textContent = `${opt.co2_kg.toFixed(1)} kg`;
                kpiCo2Delta.textContent = `-${co2Pct}% vs Baseline (${base.co2_kg.toFixed(1)} kg)`;
            } else {
                kpiCo2.textContent = `${base.co2_kg.toFixed(1)} kg`;
                kpiCo2Delta.textContent = `Baseline Active`;
            }

            // Cost Savings
            const kpiCost = document.getElementById('kpiCost');
            if (opt) {
                const costSaved = (base.total_energy_kwh - opt.total_energy_kwh) * 0.15;
                kpiCost.textContent = `$${costSaved.toFixed(2)}`;
            } else {
                kpiCost.textContent = `$0.00`;
            }
        }

        // Setpoints Panel
        const setpointsPanel = document.getElementById('setpointsPanel');
        if (opt) {
            setpointsPanel.style.display = 'block';
            document.getElementById('spCoolOcc').innerHTML = `24.0°C → <span class="badge-mint">${opt.cool_occ}°C</span>`;
            document.getElementById('spCoolUnocc').innerHTML = `26.7°C → <span class="badge-mint">${opt.cool_unocc}°C</span>`;
            document.getElementById('spHeatOcc').innerHTML = `21.0°C → <span class="badge-mint">${opt.heat_occ}°C</span>`;
            document.getElementById('spHeatUnocc').innerHTML = `15.6°C → <span class="badge-mint">${opt.heat_unocc}°C</span>`;
        }

        // Reasoning Feed
        const reasoningFeed = document.getElementById('reasoningFeed');
        if (data.history && data.history.length > 0) {
            reasoningFeed.innerHTML = data.history.map((h, i) => `
                <div class="reasoning-item">
                    <h4>Trial ${i + 1} (${h.run_id})</h4>
                    <p><strong>Setpoints:</strong> Cool Occ: ${h.cool_occ}°C, Heat Occ: ${h.heat_occ}°C. Occupancy: ${h.occ_start}:00-${h.occ_end}:00</p>
                    <p style="margin-top: 6px;">${h.reasoning}</p>
                </div>
            `).join('');
        }

    } catch (err) {
        console.error('Error fetching status:', err);
    }
}

async function fetchTimeseries(season) {
    try {
        const res = await fetch(`/api/timeseries/${season}`);
        const data = await res.json();
        
        if (!data.baseline) {
            return;
        }

        const labels = data.baseline.timestamps.map((t, i) => (i % 24 === 0 ? t : ''));
        const ctx = document.getElementById('mainChart').getContext('2d');

        if (chartInstance) {
            chartInstance.destroy();
        }

        // Apple Blue Light Gradient fill
        const gradientBlue = ctx.createLinearGradient(0, 0, 0, 300);
        gradientBlue.addColorStop(0, 'rgba(0, 113, 227, 0.15)');
        gradientBlue.addColorStop(1, 'rgba(0, 113, 227, 0.0)');

        let datasets = [];

        if (activeTab === 'temp') {
            datasets.push({
                label: 'Baseline Core Temp (°C)',
                data: data.baseline.core_temp,
                borderColor: '#86868b',
                borderDash: [4, 4],
                borderWidth: 1.5,
                fill: false,
                pointRadius: 0
            });
            if (data.optimal) {
                datasets.push({
                    label: 'AI-Optimized Core Temp (°C)',
                    data: data.optimal.core_temp,
                    borderColor: '#0071e3',
                    backgroundColor: gradientBlue,
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0
                });
            }
            datasets.push({
                label: 'Outdoor Weather Temp (°C)',
                data: data.baseline.outdoor_temp,
                borderColor: '#d97706',
                borderDash: [2, 2],
                borderWidth: 1.5,
                fill: false,
                pointRadius: 0
            });
        } else if (activeTab === 'pmv') {
            datasets.push({
                label: 'Baseline PMV Index',
                data: data.baseline.pmv,
                borderColor: '#86868b',
                borderDash: [4, 4],
                borderWidth: 1.5,
                fill: false,
                pointRadius: 0
            });
            if (data.optimal) {
                datasets.push({
                    label: 'AI-Optimized PMV Index',
                    data: data.optimal.pmv,
                    borderColor: '#0071e3',
                    backgroundColor: gradientBlue,
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0
                });
            }
        } else if (activeTab === 'energy') {
            datasets.push({
                label: 'Baseline Hourly Energy (kWh)',
                data: data.baseline.electricity_kwh,
                backgroundColor: '#e5e5ea',
                borderRadius: 0,
                type: 'bar'
            });
            if (data.optimal) {
                datasets.push({
                    label: 'AI-Optimized Hourly Energy (kWh)',
                    data: data.optimal.electricity_kwh,
                    backgroundColor: '#0071e3',
                    borderRadius: 0,
                    type: 'bar'
                });
            }
        }

        chartInstance = new Chart(ctx, {
            type: activeTab === 'energy' ? 'bar' : 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            font: { family: '-apple-system, SF Pro Display, sans-serif', size: 12, weight: '500' },
                            color: '#1d1d1f',
                            padding: 16,
                            usePointStyle: true,
                            boxWidth: 8
                        }
                    },
                    tooltip: {
                        backgroundColor: '#ffffff',
                        titleColor: '#1d1d1f',
                        bodyColor: '#86868b',
                        borderColor: 'rgba(0, 0, 0, 0.1)',
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 0,
                        titleFont: { family: '-apple-system, sans-serif', size: 12, weight: '600' },
                        bodyFont: { family: '-apple-system, sans-serif', size: 12 }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(0, 0, 0, 0.04)', drawBorder: false },
                        ticks: { color: '#86868b', font: { family: '-apple-system, sans-serif', size: 11 } }
                    },
                    y: {
                        grid: { color: 'rgba(0, 0, 0, 0.04)', drawBorder: false },
                        ticks: { color: '#86868b', font: { family: '-apple-system, sans-serif', size: 11 } }
                    }
                }
            }
        });

    } catch (err) {
        console.error('Error fetching timeseries:', err);
    }
}

