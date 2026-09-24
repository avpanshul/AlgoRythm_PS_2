from app.schemas.canonical import CanonicalEvent
from app.core.config import settings
from typing import Dict, Any

class RiskEngine:
    def __init__(self):
        self.weights = settings.RISK_WEIGHTS
        self.severity_map = {
            "critical": 100,
            "high": 80,
            "medium": 50,
            "low": 20,
            "info": 0,
            "unknown": 10
        }
        self.action_risk_map = {
            "deny": 30,
            "allow": 10,
            "login_failure": 70,
            "login_success": 20,
            "port_scan": 60,
            "malware": 100,
            "privilege_escalation": 95,
            "unknown": 20
        }
        
    def calculate_risk(self, event: CanonicalEvent, correlation_score: int = 0, frequency_score: int = 0) -> Dict[str, Any]:
        # Base factors
        severity_score = self.severity_map.get(event.event.severity.lower(), 10)
        action_score = self.action_risk_map.get(event.event.action.lower(), 20)
        
        # We can simulate asset criticality from source/destination IPs later
        asset_score = 50 # Default baseline
        
        w_sev = self.weights.get("severity", 0.3)
        w_act = self.weights.get("action", 0.2)
        w_freq = self.weights.get("frequency", 0.2)
        w_asset = self.weights.get("asset", 0.15)
        w_corr = self.weights.get("correlation", 0.15)
        
        total_risk = (
            (severity_score * w_sev) +
            (action_score * w_act) +
            (frequency_score * w_freq) +
            (asset_score * w_asset) +
            (correlation_score * w_corr)
        )
        
        total_risk = min(100, max(0, int(total_risk)))
        
        if total_risk >= 80:
            level = "CRITICAL"
        elif total_risk >= 60:
            level = "HIGH"
        elif total_risk >= 30:
            level = "MEDIUM"
        else:
            level = "LOW"
            
        factors = [
            {"factor": "severity", "contribution": int(severity_score * w_sev)},
            {"factor": "action", "contribution": int(action_score * w_act)},
            {"factor": "frequency", "contribution": int(frequency_score * w_freq)},
            {"factor": "asset_criticality", "contribution": int(asset_score * w_asset)},
            {"factor": "correlation", "contribution": int(correlation_score * w_corr)}
        ]
        
        return {
            "score": total_risk,
            "level": level,
            "factors": factors
        }

risk_engine = RiskEngine()
