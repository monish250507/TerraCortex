"""
AEGIS Resource Optimizer — Recommends intervention allocations using linear programming (PuLP).
"""
import pulp
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
import logging
from engine.intervention_simulator import simulate_intervention
from models import RiskAssessment, Zone

logger = logging.getLogger("aegis.engine.optimizer")

def optimize_resources(db: Session, total_budget: float) -> Dict[str, Any]:
    """
    Simulate the effect of various interventions and allocate resources
    to maximize total risk reduction across zones.
    """
    # Hardcoded costs and effectiveness for simplicity
    COST_COOLING = 50000
    COST_MASK = 10000
    
    zones = db.query(Zone).all()
    if not zones:
        return {"error": "No zones found"}
        
    prob = pulp.LpProblem("Maximize_Risk_Reduction", pulp.LpMaximize)
    
    cooling_vars = {}
    mask_vars = {}
    for z in zones:
        cooling_vars[z.id] = pulp.LpVariable(f"cooling_{z.id}", lowBound=0, cat='Integer')
        mask_vars[z.id] = pulp.LpVariable(f"masks_{z.id}", lowBound=0, cat='Integer')
        
    objective_terms = []
    
    latest_risks = {}
    for z in zones:
        latest = db.query(RiskAssessment).filter(RiskAssessment.zone_id == z.id).order_by(desc(RiskAssessment.timestamp)).first()
        if latest:
            latest_risks[z.id] = latest
            
            density_factor = z.population / (z.area_km2 * 1000) if z.area_km2 else 1.0
            
            heat_risk = latest.heat_score / 100.0
            air_risk = latest.air_score / 100.0
            
            # Simple heuristic score per intervention based on population and existing risk
            cc_impact_score = heat_risk * density_factor
            mask_impact_score = air_risk * density_factor
            
            objective_terms.append(cc_impact_score * cooling_vars[z.id])
            objective_terms.append(mask_impact_score * mask_vars[z.id])
            
    if not objective_terms:
        return {"error": "No assessment data available"}
        
    prob += pulp.lpSum(objective_terms), "Total_Risk_Reduction_Score"
    
    # Constraints
    # Budget constraint
    prob += pulp.lpSum([COST_COOLING * cooling_vars[z.id] + COST_MASK * mask_vars[z.id] for z in zones]) <= total_budget, "Budget_Constraint"
    
    # Capacity constraint (max 5 CCs and 10 Masks per zone)
    for z in zones:
        prob += cooling_vars[z.id] <= 5, f"Capacity_CC_{z.id}"
        prob += mask_vars[z.id] <= 10, f"Capacity_Masks_{z.id}"
        
    # Solve
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    
    allocation_matrix = {}
    total_budget_utilized = 0.0
    estimated_total_risk_reduction = 0.0 
    
    if pulp.LpStatus[prob.status] == 'Optimal':
        for z in zones:
            cc_assigned = int(cooling_vars[z.id].varValue)
            mask_assigned = int(mask_vars[z.id].varValue)
            
            allocation_matrix[z.name] = {
                "cooling_centers": cc_assigned,
                "mask_units": mask_assigned
            }
            
            total_budget_utilized += cc_assigned * COST_COOLING + mask_assigned * COST_MASK
            
            # Estimate risk points reduced (roughly 2 composite points per CC, 1 point per MU)
            if z.id in latest_risks:
                estimated_total_risk_reduction += cc_assigned * 2.0 + mask_assigned * 1.0
                
        return {
            "status": "Optimal",
            "allocation_matrix": allocation_matrix,
            "expected_total_risk_reduction": round(estimated_total_risk_reduction, 1),
            "budget_utilization": round(total_budget_utilized, 2),
            "total_budget": total_budget
        }
    else:
        return {"error": f"Optimization failed: {pulp.LpStatus[prob.status]}"}
