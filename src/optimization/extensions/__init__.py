"""Research extension modules for EVCS planning analysis."""

from src.optimization.extensions.uncertainty import write_uncertainty_screen
from src.optimization.extensions.equity import write_equity_accessibility
from src.optimization.extensions.time_profiles import write_time_profiles
from src.optimization.extensions.queueing import write_queue_screen
from src.optimization.extensions.grid_upgrade import write_grid_upgrade_screen
from src.optimization.extensions.field_validation import write_field_template
from src.optimization.extensions.investment import write_investment_scenarios
from src.optimization.extensions.carbon import write_carbon_analysis
from src.optimization.extensions.utilization import write_utilization_analysis
from src.optimization.extensions.robustness import write_portfolio_robustness, write_site_stability_matrix
from src.optimization.extensions.unmet_demand import write_unmet_demand_analysis, write_access_burden_analysis
from src.optimization.extensions.ahp_sensitivity import write_ahp_weight_sensitivity

__all__ = [
    "write_uncertainty_screen",
    "write_equity_accessibility",
    "write_time_profiles",
    "write_queue_screen",
    "write_grid_upgrade_screen",
    "write_field_template",
    "write_investment_scenarios",
    "write_carbon_analysis",
    "write_utilization_analysis",
    "write_portfolio_robustness",
    "write_site_stability_matrix",
    "write_unmet_demand_analysis",
    "write_access_burden_analysis",
    "write_ahp_weight_sensitivity",
]
