import { describe, expect, it } from 'vitest';
import { filterCandidates, paretoRoles } from './mapLogic.js';

describe('Pareto roles', () => {
  it('finds minimum cost, maximum coverage and geometric knee independent of input order', () => {
    const rows = [
      { solution_id: 'balanced', total_cost_bdt: 60, demand_coverage_pct: 60 },
      { solution_id: 'coverage', total_cost_bdt: 100, demand_coverage_pct: 100 },
      { solution_id: 'cheap', total_cost_bdt: 20, demand_coverage_pct: 20 },
    ];
    const result = paretoRoles(rows);
    expect(rows[result.indexes['Minimum cost']].solution_id).toBe('cheap');
    expect(rows[result.indexes['Maximum coverage']].solution_id).toBe('coverage');
    expect(rows[result.indexes['Knee point']].solution_id).toBe('balanced');
  });

  it('handles an empty frontier', () => {
    expect(paretoRoles([])).toEqual({ roles: [], indexes: {} });
  });
});

describe('candidate filters', () => {
  const features = [
    { properties: { candidate_id: 'a', site_name: 'S1', zone_name: 'Motijheel_Dilkusha', ahp_suitability_score: 0.8 } },
    { properties: { candidate_id: 'b', site_name: 'S2', zone_name: 'Badda_Mohakhali', ahp_suitability_score: 0.7 } },
    { properties: { candidate_id: 'c', site_name: 'S3', zone_name: 'Purbachal_Suburbs', ahp_suitability_score: 0.9 } },
  ];
  it('maps display zones to real dataset zones and applies score and text filters', () => {
    expect(filterCandidates(features, {}, 'Motijheel Commercial Zone (CBD)', 0.5)).toHaveLength(1);
    expect(filterCandidates(features, {}, 'Mohakhali & Tejgaon Industrial', 0.5)).toHaveLength(1);
    expect(filterCandidates(features, {}, 'Purbachal 300ft Corridor', 0.85)).toHaveLength(1);
    expect(filterCandidates(features, {}, 'ALL', 0.75, 's1')).toHaveLength(1);
  });
});
