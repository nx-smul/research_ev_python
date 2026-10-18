export const MAP_COLORS = Object.freeze({
  candidate: '#0072B2',
  selected: '#D55E00',
  demand: '#56B4E9',
  road: '#E69F00',
  landUse: '#009E73',
  landUseExcluded: '#CC79A7',
  evCharger: '#F0E442',
  fuelStation: '#4D4D4D',
  substationLow: '#332288',
  substationMedium: '#8877AA',
  substationHigh: '#CCBBEE',
});

export const SUBSTATION_HEADROOM_COLORS = Object.freeze([
  MAP_COLORS.substationLow,
  MAP_COLORS.substationMedium,
  MAP_COLORS.substationHigh,
]);

export const SUBSTATION_HEADROOM_COLOR_EXPRESSION = Object.freeze([
  'step',
  ['to-number', ['get', 'headroom_pct'], 0],
  MAP_COLORS.substationLow,
  15,
  MAP_COLORS.substationMedium,
  30,
  MAP_COLORS.substationHigh,
]);
