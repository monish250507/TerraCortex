/**
 * AEGIS — Government Intelligence Command Center
 * Frontend logic: auth, dashboard, feed, alerts, charts, detail modal
 */
(function () {
    'use strict';

    const API = 'http://127.0.0.1:8001';
    let authToken = localStorage.getItem('aegis_token') || null;
    let currentAdvisoryId = null;
    let refreshTimer = null;

    // ── Charts ──
    let chartAir, chartHeat, chartComposite;

    // ══════════════════════════════════════════════════════
    // AUTH
    // ══════════════════════════════════════════════════════

    function showLogin() {
        console.log('Showing login screen');
        const loginScreen = document.getElementById('loginScreen');
        const mainApp = document.getElementById('mainApp');
        console.log('Login screen element:', loginScreen);
        console.log('Main app element:', mainApp);
        loginScreen.style.display = 'flex';
        mainApp.style.display = 'none';
        console.log('Login screen display:', loginScreen.style.display);
        console.log('Main app display:', mainApp.style.display);
    }

    function showApp() {
        console.log('Showing main app');
        const loginScreen = document.getElementById('loginScreen');
        const mainApp = document.getElementById('mainApp');
        console.log('Login screen element:', loginScreen);
        console.log('Main app element:', mainApp);
        loginScreen.style.display = 'none';
        mainApp.style.display = 'block';
        console.log('Login screen display:', loginScreen.style.display);
        console.log('Main app display:', mainApp.style.display);
        initCharts();
        loadDashboard();
        startAutoRefresh();
    }

    async function login() {
        console.log('Login function called');
        const user = document.getElementById('loginUser').value.trim();
        const pass = document.getElementById('loginPass').value;
        const errEl = document.getElementById('loginError');
        console.log('Username:', user);
        console.log('Password length:', pass.length);
        errEl.style.display = 'none';

        try {
            const resp = await fetch(`${API}/api/gov/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: user, password: pass }),
            });
            console.log('Login response status:', resp.status);
            if (!resp.ok) throw new Error('Auth failed');
            const data = await resp.json();
            console.log('Login response data:', data);
            authToken = data.access_token;
            localStorage.setItem('aegis_token', authToken);
            console.log('Token stored, showing app');
            showApp();
        } catch (error) {
            console.error('Login error:', error);
            errEl.style.display = 'block';
        }
    }

    function logout() {
        authToken = null;
        localStorage.removeItem('aegis_token');
        if (refreshTimer) clearInterval(refreshTimer);
        showLogin();
    }

    function authHeaders() {
        return { Authorization: `Bearer ${authToken}` };
    }

    async function apiFetch(url) {
        console.log(`Making API call to: ${API}${url}`);
        try {
            const resp = await fetch(`${API}${url}`, { headers: authHeaders() });
            console.log(`API response status: ${resp.status}`);
            if (resp.status === 401) { 
                console.log('Unauthorized access, logging out');
                logout(); 
                throw new Error('Unauthorized'); 
            }
            if (!resp.ok) {
                console.error(`API call failed with status: ${resp.status}`);
                throw new Error(`HTTP error! status: ${resp.status}`);
            }
            const data = await resp.json();
            console.log(`API response data:`, data);
            return data;
        } catch (error) {
            console.error(`API fetch error for ${url}:`, error);
            throw error;
        }
    }

    // ══════════════════════════════════════════════════════
    // DASHBOARD
    // ══════════════════════════════════════════════════════

    async function loadDashboard() {
        console.log('Loading dashboard...');
        try {
            const data = await apiFetch('/api/gov/dashboard');
            console.log('Dashboard data:', data);
            updateRiskCard('air', data.air);
            updateRiskCard('heat', data.heat);
            updateRiskCard('composite', data.composite);

            document.getElementById('alertCount').textContent = data.active_alerts;
            if (data.last_updated) {
                const d = new Date(data.last_updated);
                document.getElementById('lastUpdated').textContent = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
            }
        } catch (e) {
            console.warn('Dashboard load error:', e);
        }

        loadQuickFeed();
        loadAlerts();
        loadTrends();
        loadHealth();
    }

    function updateRiskCard(type, d) {
        console.log(`Updating risk card for ${type}:`, d);
        if (!d) {
            console.log(`No data for ${type} risk card`);
            return;
        }
        const score = d.score != null ? d.score.toFixed(1) : '--';
        const scoreElement = document.getElementById(`${type}Score`);
        console.log(`${type}Score element:`, scoreElement);
        if (scoreElement) {
            scoreElement.innerHTML = `${score}<span class="risk-card-score-unit">/100</span>`;
        }

        // Status badge
        const statusEl = document.getElementById(`${type}Status`);
        console.log(`${type}Status element:`, statusEl);
        if (statusEl) {
            statusEl.textContent = d.status || '--';
            statusEl.className = 'risk-card-status status-' + (d.status || 'normal').toLowerCase();
        }

        // Value
        if (type === 'air') {
            const airValueElement = document.getElementById('airValue');
            console.log('airValue element:', airValueElement);
            if (airValueElement) {
                airValueElement.textContent = `PM2.5: ${d.value != null ? d.value.toFixed(1) : '--'} ${d.unit || 'µg/m³'}`;
            }
        } else if (type === 'heat') {
            const heatValueElement = document.getElementById('heatValue');
            console.log('heatValue element:', heatValueElement);
            if (heatValueElement) {
                heatValueElement.textContent = `Heat Index: ${d.value != null ? d.value.toFixed(1) : '--'} ${d.unit || '°C'}`;
            }
        } else {
            const compositeValueElement = document.getElementById('compositeValue');
            console.log('compositeValue element:', compositeValueElement);
            if (compositeValueElement) {
                compositeValueElement.textContent = `Amplification: ${d.amplification ? d.amplification.toFixed(3) : '--'}`;
            }
        }

        // Confidence
        const confidenceElement = document.getElementById(`${type}Confidence`);
        console.log(`${type}Confidence element:`, confidenceElement);
        if (confidenceElement) {
            confidenceElement.textContent = `Confidence: ${d.confidence != null ? d.confidence.toFixed(0) : '--'}%`;
        }

        // Trend
        const trendEl = document.getElementById(`${type}Trend`);
        console.log(`${type}Trend element:`, trendEl);
        if (trendEl) {
            const trendMap = { up: '↑ Rising', down: '↓ Falling', stable: '— Stable' };
            trendEl.textContent = trendMap[d.trend] || '— Stable';
            trendEl.className = `risk-card-trend trend-${d.trend || 'stable'}`;
        }
    }

    // ══════════════════════════════════════════════════════
    // INTELLIGENCE FEED
    // ══════════════════════════════════════════════════════

    async function loadQuickFeed() {
        try {
            const data = await apiFetch('/api/gov/feed?limit=8');
            renderFeed('quickFeed', data);
        } catch (e) { console.warn('Feed error:', e); }
    }

    async function loadFullFeed() {
        try {
            const data = await apiFetch('/api/gov/feed?limit=50');
            renderFeed('fullFeed', data);
        } catch (e) { console.warn('Feed error:', e); }
    }

    function renderFeed(containerId, entries) {
        const container = document.getElementById(containerId);
        if (!entries.length) {
            container.innerHTML = '<div class="empty-state">No intelligence entries</div>';
            return;
        }
        container.innerHTML = entries.map(e => {
            const time = e.timestamp ? new Date(e.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '--:--';
            const severityClass = `feed-severity-${e.severity || 'info'}`;
            return `
                <div class="feed-entry" onclick="this.classList.toggle('expanded')">
                    <div class="feed-entry-header">
                        <div class="feed-entry-title"><span class="feed-severity-badge ${severityClass}"></span>${e.title}</div>
                        <div class="feed-entry-time">${time}</div>
                    </div>
                    <div class="feed-entry-content">${e.content}</div>
                </div>`;
        }).join('');
    }

    // ══════════════════════════════════════════════════════
    // ALERTS
    // ══════════════════════════════════════════════════════

    async function loadAlerts() {
        try {
            const data = await apiFetch('/api/gov/alerts');
            renderAlerts('quickAlerts', data.active, true);
            renderAlerts('activeAlerts', data.active, true);
            renderAlerts('pastAlerts', data.past, false);
        } catch (e) { console.warn('Alerts error:', e); }
    }

    function renderAlerts(containerId, alerts, showActions) {
        const container = document.getElementById(containerId);
        if (!container) return;
        if (!alerts || !alerts.length) {
            container.innerHTML = '<div class="empty-state">No alerts</div>';
            return;
        }
        container.innerHTML = alerts.map(a => {
            const time = a.timestamp ? new Date(a.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }) : '';
            const sevClass = `alert-item-severity-${(a.severity || 'normal').toLowerCase()}`;
            return `
                <div class="alert-item ${sevClass}">
                    <div class="alert-item-body">
                        <div class="alert-item-message">${a.message}</div>
                        <div class="alert-item-meta">${a.severity} · ${a.type.replace(/_/g, ' ')} · ${time}</div>
                    </div>
                    ${showActions ? `
                        <div class="alert-item-actions">
                            <button class="aegis-btn aegis-btn-sm" onclick="acknowledgeAlert(${a.id})">ACK</button>
                        </div>
                    ` : ''}
                </div>`;
        }).join('');
    }

    window.acknowledgeAlert = async function (id) {
        try {
            await fetch(`${API}/api/gov/alerts/${id}/acknowledge`, {
                method: 'POST',
                headers: authHeaders(),
            });
            loadAlerts();
            loadDashboard();
        } catch (e) { console.warn('Ack error:', e); }
    };

    // ══════════════════════════════════════════════════════
    // ADVISORY
    // ══════════════════════════════════════════════════════

    async function generateAdvisory() {
        try {
            const resp = await fetch(`${API}/api/gov/advisory/generate`, {
                method: 'POST',
                headers: authHeaders(),
            });
            const data = await resp.json();
            currentAdvisoryId = data.id;
            document.getElementById('advisoryDraftText').textContent = data.message;
            document.getElementById('advisoryDraft').style.display = 'block';
        } catch (e) { console.warn('Advisory gen error:', e); }
    }

    async function approveAdvisory() {
        if (!currentAdvisoryId) return;
        try {
            await fetch(`${API}/api/gov/advisory/${currentAdvisoryId}/approve`, {
                method: 'POST',
                headers: authHeaders(),
            });
            document.getElementById('advisoryDraft').style.display = 'none';
            currentAdvisoryId = null;
            loadDashboard();
        } catch (e) { console.warn('Advisory approve error:', e); }
    }

    // ══════════════════════════════════════════════════════
    // TRENDS / CHARTS
    // ══════════════════════════════════════════════════════

    function initCharts() {
        console.log('Initializing charts...');
        try {
            chartAir = new AegisChart('chartAir', { yLabel: 'PM2.5 (µg/m³)', lineColor: '#A855F7' });
            console.log('Chart Air initialized:', chartAir);
            chartHeat = new AegisChart('chartHeat', { yLabel: 'Heat Index (°C)', lineColor: '#C084FC' });
            console.log('Chart Heat initialized:', chartHeat);
            chartComposite = new AegisChart('chartComposite', { yLabel: 'Risk Score', yMin: 0, yMax: 100, lineColor: '#7C3AED' });
            console.log('Chart Composite initialized:', chartComposite);
        } catch (error) {
            console.error('Error initializing charts:', error);
        }
    }

    async function loadTrends() {
        try {
            const data = await apiFetch('/api/gov/trends?hours=24');
            if (chartAir && data.pm25_values) chartAir.setData(data.labels, data.pm25_values);
            if (chartHeat && data.heat_index_values) chartHeat.setData(data.labels, data.heat_index_values);
            if (chartComposite && data.composite_scores) chartComposite.setData(data.labels, data.composite_scores);
        } catch (e) { console.warn('Trends error:', e); }
    }

    // ══════════════════════════════════════════════════════
    // SYSTEM HEALTH
    // ══════════════════════════════════════════════════════

    async function loadHealth() {
        // Engine agent statuses
        try {
            const data = await apiFetch('/api/gov/system-health');
            setHealth('healthObserver', data.observer_agent);
            setHealth('healthDetection', data.detection_engine);
            setHealth('healthInvestigation', data.investigation_engine);
            setHealth('healthExplanation', data.explanation_engine);
            setHealth('healthAutonomy', data.autonomy_mode);
        } catch (e) { console.warn('Health error:', e); }

        // Live API connectivity
        try {
            const resp = await fetch(`${API}/system/health`);
            const api = await resp.json();
            setApiHealth('healthOpenAQ', api.openaq);
            setApiHealth('healthOpenWeather', api.openweather);
            setApiHealth('healthOpenRouter', api.openrouter);
        } catch (e) { console.warn('API health error:', e); }
    }

    function setHealth(elId, info) {
        const el = document.getElementById(elId);
        if (!el || !info) return;
        el.textContent = info.status;
        el.className = 'health-item-status' + (info.status === 'Enabled' || info.status === 'Active' || info.status === 'Running' || info.status === 'Operational' || info.status === 'Connected' ? '' : ' inactive');
    }

    function setApiHealth(elId, status) {
        const el = document.getElementById(elId);
        if (!el) return;
        const isOk = status === 'connected';
        el.textContent = isOk ? 'Connected' : (status || 'Unknown');
        el.className = 'health-item-status' + (isOk ? '' : ' inactive');
    }

    // ══════════════════════════════════════════════════════
    // DETAIL MODAL
    // ══════════════════════════════════════════════════════

    async function openDetail(riskType) {
        try {
            const data = await apiFetch(`/api/gov/risk/${riskType}/detail`);
            const modal = document.getElementById('detailModal');
            const titleMap = { air: 'Air Pollution Risk — Detailed Intelligence', heat: 'Heat Stress Risk — Detailed Intelligence', composite: 'Composite Risk — Detailed Intelligence' };
            document.getElementById('modalTitle').textContent = titleMap[riskType] || 'Risk Detail';

            let gridHTML = '';
            gridHTML += detailItem('Risk Score', data.score != null ? data.score.toFixed(1) + '/100' : '--');
            gridHTML += detailItem('Confidence', data.confidence != null ? data.confidence.toFixed(0) + '%' : '--');

            if (riskType === 'air') {
                gridHTML += detailItem('Current PM2.5', data.current_value != null ? data.current_value.toFixed(1) + ' µg/m³' : '--');
                gridHTML += detailItem('Baseline Mean', data.baseline_mean != null ? data.baseline_mean.toFixed(1) + ' µg/m³' : 'Building...');
                gridHTML += detailItem('Deviation (Z-score)', data.zscore != null ? data.zscore.toFixed(3) : '--');
                gridHTML += detailItem('Historical Percentile', data.percentile != null ? data.percentile.toFixed(1) + 'th' : '--');
            } else if (riskType === 'heat') {
                gridHTML += detailItem('Heat Index', data.current_value != null ? data.current_value.toFixed(1) + ' °C' : '--');
                gridHTML += detailItem('Temperature', data.temperature != null ? data.temperature.toFixed(1) + ' °C' : '--');
                gridHTML += detailItem('Humidity', data.humidity != null ? data.humidity.toFixed(0) + '%' : '--');
                gridHTML += detailItem('Baseline Mean', data.baseline_mean != null ? data.baseline_mean.toFixed(1) + ' °C' : 'Building...');
                gridHTML += detailItem('Deviation (Z-score)', data.zscore != null ? data.zscore.toFixed(3) : '--');
                gridHTML += detailItem('Historical Percentile', data.percentile != null ? data.percentile.toFixed(1) + 'th' : '--');
            } else {
                gridHTML += detailItem('Air Contribution', data.air_contribution != null ? data.air_contribution.toFixed(1) : '--');
                gridHTML += detailItem('Heat Contribution', data.heat_contribution != null ? data.heat_contribution.toFixed(1) : '--');
                gridHTML += detailItem('Amplification Factor', data.amplification_factor != null ? data.amplification_factor.toFixed(4) : '--');
                gridHTML += detailItem('Synergistic Boost', data.synergistic_boost != null ? '+' + data.synergistic_boost.toFixed(1) : '--');
                gridHTML += detailItem('Air Risk Score', data.air_score != null ? data.air_score.toFixed(1) + '/100' : '--');
                gridHTML += detailItem('Heat Risk Score', data.heat_score != null ? data.heat_score.toFixed(1) + '/100' : '--');
            }

            document.getElementById('modalGrid').innerHTML = gridHTML;
            document.getElementById('modalSummaryText').textContent = data.intelligence_summary || 'No intelligence summary available — awaiting LLM processing.';

            if (data.anomaly_flags && data.anomaly_flags.length) {
                document.getElementById('modalSummaryText').textContent += '\n\n⚠ Anomaly Flags: ' + data.anomaly_flags.join(', ');
            }

            modal.classList.add('active');
        } catch (e) {
            console.warn('Detail error:', e);
        }
    }

    function detailItem(label, value) {
        return `
            <div class="modal-detail-item">
                <div class="modal-detail-label">${label}</div>
                <div class="modal-detail-value">${value}</div>
            </div>`;
    }

    // ══════════════════════════════════════════════════════
    // TABS
    // ══════════════════════════════════════════════════════

    function switchTab(tabId) {
        document.querySelectorAll('.aegis-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.querySelector(`.aegis-tab[data-tab="${tabId}"]`).classList.add('active');
        document.getElementById(`tab-${tabId}`).classList.add('active');

        if (tabId === 'feed') loadFullFeed();
        if (tabId === 'analytics') {
            loadTrends();
            setTimeout(() => {
                if (chartAir) chartAir._resize();
                if (chartHeat) chartHeat._resize();
                if (chartComposite) chartComposite._resize();
            }, 100);
        }
        if (tabId === 'alerts') loadAlerts();
        if (tabId === 'health') loadHealth();
    }

    // ══════════════════════════════════════════════════════
    // AUTO REFRESH
    // ══════════════════════════════════════════════════════

    function startAutoRefresh() {
        if (refreshTimer) clearInterval(refreshTimer);
        refreshTimer = setInterval(loadDashboard, 60000);
    }

    // ══════════════════════════════════════════════════════
    // TRIGGER CYCLE
    // ══════════════════════════════════════════════════════

    async function triggerCycle() {
        try {
            const btn = document.getElementById('triggerCycleBtn');
            btn.textContent = '⟳ ...';
            btn.disabled = true;
            await fetch(`${API}/api/trigger-cycle`, { method: 'POST' });
            await loadDashboard();
            btn.textContent = '⟳ CYCLE';
            btn.disabled = false;
        } catch (e) {
            console.warn('Cycle trigger error:', e);
            document.getElementById('triggerCycleBtn').textContent = '⟳ CYCLE';
            document.getElementById('triggerCycleBtn').disabled = false;
        }
    }

    // ══════════════════════════════════════════════════════
    // INIT
    // ══════════════════════════════════════════════════════

    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOM loaded, initializing AEGIS...');
        try {
            // Login
            const loginBtn = document.getElementById('loginBtn');
            const loginPass = document.getElementById('loginPass');
            const logoutBtn = document.getElementById('logoutBtn');
            
            if (loginBtn) {
                loginBtn.addEventListener('click', login);
                console.log('Login button event listener added');
            } else {
                console.error('Login button not found!');
            }
            
            if (loginPass) {
                loginPass.addEventListener('keydown', e => { if (e.key === 'Enter') login(); });
                console.log('Login password Enter key event listener added');
            } else {
                console.error('Login password field not found!');
            }
            
            if (logoutBtn) {
                logoutBtn.addEventListener('click', logout);
                console.log('Logout button event listener added');
            } else {
                console.error('Logout button not found!');
            }

            // Tabs
            const tabs = document.querySelectorAll('.aegis-tab');
            console.log(`Found ${tabs.length} tab elements`);
            tabs.forEach(tab => {
                tab.addEventListener('click', () => switchTab(tab.dataset.tab));
                console.log(`Tab listener added for ${tab.dataset.tab}`);
            });

            // Risk cards click → detail modal
            const riskCards = document.querySelectorAll('.risk-card');
            console.log(`Found ${riskCards.length} risk card elements`);
            riskCards.forEach(card => {
                card.addEventListener('click', () => openDetail(card.dataset.risk));
                console.log(`Risk card listener added for ${card.dataset.risk}`);
            });

            // Modal close
            const modalClose = document.getElementById('modalClose');
            const detailModal = document.getElementById('detailModal');
            if (modalClose) {
                modalClose.addEventListener('click', () => {
                    detailModal.classList.remove('active');
                });
                console.log('Modal close event listener added');
            }
            
            if (detailModal) {
                detailModal.addEventListener('click', e => {
                    if (e.target === e.currentTarget) e.currentTarget.classList.remove('active');
                });
                console.log('Modal overlay event listener added');
            }

            // Advisory
            const generateAdvisoryBtn = document.getElementById('generateAdvisoryBtn');
            const approveAdvisoryBtn = document.getElementById('approveAdvisoryBtn');
            
            if (generateAdvisoryBtn) {
                generateAdvisoryBtn.addEventListener('click', generateAdvisory);
                console.log('Generate advisory button event listener added');
            }
            
            if (approveAdvisoryBtn) {
                approveAdvisoryBtn.addEventListener('click', approveAdvisory);
                console.log('Approve advisory button event listener added');
            }

            // Trigger cycle
            const triggerCycleBtn = document.getElementById('triggerCycleBtn');
            if (triggerCycleBtn) {
                triggerCycleBtn.addEventListener('click', triggerCycle);
                console.log('Trigger cycle button event listener added');
            }

            // Check auth
            console.log('Checking authentication status...');
            if (authToken) {
                // Validate token by trying dashboard
                console.log('Validating existing token...');
                apiFetch('/api/gov/dashboard').then(() => {
                    console.log('Token valid, showing app');
                    showApp();
                }).catch((error) => {
                    console.log('Token invalid, showing login', error);
                    showLogin();
                });
            } else {
                console.log('No token found, showing login');
                showLogin();
            }
        } catch (error) {
            console.error('Error during DOM initialization:', error);
            // Fallback: show login screen
            showLogin();
        }
    });

})();
