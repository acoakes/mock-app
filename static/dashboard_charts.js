// Dashboard anomaly charts renderer.
//
// Reads the chart datasets inlined by the Flask route in a
// <script type="application/json" id="dashboard-chart-data"> tag (NO HTTP
// endpoint) and renders three Chart.js charts using the vendored
// chart.min.js (no CDN):
//   #chart-by-vendor   - bar       (anomalies per vendor)
//   #chart-by-severity - doughnut  (anomalies per HIGH/MEDIUM/LOW)
//   #chart-over-time   - line      (anomalies per window_start)
// Each dataset has the shape { labels: [...], values: [...] }.
// Fails safe: no-ops if Chart.js or the data tag is absent.
(function () {
  'use strict';

  function parsePayload() {
    var tag = document.getElementById('dashboard-chart-data');
    if (!tag) {
      return null;
    }
    try {
      return JSON.parse(tag.textContent || tag.innerText || '{}');
    } catch (err) {
      return null;
    }
  }

  var PALETTE = ['#2563eb', '#7c3aed', '#1b9e4b', '#e0a73a', '#e06a6a', '#5bc0de'];
  var SEVERITY_COLOURS = {
    HIGH: '#c0392b',
    MEDIUM: '#e67e22',
    LOW: '#27ae60'
  };

  function makeBar(ctx, ds) {
    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ds.labels,
        datasets: [{
          label: 'Anomalies',
          data: ds.values,
          backgroundColor: ds.labels.map(function (_, i) {
            return PALETTE[i % PALETTE.length];
          })
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
      }
    });
  }

  function makeDoughnut(ctx, ds) {
    return new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ds.labels,
        datasets: [{
          data: ds.values,
          backgroundColor: ds.labels.map(function (label, i) {
            return SEVERITY_COLOURS[label] || PALETTE[i % PALETTE.length];
          })
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'bottom' } }
      }
    });
  }

  function makeLine(ctx, ds) {
    return new Chart(ctx, {
      type: 'line',
      data: {
        labels: ds.labels,
        datasets: [{
          label: 'Anomalies',
          data: ds.values,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37,99,235,0.15)',
          fill: true,
          tension: 0.25,
          pointRadius: 3
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
      }
    });
  }

  function canvasCtx(id) {
    var el = document.getElementById(id);
    return el ? el.getContext('2d') : null;
  }

  function render() {
    if (typeof Chart === 'undefined') {
      return;
    }
    var data = parsePayload();
    if (!data) {
      return;
    }

    var vendorCtx = canvasCtx('chart-by-vendor');
    if (vendorCtx && data.by_vendor) {
      makeBar(vendorCtx, data.by_vendor);
    }
    var sevCtx = canvasCtx('chart-by-severity');
    if (sevCtx && data.by_severity) {
      makeDoughnut(sevCtx, data.by_severity);
    }
    var timeCtx = canvasCtx('chart-over-time');
    if (timeCtx && data.over_time) {
      makeLine(timeCtx, data.over_time);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
