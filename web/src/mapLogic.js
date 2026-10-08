export function paretoRoles(rows) {
  if (!rows.length) return { roles: [], indexes: {} };
  const cost = row => Number(row.total_cost_bdt ?? Number(row.total_cost_million_bdt) * 1e6);
  const coverage = row => Number(row.demand_coverage_score ?? row.demand_coverage_pct);
  const minIndex = rows.reduce((best, row, i) => cost(row) < cost(rows[best]) ? i : best, 0);
  const maxIndex = rows.reduce((best, row, i) => coverage(row) > coverage(rows[best]) ? i : best, 0);
  const costs = rows.map(cost), coverages = rows.map(coverage);
  const minCost = Math.min(...costs), maxCost = Math.max(...costs);
  const minCoverage = Math.min(...coverages), maxCoverage = Math.max(...coverages);
  let kneeIndex = 0, maxDistance = -1;
  rows.forEach((row, i) => {
    const x = maxCost === minCost ? 0 : 1 - (cost(row) - minCost) / (maxCost - minCost);
    const y = maxCoverage === minCoverage ? 0 : (coverage(row) - minCoverage) / (maxCoverage - minCoverage);
    const distance = Math.abs(x + y - 1) / Math.SQRT2;
    if (distance > maxDistance) { maxDistance = distance; kneeIndex = i; }
  });
  const indexes = { 'Minimum cost': minIndex, 'Maximum coverage': maxIndex, 'Knee point': kneeIndex };
  return { indexes, roles: rows.map((row, i) => Object.entries(indexes).filter(([, index]) => index === i).map(([label]) => label)) };
}

export function filterCandidates(features, rankMap, selectedZone, minAhp, search = '') {
  const groups = {
    'Gulshan / Banani / Baridhara': ['Gulshan_Banani'],
    'Motijheel Commercial Zone (CBD)': ['Motijheel_Dilkusha'],
    'Mirpur (1, 10, 11, DOHS)': ['Mirpur'],
    'Uttara North Gateway': ['Uttara'],
    'Mohakhali & Tejgaon Industrial': ['Badda_Mohakhali', 'Kawran_Bazar_Tejgaon'],
    'Dhanmondi & Mohammadpur': ['Dhanmondi', 'Mohammadpur'],
    'Old Dhaka (Lalbagh/Sutrapur/Sadarghat)': ['Old_Dhaka'],
    'Purbachal 300ft Corridor': ['Purbachal_Suburbs'],
  };
  const zones = groups[selectedZone];
  const q = search.trim().toLowerCase();
  return features.filter(feature => {
    const properties = feature.properties || {};
    const rank = rankMap[properties.candidate_id] || {};
    const score = Number(rank.ahp_suitability_score ?? properties.ahp_suitability_score);
    const zone = properties.zone_name || rank.zone_name || '';
    const name = properties.site_name || '';
    return Number.isFinite(score) && score >= minAhp &&
      (!zones || zones.includes(zone)) &&
      (!q || `${name} ${zone}`.toLowerCase().includes(q));
  });
}
