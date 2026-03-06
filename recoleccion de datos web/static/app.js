/**
 * Lead Scanner — Client-side JavaScript
 * Handles form submission, SSE progress, table rendering, filtering & export.
 */

// ── State ────────────────────────────────────────────────────────────────────
let allResults = [];
let filteredResults = [];
let sortColumn = null;
let sortAsc = true;
let minReviewsFilter = false;
let eventSource = null;

// ── DOM refs ─────────────────────────────────────────────────────────────────
const form            = document.getElementById('scan-form');
const btnScan         = document.getElementById('btn-scan');
const btnScanText     = document.getElementById('btn-scan-text');
const inputRubro      = document.getElementById('input-rubro');
const inputDepto      = document.getElementById('input-depto');
const chkHeadless     = document.getElementById('chk-headless');

const progressSection = document.getElementById('progress-section');
const progressFill    = document.getElementById('progress-fill');
const progressPct     = document.getElementById('progress-pct');
const progressText    = document.getElementById('progress-text');

const resultsSection  = document.getElementById('results-section');
const statTotal       = document.getElementById('stat-total');
const statDisplayed   = document.getElementById('stat-displayed');
const filterInput     = document.getElementById('filter-input');
const filterToggle    = document.getElementById('filter-toggle');
const tableBody       = document.getElementById('table-body');
const tableHeaders    = document.querySelectorAll('th[data-col]');

const btnExportCsv    = document.getElementById('btn-export-csv');
const btnExportXlsx   = document.getElementById('btn-export-xlsx');

const toastContainer  = document.getElementById('toast-container');

// ── Form Submit ──────────────────────────────────────────────────────────────
form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const rubro = inputRubro.value.trim();
  const depto = inputDepto.value.trim();
  if (!rubro || !depto) {
    showToast('Completá ambos campos para iniciar.', 'error');
    return;
  }

  // Reset state
  allResults = [];
  filteredResults = [];
  btnScan.disabled = true;
  btnScanText.textContent = 'Escaneando…';
  resultsSection.classList.remove('active');
  progressSection.classList.add('active');
  updateProgress(0, 'Conectando…');

  // Start SSE connection BEFORE sending the scan request so we don't miss events
  connectSSE();

  try {
    const resp = await fetch('/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rubro,
        departamento: depto,
        headless: chkHeadless.checked,
      }),
    });

    const data = await resp.json();
    if (!resp.ok) {
      showToast(data.error || 'Error al iniciar el escaneo.', 'error');
      resetScanBtn();
      progressSection.classList.remove('active');
    }
  } catch (err) {
    showToast('No se pudo conectar al servidor.', 'error');
    resetScanBtn();
    progressSection.classList.remove('active');
  }
});

// ── SSE Connection ───────────────────────────────────────────────────────────
function connectSSE() {
  if (eventSource) eventSource.close();

  eventSource = new EventSource('/progress');

  eventSource.addEventListener('status', (e) => {
    const d = JSON.parse(e.data);
    updateProgress(d.progress || 0, d.message || '');
  });

  eventSource.addEventListener('done', (e) => {
    const d = JSON.parse(e.data);
    allResults = d.results || [];
    applySortAndFilter();
    renderResults();
    showResultsSection();
    resetScanBtn();
    updateProgress(100, '¡Completado!');

    if (allResults.length > 0) {
      showToast(`Se encontraron ${allResults.length} prospectos.`, 'success');
    } else {
      showToast('No se encontraron prospectos para esta búsqueda.', 'error');
    }

    if (eventSource) eventSource.close();
    eventSource = null;
  });

  eventSource.addEventListener('error_event', (e) => {
    const d = JSON.parse(e.data);
    showToast(d.message || 'Error durante el escaneo.', 'error');
    resetScanBtn();
    if (eventSource) eventSource.close();
    eventSource = null;
  });

  eventSource.onerror = () => {
    // SSE connection lost — could be normal after scan finishes
  };
}

// ── Progress ─────────────────────────────────────────────────────────────────
function updateProgress(pct, text) {
  progressFill.style.width = pct + '%';
  progressPct.textContent = pct + '%';
  progressText.textContent = text;
}

// ── Results Rendering ────────────────────────────────────────────────────────
function renderResults() {
  tableBody.innerHTML = '';

  if (filteredResults.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; padding: 40px; color: var(--text-muted);">
          No se encontraron resultados con los filtros actuales.
        </td>
      </tr>`;
    statDisplayed.textContent = '0';
    return;
  }

  statDisplayed.textContent = filteredResults.length;

  filteredResults.forEach((lead) => {
    const tr = document.createElement('tr');

    const reviews = parseInt(lead.Reseñas) || 0;
    const reviewsClass = reviews >= 50 ? 'reviews-cell high' : 'reviews-cell';

    let situacionClass = 'situacion-cell';
    if (lead.Situacion.toLowerCase().includes('sin presencia')) {
      situacionClass += ' sin-web';
    } else {
      situacionClass += ' solo-redes';
    }

    tr.innerHTML = `
      <td><strong>${escapeHTML(lead.Nombre)}</strong></td>
      <td>${escapeHTML(lead.Telefono)}</td>
      <td class="stars-cell">⭐ ${escapeHTML(String(lead.Estrellas))}</td>
      <td class="${reviewsClass}">${reviews.toLocaleString()}</td>
      <td><span class="${situacionClass}">${escapeHTML(lead.Situacion)}</span></td>
    `;
    tableBody.appendChild(tr);
  });
}

function showResultsSection() {
  resultsSection.classList.add('active');
  statTotal.textContent = allResults.length;
}

// ── Sorting ──────────────────────────────────────────────────────────────────
tableHeaders.forEach((th) => {
  th.addEventListener('click', () => {
    const col = th.dataset.col;

    if (sortColumn === col) {
      sortAsc = !sortAsc;
    } else {
      sortColumn = col;
      sortAsc = true;
    }

    // Update sort icons
    tableHeaders.forEach((h) => {
      h.classList.remove('sorted');
      h.querySelector('.sort-icon').textContent = '↕';
    });
    th.classList.add('sorted');
    th.querySelector('.sort-icon').textContent = sortAsc ? '↑' : '↓';

    applySortAndFilter();
    renderResults();
  });
});

// ── Filtering ────────────────────────────────────────────────────────────────
filterInput.addEventListener('input', () => {
  applySortAndFilter();
  renderResults();
});

filterToggle.addEventListener('click', () => {
  minReviewsFilter = !minReviewsFilter;
  filterToggle.classList.toggle('active', minReviewsFilter);
  applySortAndFilter();
  renderResults();
});

function applySortAndFilter() {
  let data = [...allResults];

  // Text filter
  const query = filterInput.value.toLowerCase().trim();
  if (query) {
    data = data.filter((d) =>
      d.Nombre.toLowerCase().includes(query) ||
      d.Telefono.toLowerCase().includes(query) ||
      d.Situacion.toLowerCase().includes(query)
    );
  }

  // Minimum reviews filter
  if (minReviewsFilter) {
    data = data.filter((d) => (parseInt(d.Reseñas) || 0) >= 50);
  }

  // Sort
  if (sortColumn) {
    data.sort((a, b) => {
      let va = a[sortColumn];
      let vb = b[sortColumn];

      if (sortColumn === 'Reseñas' || sortColumn === 'Estrellas') {
        va = parseFloat(va) || 0;
        vb = parseFloat(vb) || 0;
      } else {
        va = String(va).toLowerCase();
        vb = String(vb).toLowerCase();
      }

      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
  }

  filteredResults = data;
}

// ── Export ────────────────────────────────────────────────────────────────────
btnExportCsv.addEventListener('click', () => exportData('csv'));
btnExportXlsx.addEventListener('click', () => exportData('xlsx'));

function exportData(fmt) {
  if (allResults.length === 0) {
    showToast('No hay datos para exportar.', 'error');
    return;
  }
  const minReviews = minReviewsFilter ? 50 : 0;
  window.location.href = `/export/${fmt}?min_reviews=${minReviews}`;
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function resetScanBtn() {
  btnScan.disabled = false;
  btnScanText.textContent = 'Iniciar Escaneo';
}

function escapeHTML(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    if (toast.parentNode) toast.remove();
  }, 4000);
}
