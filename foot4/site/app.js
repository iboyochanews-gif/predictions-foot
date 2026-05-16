/**
 * FOOT/4 — Frontend logic
 *
 * Charge ../data/predictions.json (généré toutes les 6h par GitHub Actions),
 * affiche le combo du jour + tous les matchs + jours suivants si dispo.
 */

const DATA_URL = '../data/predictions.json';
const FALLBACK_DATA_URL = './data/predictions.json';

// ============================================================ UTILITIES

const fmtPct = (p) => `${(p * 100).toFixed(1)}%`;
const fmtOdds = (o) => o.toFixed(2);
const fmtTime = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
};
const fmtDateTime = (iso) => {
  const d = new Date(iso);
  return d.toLocaleString('fr-FR', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
  });
};
const fmtDateLong = (iso) => {
  const d = new Date(iso);
  return d.toLocaleDateString('fr-FR', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  });
};

function fmtCountdown(target) {
  const ms = target - new Date();
  if (ms <= 0) return 'maintenant';
  const totalMin = Math.floor(ms / 60000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h > 0) return `${h}h${String(m).padStart(2, '0')}`;
  return `${m}m`;
}

const MARKET_LABEL = {
  '1':       'Domicile',
  'X':       'Nul',
  '2':       'Extérieur',
  '1X':      'Domicile ou nul',
  'X2':      'Extérieur ou nul',
  '12':      'Pas de nul',
  'BTTS Oui':'BTTS · Oui',
  'BTTS Non':'BTTS · Non',
  '+1.5':    'Plus de 1.5 buts',
  '-1.5':    'Moins de 1.5 buts',
  '+2.5':    'Plus de 2.5 buts',
  '-2.5':    'Moins de 2.5 buts',
};

// ============================================================ RENDER

function renderHeader(meta) {
  document.getElementById('last-update').textContent = fmtDateTime(meta.generated_at);

  // Countdown
  const target = new Date(meta.next_update_at);
  const update = () => {
    document.getElementById('countdown').textContent = fmtCountdown(target);
  };
  update();
  setInterval(update, 30000);

  // Date du jour
  document.getElementById('current-date').textContent =
    fmtDateLong(new Date().toISOString());

  // Modèle et entraînement (footer)
  document.getElementById('model-name').textContent = meta.model || '—';
  if (meta.training) {
    document.getElementById('training-info').textContent =
      `${meta.training.n_matches} matchs · ${meta.training.date_range}`;
  }
  if (meta.params) {
    document.getElementById('param-home-adv').textContent = meta.params.dixon_coles_home_adv ?? '—';
    document.getElementById('param-rho').textContent      = meta.params.dixon_coles_rho ?? '—';
  }
}

function renderError(message) {
  document.getElementById('combo-body').innerHTML = `
    <div class="state state--error">
      <span class="state__icon">!</span>
      <h3 class="state__title">Erreur de chargement</h3>
      <p class="state__body">${escapeHtml(message)}</p>
    </div>
  `;
}

function renderNoCombo(reason, comboLabel = "Aujourd'hui") {
  return `
    <div class="state">
      <span class="state__icon">∅</span>
      <h3 class="state__title">Pas de combo ${comboLabel.toLowerCase() === "aujourd'hui" ? "aujourd'hui" : `pour ${comboLabel}`}</h3>
      <p class="state__body">${escapeHtml(reason || "Aucune sélection ne dépasse le seuil de confiance requis.")}</p>
    </div>
  `;
}

function renderCombo(day) {
  if (!day) {
    return renderNoCombo("Aucun match programmé dans les 5 ligues majeures.");
  }
  if (!day.combo || !day.combo.available) {
    return renderNoCombo(day.combo?.reason || "Moins de 4 sélections au-dessus du seuil de confiance.");
  }

  const c = day.combo;
  const meanProb = c.picks.reduce((s, p) => s + p.probability, 0) / c.picks.length;

  const statsHtml = `
    <div class="combo-stats">
      <div class="stat">
        <div class="stat__label">Probabilité combinée</div>
        <div class="stat__value stat__value--accent">${fmtPct(c.joint_probability)}</div>
        <div class="stat__sub">P(X₁ ∩ X₂ ∩ X₃ ∩ X₄)</div>
      </div>
      <div class="stat">
        <div class="stat__label">Cote combinée (juste)</div>
        <div class="stat__value">${fmtOdds(c.fair_combined_odds)}</div>
        <div class="stat__sub">Sans marge bookmaker</div>
      </div>
      <div class="stat">
        <div class="stat__label">Confiance moyenne</div>
        <div class="stat__value">${fmtPct(meanProb)}</div>
        <div class="stat__sub">Sur les 4 sélections</div>
      </div>
      <div class="stat">
        <div class="stat__label">Matchs analysés</div>
        <div class="stat__value">${day.fixtures_count}</div>
        <div class="stat__sub">Dans les 5 ligues ce jour</div>
      </div>
    </div>
  `;

  const picksHtml = c.picks.map((p, i) => {
    // Retrouver les détails du match (kickoff) dans day.fixtures
    const matchFixture = day.fixtures.find(f =>
      `${f.home} vs ${f.away}` === p.match
    );
    const kickoff = matchFixture?.kickoff;
    return `
      <article class="pick" style="--prob:${(p.probability * 100).toFixed(1)}%">
        <div class="pick__num">${String(i + 1).padStart(2, '0')}</div>
        <div class="pick__body">
          <div class="pick__head">
            <span class="pick__league">${escapeHtml(p.league_name)}</span>
            ${kickoff ? `<span class="pick__kickoff">Coup d'envoi · ${fmtTime(kickoff)}</span>` : ''}
          </div>
          <h3 class="pick__match">${escapeHtml(p.match)}</h3>
          <div class="pick__selection">
            <span class="pick__market">${escapeHtml(p.market)}</span>
            <span class="pick__desc">${escapeHtml(p.selection)}</span>
          </div>
        </div>
        <aside class="pick__sidebar">
          <div class="pick-stat">
            <span class="pick-stat__label">Probabilité</span>
            <span class="pick-stat__value pick-stat__value--accent">${fmtPct(p.probability)}</span>
          </div>
          <div class="prob-bar"><div class="prob-bar__fill" data-prob="${p.probability}"></div></div>
          <div class="pick-stat">
            <span class="pick-stat__label">Cote juste</span>
            <span class="pick-stat__value">${fmtOdds(p.fair_odds)}</span>
          </div>
          <div class="pick-stat">
            <span class="pick-stat__label">xG</span>
            <span class="pick-stat__value">${p.xg}</span>
          </div>
        </aside>
      </article>
    `;
  }).join('');

  return statsHtml + `<div class="picks">${picksHtml}</div>`;
}

function renderFixturesTable(day) {
  if (!day || !day.fixtures.length) {
    return `<div class="state"><span class="state__icon">∅</span>
      <h3 class="state__title">Aucun match programmé</h3>
      <p class="state__body">Les 5 ligues majeures ne jouent pas ce jour.</p></div>`;
  }

  const comboMatches = new Set(
    (day.combo?.picks || []).map(p => p.match)
  );

  const rows = day.fixtures
    .slice()
    .sort((a, b) => (a.kickoff || '').localeCompare(b.kickoff || ''))
    .map(f => {
      const matchStr = `${f.home} vs ${f.away}`;
      const inCombo = comboMatches.has(matchStr);
      return `
        <tr class="${inCombo ? 'in-combo' : ''}">
          <td class="time-cell">${fmtTime(f.kickoff)}</td>
          <td class="league-cell">${escapeHtml(f.league_name)}</td>
          <td class="match-cell">${escapeHtml(matchStr)}</td>
          <td class="market-cell">${escapeHtml(f.best_pick.market)}</td>
          <td class="prob-cell">${fmtPct(f.best_pick.probability)}</td>
          <td class="odds-cell">${fmtOdds(f.best_pick.fair_odds)}</td>
        </tr>
      `;
    }).join('');

  return `
    <table class="fixtures-table">
      <thead>
        <tr>
          <th>Heure</th><th>Ligue</th><th>Match</th>
          <th>Meilleur pari</th><th>Probabilité</th><th>Cote</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderUpcoming(days) {
  // Days other than today
  const upcoming = days.filter(d => !d.is_today);
  if (!upcoming.length) return '';

  return upcoming.map(d => `
    <div class="day-block">
      <div class="day-block__head">
        <h3 class="day-block__date">${escapeHtml(fmtDateLong(d.date))}</h3>
        <span class="day-block__count">${d.fixtures_count} matchs</span>
      </div>
      ${d.combo?.available ? renderCombo(d) : renderNoCombo(d.combo?.reason, fmtDateLong(d.date))}
    </div>
  `).join('');
}

// ============================================================ MAIN

async function load() {
  let data;
  try {
    const r = await fetch(DATA_URL, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    data = await r.json();
  } catch (e) {
    try {
      const r = await fetch(FALLBACK_DATA_URL, { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      data = await r.json();
    } catch (e2) {
      renderError(`Impossible de charger les prédictions (${e.message}).`);
      return;
    }
  }

  renderHeader(data.meta || {});

  if (data.meta?.status === 'error') {
    renderError(data.meta.error_message || 'Erreur inconnue côté serveur.');
    return;
  }

  const days = data.days || [];
  const today = days.find(d => d.is_today);

  // --- Combo section
  document.getElementById('combo-body').innerHTML = renderCombo(today);

  // --- Fixtures section (today + upcoming days)
  let fixturesHtml = '';
  if (today) {
    fixturesHtml += `
      <div class="day-block">
        <div class="day-block__head">
          <h3 class="day-block__date">Aujourd'hui</h3>
          <span class="day-block__count">${today.fixtures_count} matchs</span>
        </div>
        ${renderFixturesTable(today)}
      </div>
    `;
  }
  fixturesHtml += days.filter(d => !d.is_today).map(d => `
    <div class="day-block">
      <div class="day-block__head">
        <h3 class="day-block__date">${escapeHtml(fmtDateLong(d.date))}</h3>
        <span class="day-block__count">${d.fixtures_count} matchs · ${d.combo?.available ? 'Combo disponible' : 'Pas de combo'}</span>
      </div>
      ${renderFixturesTable(d)}
    </div>
  `).join('');
  if (!fixturesHtml) {
    fixturesHtml = `<div class="state"><span class="state__icon">∅</span>
      <h3 class="state__title">Aucun match programmé</h3>
      <p class="state__body">Les 5 ligues majeures ne jouent pas dans la fenêtre actuelle.</p></div>`;
  }
  document.getElementById('fixtures-body').innerHTML = fixturesHtml;

  // Animate prob bars after a tick
  requestAnimationFrame(() => {
    document.querySelectorAll('.prob-bar__fill').forEach(el => {
      const p = parseFloat(el.dataset.prob);
      el.style.width = `${(p * 100).toFixed(1)}%`;
    });
  });
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

document.addEventListener('DOMContentLoaded', load);
