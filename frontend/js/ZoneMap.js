/**
 * AEGIS ZoneMap Component
 * Renders an interactive SVG of Chennai zones (North, Central, South, East, West).
 */

class ZoneMap {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.svgNS = "http://www.w3.org/2000/svg";

        // Very basic stylized coordinates representing the 5 zones of Chennai footprint
        this.zonePaths = {
            "North": "M 40,20 L 70,10 L 80,40 L 40,40 Z",
            "Central": "M 40,40 L 80,40 L 70,70 L 30,60 Z",
            "South": "M 30,60 L 70,70 L 60,100 L 20,90 Z",
            "East": "M 80,40 L 100,50 L 90,80 L 70,70 Z",
            "West": "M 10,30 L 40,40 L 30,60 L 10,50 Z"
        };

        this.tooltip = this.createTooltip();
        this.renderMap();
        this.fetchData();

        // Poll for updates every minute
        setInterval(() => this.fetchData(), 60000);
    }

    createTooltip() {
        const tooltip = document.createElement("div");
        tooltip.style.position = "fixed";
        tooltip.style.padding = "10px";
        tooltip.style.backgroundColor = "rgba(10, 15, 20, 0.95)";
        tooltip.style.border = "1px solid #1a2332";
        tooltip.style.borderRadius = "4px";
        tooltip.style.color = "#a0aec0";
        tooltip.style.fontFamily = "monospace";
        tooltip.style.fontSize = "12px";
        tooltip.style.pointerEvents = "none";
        tooltip.style.display = "none";
        tooltip.style.zIndex = "1000";
        tooltip.style.boxShadow = "0 4px 6px -1px rgba(0, 0, 0, 0.5)";
        document.body.appendChild(tooltip);
        return tooltip;
    }

    renderMap() {
        this.svg = document.createElementNS(this.svgNS, "svg");
        this.svg.setAttribute("viewBox", "0 0 110 110");
        this.svg.setAttribute("width", "100%");
        this.svg.setAttribute("height", "100%");
        this.svg.style.filter = "drop-shadow(0 0 10px rgba(0,0,0,0.5))";

        this.polygons = {};

        for (const [zoneName, dPath] of Object.entries(this.zonePaths)) {
            const path = document.createElementNS(this.svgNS, "path");
            path.setAttribute("d", dPath);
            path.setAttribute("fill", "#1a2332"); // Default loading color
            path.setAttribute("stroke", "#2d3748");
            path.setAttribute("stroke-width", "1");
            path.style.cursor = "pointer";
            path.style.transition = "fill 0.3s ease, transform 0.2s ease";
            path.style.transformOrigin = "center";

            // Hover effects
            path.addEventListener("mouseover", (e) => {
                path.setAttribute("stroke", "#63b3ed");
                path.setAttribute("stroke-width", "1.5");
                this.tooltip.style.display = "block";
            });

            path.addEventListener("mousemove", (e) => {
                this.tooltip.style.left = e.clientX + 15 + "px";
                this.tooltip.style.top = e.clientY + 15 + "px";
            });

            path.addEventListener("mouseout", () => {
                path.setAttribute("stroke", "#2d3748");
                path.setAttribute("stroke-width", "1");
                this.tooltip.style.display = "none";
            });

            this.svg.appendChild(path);
            this.polygons[zoneName] = path;
        }

        this.container.appendChild(this.svg);
    }

    async fetchData() {
        try {
            const res = await fetch("/api/public/zones/risk");
            if (!res.ok) throw new Error("API failed");
            const data = await res.json();
            this.updateZoneColors(data);
        } catch (error) {
            console.error("Failed to load zone map data:", error);
        }
    }

    updateZoneColors(data) {
        for (const [zoneName, metrics] of Object.entries(data)) {
            const poly = this.polygons[zoneName];
            if (!poly) continue;

            let fillCol = "#22c55e"; // low -> green
            if (metrics.composite_score >= 70) {
                fillCol = "#ef4444"; // high -> red
            } else if (metrics.composite_score >= 40) {
                fillCol = "#eab308"; // mod -> yellow
            }

            poly.setAttribute("fill", fillCol);

            // Update Tooltip HTML
            poly.addEventListener("mouseover", () => {
                this.tooltip.innerHTML = `
                    <div style="font-weight: bold; color: white; margin-bottom: 5px; border-bottom: 1px solid #2d3748; padding-bottom: 3px;">
                        Zone: ${zoneName}
                    </div>
                    <div>Composite Risk: <span style="color: ${fillCol}">${metrics.composite_score.toFixed(1)}</span></div>
                    <div>Air Risk: ${metrics.air_score.toFixed(1)}</div>
                    <div>Heat Risk: ${metrics.heat_score.toFixed(1)}</div>
                    <div>Flood Risk: ${metrics.flood_score.toFixed(1)}</div>
                    <div>Smoke Risk: ${metrics.smoke_score.toFixed(1)}</div>
                `;
            });
        }
    }
}
