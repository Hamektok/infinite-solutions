
const SYSTEMS        = [{"name":"4-HWWF","ly":0},{"name":"PM-DWE","ly":0.893},{"name":"4GYV-Q","ly":0.937},{"name":"EIDI-N","ly":1.023},{"name":"YMJG-4","ly":1.136},{"name":"DAYP-G","ly":1.356},{"name":"WBR5-R","ly":1.443},{"name":"8TPX-N","ly":1.491},{"name":"KRUN-N","ly":1.499},{"name":"TVN-FM","ly":1.502},{"name":"IPAY-2","ly":1.577},{"name":"K8X-6B","ly":1.72},{"name":"0MV-4W","ly":1.927},{"name":"AZBR-2","ly":2.03},{"name":"Q-L07F","ly":2.198},{"name":"U54-1L","ly":2.247},{"name":"P3EN-E","ly":2.278},{"name":"T-GCGL","ly":2.44},{"name":"V-OJEN","ly":2.469},{"name":"X445-5","ly":2.533},{"name":"05R-7A","ly":2.559},{"name":"FS-RFL","ly":2.619},{"name":"NCGR-Q","ly":2.658},{"name":"Z-8Q65","ly":2.7},{"name":"IFJ-EL","ly":2.748},{"name":"9OO-LH","ly":2.759},{"name":"MC6O-F","ly":2.774},{"name":"X97D-W","ly":2.799},{"name":"49-0LI","ly":2.815},{"name":"0-R5TS","ly":2.844},{"name":"669-IX","ly":2.888},{"name":"0R-F2F","ly":3.002},{"name":"47L-J4","ly":3.07},{"name":"N-HSK0","ly":3.163},{"name":"HE-V4V","ly":3.182},{"name":"V-NL3K","ly":3.223},{"name":"0J3L-V","ly":3.232},{"name":"S-NJBB","ly":3.307},{"name":"XF-PWO","ly":3.361},{"name":"R-P7KL","ly":3.37},{"name":"A8A-JN","ly":3.386},{"name":"NFM-0V","ly":3.389},{"name":"E-D0VZ","ly":3.401},{"name":"6WW-28","ly":3.432},{"name":"UH-9ZG","ly":3.448},{"name":"YXIB-I","ly":3.497},{"name":"LZ-6SU","ly":3.503},{"name":"Y0-BVN","ly":3.631},{"name":"7-UH4Z","ly":3.631},{"name":"1N-FJ8","ly":3.718},{"name":"2DWM-2","ly":3.732},{"name":"H-UCD1","ly":3.802},{"name":"G-LOIT","ly":3.828},{"name":"1-GBBP","ly":3.837},{"name":"B-588R","ly":3.905},{"name":"5ZO-NZ","ly":4.132},{"name":"H-NOU5","ly":4.337},{"name":"97-M96","ly":4.356},{"name":"T-ZWA1","ly":4.379},{"name":"3HX-DL","ly":4.409},{"name":"7-K5EL","ly":4.429},{"name":"KX-2UI","ly":4.579},{"name":"GEKJ-9","ly":4.62},{"name":"MY-T2P","ly":4.817},{"name":"Y-ZXIO","ly":4.827},{"name":"C-FP70","ly":4.899},{"name":"G96R-F","ly":5.079},{"name":"Q-R3GP","ly":5.081},{"name":"ZA0L-U","ly":5.118},{"name":"FA-DMO","ly":5.257},{"name":"XV-8JQ","ly":5.341},{"name":"N-5QPW","ly":5.528},{"name":"MO-FIF","ly":5.566},{"name":"MA-XAP","ly":5.716},{"name":"H-5GUI","ly":5.717},{"name":"C-J7CR","ly":5.852},{"name":"Q-EHMJ","ly":5.941},{"name":"XSQ-TF","ly":6.193},{"name":"H-1EOH","ly":6.423},{"name":"FMBR-8","ly":6.451},{"name":"FH-TTC","ly":6.633},{"name":"VI2K-J","ly":6.669},{"name":"6Y-WRK","ly":6.755},{"name":"5T-KM3","ly":6.789},{"name":"IR-DYY","ly":6.818},{"name":"MQ-O27","ly":7.129},{"name":"ZLZ-1Z","ly":7.348},{"name":"F-D49D","ly":7.382},{"name":"RVCZ-C","ly":7.422},{"name":"B-E3KQ","ly":7.87},{"name":"Y5J-EU","ly":7.899},{"name":"H-EY0P","ly":8.008},{"name":"O-LR1H","ly":8.088},{"name":"LS9B-9","ly":8.17},{"name":"C-DHON","ly":8.317},{"name":"G5ED-Y","ly":8.656},{"name":"UNAG-6","ly":8.692},{"name":"A-QRQT","ly":8.849},{"name":"8-TFDX","ly":9.072},{"name":"BR-6XP","ly":9.092},{"name":"E-SCTX","ly":9.276},{"name":"7-PO3P","ly":9.281},{"name":"WMBZ-U","ly":9.319},{"name":"UL-4ZW","ly":9.656},{"name":"VORM-W","ly":9.73}];
const CONFIGS        = [{"econ":0,"exp":3,"fuelPerLY":3600.0,"effectiveCargo":362565.9375},{"econ":1,"exp":2,"fuelPerLY":3348.0,"effectiveCargo":285592.5},{"econ":2,"exp":1,"fuelPerLY":3144.313041,"effectiveCargo":225975.0},{"econ":3,"exp":0,"fuelPerLY":3018.7266,"effectiveCargo":179970.0}];
const RATE_PER_LY    = 12;
const RATE_FLAT      = 0;
const PRICING_MODE   = 'per_ly';
const COLLATERAL_PCT = 0;
const ISO_PRICE      = 676.0;
const HUB            = '4-HWWF';

// Format number with commas, optional decimal places
function fmt(n, d) {
  d = (d === undefined) ? 0 : d;
  if (!isFinite(n)) return '—';
  return n.toLocaleString('en-US', {minimumFractionDigits:d, maximumFractionDigits:d});
}

// Format a text input as integer with commas (volume)
function fmtVolInput(el) {
  var raw = el.value.replace(/[^0-9]/g, '');
  if (!raw) { el.value = ''; return; }
  el.value = parseInt(raw, 10).toLocaleString('en-US');
}

// Format a text input as decimal with commas (collateral)
function fmtCollInput(el) {
  var raw = el.value.replace(/[^0-9.]/g, '');
  // allow only one decimal point
  var parts = raw.split('.');
  var intPart = parts[0] ? parseInt(parts[0], 10).toLocaleString('en-US') : '';
  if (parts.length > 1) {
    el.value = intPart + '.' + parts[1].slice(0, 2);
  } else {
    el.value = intPart;
  }
}

function parseNum(val) {
  return parseFloat((val || '').replace(/,/g, '')) || 0;
}

function lookupLy(name) {
  var n = (name || '').trim().toUpperCase();
  if (!n) return null;
  for (var i = 0; i < SYSTEMS.length; i++) {
    if (SYSTEMS[i].name.toUpperCase() === n) return SYSTEMS[i].ly;
  }
  return undefined;
}

function onPickupChange() {
  var pickup  = (document.getElementById('sys_input').value || '').trim().toUpperCase();
  var distEl  = document.getElementById('sys_dist_note');
  var fixed   = document.getElementById('dest_fixed');
  var free    = document.getElementById('dest_input');

  if (pickup === HUB) {
    fixed.style.display = 'none';
    free.style.display  = '';
    if (free.value.toUpperCase() === HUB) free.value = '';
    distEl.textContent = 'Hub — choose destination below';
    distEl.style.color = 'var(--dim)';
  } else {
    fixed.style.display = '';
    free.style.display  = 'none';
    free.value = '';
    if (pickup === '') {
      fixed.textContent  = 'Select a pickup system first';
      fixed.style.fontStyle = 'italic';
      fixed.style.color  = 'var(--dim)';
      distEl.textContent = '';
    } else {
      fixed.textContent  = HUB;
      fixed.style.fontStyle = 'normal';
      fixed.style.color  = 'var(--text)';
      var ly = lookupLy(pickup);
      if (ly === undefined) {
        distEl.textContent = 'System not found';
        distEl.style.color = 'var(--red)';
      } else {
        distEl.textContent = ly.toFixed(3) + ' ly';
        distEl.style.color = '';
      }
    }
  }
  recalc();
}

function getRoute() {
  var pickup = (document.getElementById('sys_input').value || '').trim().toUpperCase();
  if (!pickup) return null;
  var ly, from, to;
  if (pickup === HUB) {
    var dest = (document.getElementById('dest_input').value || '').trim().toUpperCase();
    if (!dest) return null;
    ly = lookupLy(dest); from = HUB; to = dest;
  } else {
    ly = lookupLy(pickup); from = pickup; to = HUB;
  }
  if (ly == null || ly === undefined) return null;
  return { ly: ly, from: from, to: to };
}

function recalc() {
  var route = getRoute();
  var vol   = parseNum(document.getElementById('cargo_vol').value);
  var coll  = parseNum(document.getElementById('cargo_coll').value);

  // Update dest note for outbound
  var destNoteEl = document.getElementById('dest_note');
  var pickup = (document.getElementById('sys_input').value || '').trim().toUpperCase();
  if (pickup === HUB) {
    var destVal = (document.getElementById('dest_input').value || '').trim().toUpperCase();
    var destLy  = lookupLy(destVal);
    if (!destVal) {
      destNoteEl.textContent = '';
    } else if (destLy === undefined) {
      destNoteEl.textContent = 'System not found';
      destNoteEl.style.color = 'var(--red)';
    } else {
      destNoteEl.textContent = destLy.toFixed(3) + ' ly';
      destNoteEl.style.color = '';
    }
  } else {
    destNoteEl.textContent = '';
  }

  var emptyEl = document.getElementById('quote_empty');
  var cardEl  = document.getElementById('quote_card');

  if (!route || !vol) {
    emptyEl.style.display = '';
    cardEl.classList.remove('show');
    saveState();
    return;
  }

  var ly        = route.ly;
  var collFee   = coll * COLLATERAL_PCT / 100;
  var markupFee = PRICING_MODE === 'per_ly' ? RATE_PER_LY * ly * vol : RATE_FLAT * vol;
  var bestResult = null;

  CONFIGS.forEach(function(c) {
    var trips    = Math.ceil(vol / c.effectiveCargo);
    var isoUsed  = trips * ly * 2 * c.fuelPerLY;
    var fuelCost = isoUsed * ISO_PRICE;
    var total    = fuelCost + markupFee + collFee;
    if (bestResult === null || total < bestResult.total) {
      bestResult = { trips: trips, fuelCost: fuelCost, total: total };
    }
  });

  emptyEl.style.display = 'none';
  cardEl.classList.add('show');

  var totalISK = Math.round(bestResult.total);
  window._totalISK = totalISK;

  document.getElementById('q_total').textContent = fmt(totalISK, 0) + ' ISK';
  document.getElementById('copy_hint').textContent = 'click to copy';
  document.getElementById('q_route').textContent = route.from + ' → ' + route.to;
  document.getElementById('q_dist').textContent  = ly.toFixed(3) + ' ly (×2 round trip)';
  document.getElementById('q_vol').textContent   = fmt(Math.round(vol), 0) + ' m³';

  var collRow = document.getElementById('q_coll_row');
  if (coll > 0) {
    document.getElementById('q_coll').textContent = fmt(coll, 2) + ' ISK';
    collRow.style.display = '';
  } else {
    collRow.style.display = 'none';
  }

  var collFeeRow = document.getElementById('q_coll_fee_row');
  if (COLLATERAL_PCT > 0 && coll > 0) {
    document.getElementById('q_coll_fee').textContent = fmt(collFee, 2) + ' ISK';
    collFeeRow.style.display = '';
  } else {
    collFeeRow.style.display = 'none';
  }

  var ci = document.getElementById('contract_instructions');
  if (ci) {
    ci.innerHTML = 'Set reward to quoted fee &middot; Set collateral to declared value &middot; ' +
      'Pickup: <strong style="color:var(--accent2)">' + route.from + '</strong> &middot; ' +
      'Deliver to: <strong style="color:var(--accent2)">' + route.to + '</strong>';
  }

  saveState();
}

function copyTotal() {
  var n = window._totalISK;
  if (!n) return;
  var text = String(n);
  var el = document.getElementById('copy_hint');
  var wrap = document.querySelector('.reward-copy');
  var done = function() {
    if (el) el.textContent = '✓ Copied!';
    if (wrap) wrap.classList.add('copied');
    setTimeout(function() {
      if (el) el.textContent = 'click to copy';
      if (wrap) wrap.classList.remove('copied');
    }, 2000);
  };
  navigator.clipboard.writeText(text).then(done).catch(function() {
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select(); document.execCommand('copy');
    document.body.removeChild(ta); done();
  });
}

function saveState() {
  var s = {};
  ['cargo_vol', 'cargo_coll'].forEach(function(id) {
    var el = document.getElementById(id); if (el) s[id] = el.value;
  });
  try { localStorage.setItem('haul_quote_state', JSON.stringify(s)); } catch(e) {}
}

function loadState() {
  var raw; try { raw = localStorage.getItem('haul_quote_state'); } catch(e) {}
  if (!raw) { recalc(); return; }
  var s; try { s = JSON.parse(raw); } catch(e) { recalc(); return; }
  ['cargo_vol', 'cargo_coll'].forEach(function(id) {
    var el = document.getElementById(id); if (el && s[id] != null) el.value = s[id];
  });
  recalc();
}

window.onload = function() {
  loadState();
  var _lastPickup = document.getElementById('sys_input').value || '';
  setInterval(function() {
    var cur = document.getElementById('sys_input').value || '';
    if (cur !== _lastPickup) {
      _lastPickup = cur;
      onPickupChange();
    }
  }, 200);
};
