/**
 * AEGIS — Lightweight Canvas Chart Renderer
 * Thin neon-purple lines on dark background with minimal grid.
 */

console.log('Loading AegisChart class...');

class AegisChart {
    constructor(canvasId, options = {}) {
        console.log(`Initializing AegisChart with canvasId: ${canvasId}`);
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error(`Canvas element with id '${canvasId}' not found`);
            return;
        }
        this.ctx = this.canvas.getContext('2d');
        this.options = {
            lineColor: options.lineColor || '#A855F7',
            lineWidth: options.lineWidth || 2,
            gridColor: options.gridColor || 'rgba(106, 13, 173, 0.12)',
            labelColor: options.labelColor || '#5A5A72',
            fillGradient: options.fillGradient !== false,
            yMin: options.yMin ?? null,
            yMax: options.yMax ?? null,
            yLabel: options.yLabel || '',
            ...options,
        };
        this.data = { labels: [], values: [] };
        this._resize();
        window.addEventListener('resize', () => this._resize());
        console.log(`AegisChart initialized for ${canvasId}`);
    }

    _resize() {
        console.log('Resizing chart...');
        if (!this.canvas || !this.canvas.parentElement) {
            console.error('Canvas or parent element not found');
            return;
        }
        try {
            const rect = this.canvas.parentElement.getBoundingClientRect();
            this.canvas.width = rect.width * (window.devicePixelRatio || 1);
            this.canvas.height = rect.height * (window.devicePixelRatio || 1);
            this.canvas.style.width = rect.width + 'px';
            this.canvas.style.height = rect.height + 'px';
            this.ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
            this.width = rect.width;
            this.height = rect.height;
            this.render();
            console.log('Chart resized');
        } catch (error) {
            console.error('Error resizing chart:', error);
        }
    }

    setData(labels, values) {
        console.log('Setting chart data:', { labels, values });
        this.data = { labels, values };
        this.render();
    }

    render() {
        console.log('Rendering chart...');
        try {
            const { ctx, width, height, data, options } = this;
            if (!ctx || !data.values.length) {
                console.log('No data to render');
                return;
            }

            ctx.clearRect(0, 0, width, height);

            const padding = { top: 20, right: 20, bottom: 35, left: 50 };
            const chartW = width - padding.left - padding.right;
            const chartH = height - padding.top - padding.bottom;

            const vals = data.values;
            const yMin = options.yMin !== null ? options.yMin : Math.min(...vals) * 0.9;
            const yMax = options.yMax !== null ? options.yMax : Math.max(...vals) * 1.1;
            const yRange = yMax - yMin || 1;

            // ── Grid lines ──
            ctx.strokeStyle = options.gridColor;
            ctx.lineWidth = 0.5;
            const gridLines = 5;
            for (let i = 0; i <= gridLines; i++) {
                const y = padding.top + (chartH / gridLines) * i;
                ctx.beginPath();
                ctx.moveTo(padding.left, y);
                ctx.lineTo(width - padding.right, y);
                ctx.stroke();

                // Y-axis labels
                const val = yMax - (yRange / gridLines) * i;
                ctx.fillStyle = options.labelColor;
                ctx.font = '10px "JetBrains Mono", monospace';
                ctx.textAlign = 'right';
                ctx.fillText(val.toFixed(0), padding.left - 8, y + 4);
            }

            // ── X-axis labels ──
            ctx.fillStyle = options.labelColor;
            ctx.font = '10px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            const labelStep = Math.max(1, Math.floor(data.labels.length / 8));
            for (let i = 0; i < data.labels.length; i += labelStep) {
                const x = padding.left + (chartW / (vals.length - 1)) * i;
                ctx.fillText(data.labels[i], x, height - padding.bottom + 18);
            }

            // ── Data line ──
            if (vals.length < 2) {
                console.log('Not enough data points to render line');
                return;
            }

            const points = vals.map((v, i) => ({
                x: padding.left + (chartW / (vals.length - 1)) * i,
                y: padding.top + chartH - ((v - yMin) / yRange) * chartH,
            }));

            // Fill gradient
            if (options.fillGradient) {
                const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
                gradient.addColorStop(0, 'rgba(168, 85, 247, 0.15)');
                gradient.addColorStop(1, 'rgba(168, 85, 247, 0.0)');
                ctx.fillStyle = gradient;
                ctx.beginPath();
                ctx.moveTo(points[0].x, padding.top + chartH);
                points.forEach(p => ctx.lineTo(p.x, p.y));
                ctx.lineTo(points[points.length - 1].x, padding.top + chartH);
                ctx.closePath();
                ctx.fill();
            }

            // Line
            ctx.strokeStyle = options.lineColor;
            ctx.lineWidth = options.lineWidth;
            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {
                ctx.lineTo(points[i].x, points[i].y);
            }
            ctx.stroke();

            // End dot
            const last = points[points.length - 1];
            ctx.fillStyle = options.lineColor;
            ctx.beginPath();
            ctx.arc(last.x, last.y, 4, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = 'rgba(168, 85, 247, 0.4)';
            ctx.lineWidth = 8;
            ctx.beginPath();
            ctx.arc(last.x, last.y, 4, 0, Math.PI * 2);
            ctx.stroke();

            // Y-axis label
            if (options.yLabel) {
                ctx.save();
                ctx.fillStyle = options.labelColor;
                ctx.font = '10px "Inter", sans-serif';
                ctx.translate(12, padding.top + chartH / 2);
                ctx.rotate(-Math.PI / 2);
                ctx.textAlign = 'center';
                ctx.fillText(options.yLabel, 0, 0);
                ctx.restore();
            }
            console.log('Chart rendered successfully');
        } catch (error) {
            console.error('Error rendering chart:', error);
        }
    }
}
