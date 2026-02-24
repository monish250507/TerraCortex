/**
 * AEGIS — Public Advisory Layer
 * Calm, non-panic-inducing environmental status display.
 */
(function () {
    'use strict';

    const API = 'http://127.0.0.1:8001';
    let lastAdvisoryMessage = '';
    let chartAir, chartHeat;

    // ── Soft notification tone via Web Audio API ──
    function playNotificationTone() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.type = 'sine';
            osc.frequency.setValueAtTime(520, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(420, ctx.currentTime + 0.6);

            gain.gain.setValueAtTime(0.12, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.8);

            osc.connect(gain);
            gain.connect(ctx.destination);

            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.8);
        } catch (e) {
            // Audio not available
        }
    }

    // ── Load Public Status ──
    async function loadStatus() {
        console.log('Loading public status...');
        try {
            const resp = await fetch(`${API}/api/public/status`);
            console.log('Status response:', resp.status);
            if (!resp.ok) {
                throw new Error(`HTTP error! status: ${resp.status}`);
            }
            const data = await resp.json();
            console.log('Status data:', data);

            // Central indicator
            const ring = document.getElementById('statusRing');
            const text = document.getElementById('statusText');
            console.log('Status ring element:', ring);
            console.log('Status text element:', text);
            const level = data.overall || 'LOW';

            if (text) {
                text.textContent = level;
            }
            if (ring) {
                ring.className = 'public-status-ring level-' + level.toLowerCase();
            }

            // Set text color based on level
            const colorClass = 'level-' + level.toLowerCase() + '-text';
            if (text) {
                text.style.color = getComputedStyle(document.documentElement).getPropertyValue(
                    level === 'LOW' ? '--severity-normal' :
                        level === 'MODERATE' ? '--severity-moderate' : '--severity-high'
                );
            }

            // Risk levels
            setLevel('publicAirLevel', data.air_level);
            setLevel('publicHeatLevel', data.heat_level);
            setLevel('publicCompositeLevel', data.composite_level);
        } catch (e) {
            console.error('Status load error:', e);
        }
    }

    function setLevel(elId, level) {
        console.log(`Setting level for ${elId}:`, level);
        const el = document.getElementById(elId);
        console.log('Element:', el);
        if (!el) {
            console.log(`Element ${elId} not found`);
            return;
        }
        el.textContent = level || 'LOW';
        el.className = 'public-risk-value level-' + (level || 'low').toLowerCase() + '-text';
    }

    // ── Load Advisory ──
    async function loadAdvisory() {
        console.log('Loading public advisory...');
        try {
            const resp = await fetch(`${API}/api/public/advisory`);
            console.log('Advisory response:', resp.status);
            if (!resp.ok) {
                throw new Error(`HTTP error! status: ${resp.status}`);
            }
            const data = await resp.json();
            console.log('Advisory data:', data);

            const messageElement = document.getElementById('advisoryMessage');
            console.log('Advisory message element:', messageElement);
            if (messageElement) {
                messageElement.textContent = data.message;
            }

            // Play single notification if new advisory appeared
            if (data.has_advisory && data.message !== lastAdvisoryMessage && lastAdvisoryMessage !== '') {
                playNotificationTone();
            }
            lastAdvisoryMessage = data.message;
        } catch (e) {
            console.error('Advisory load error:', e);
        }
    }

    // ── Load Trends ──
    async function loadTrends() {
        console.log('Loading public trends...');
        try {
            const resp = await fetch(`${API}/api/public/trends`);
            console.log('Trends response:', resp.status);
            if (!resp.ok) {
                throw new Error(`HTTP error! status: ${resp.status}`);
            }
            const data = await resp.json();
            console.log('Trends data:', data);

            if (chartAir && data.air_trend) {
                console.log('Setting air trend data');
                chartAir.setData(data.labels, data.air_trend);
            }
            if (chartHeat && data.heat_trend) {
                console.log('Setting heat trend data');
                chartHeat.setData(data.labels, data.heat_trend);
            }
        } catch (e) {
            console.error('Trends error:', e);
        }
    }

    // ── Init ──
    document.addEventListener('DOMContentLoaded', () => {
        console.log('Initializing public page...');
        chartAir = new AegisChart('publicChartAir', {
            lineColor: '#A855F7',
            yMin: 0,
            yMax: 4,
            yLabel: 'Level',
        });
        chartHeat = new AegisChart('publicChartHeat', {
            lineColor: '#C084FC',
            yMin: 0,
            yMax: 4,
            yLabel: 'Level',
        });

        // Initial load
        loadStatus();
        loadAdvisory();
        loadTrends();

        // Refresh every 5 minutes
        setInterval(() => {
            loadStatus();
            loadAdvisory();
            loadTrends();
        }, 300000);
    });

})();
