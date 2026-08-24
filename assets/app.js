"use strict";

const formatPercent = (count, total) => `${((count / total) * 100).toFixed(1)}%`;

const escapeHtml = (value) =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const renderStats = (stats) => {
  const grid = document.querySelector("#benchmark-stats");
  grid.innerHTML = stats
    .map(
      (stat) => `
        <div class="stat-card">
          <span class="stat-value">${escapeHtml(stat.value)}</span>
          <span class="stat-label">${escapeHtml(stat.label)}</span>
          <span class="stat-note">${escapeHtml(stat.note)}</span>
        </div>`,
    )
    .join("");
};

const renderLeaderboard = (payload) => {
  const body = document.querySelector("#leaderboard-body");
  body.innerHTML = payload.results
    .map((row, index) => {
      const paperUrl = row.links.paper;
      const benchmarkCells = payload.benchmark_slices
        .map((benchmark) => {
          const result = row.by_benchmark[benchmark.id];
          return `
            <td class="number slice-metric" title="${result.root_exact_correct} / ${result.n} exact">
              ${formatPercent(result.root_exact_correct, result.n)}
            </td>`;
        })
        .join("");
      return `
        <tr class="${index === 0 ? "leader" : ""}">
          <td><span class="rank">${index + 1}</span></td>
          <td class="method-cell">
            <div class="method-line">
              <span class="method-name">${escapeHtml(row.display_name)}</span>
              <a class="method-citation" href="${escapeHtml(paperUrl)}" aria-label="Read the ${escapeHtml(row.citation_label)} paper">[${escapeHtml(row.citation_label)}]</a>
            </div>
            <span class="model-backbone">(Equipped with ${escapeHtml(row.model)})</span>
            <span class="sample-count">n = ${row.n.toLocaleString("en-US")}</span>
          </td>
          <td class="number primary-metric"><strong>${formatPercent(row.root_exact_correct, row.n)}</strong></td>
          ${benchmarkCells}
        </tr>`;
    })
    .join("");
};

const renderFailure = () => {
  const body = document.querySelector("#leaderboard-body");
  body.innerHTML = '<tr><td colspan="8" class="loading error">Leaderboard data could not be loaded.</td></tr>';
};

const loadData = async () => {
  try {
    const siteRequest = fetch("data/site.json");
    const leaderboardRequest = fetch("data/leaderboard.json");
    const [siteResponse, leaderboardResponse] = await Promise.all([
      siteRequest,
      leaderboardRequest,
    ]);
    if (!siteResponse.ok || !leaderboardResponse.ok) {
      throw new Error("A data request failed");
    }
    renderStats((await siteResponse.json()).stats);
    renderLeaderboard(await leaderboardResponse.json());
  } catch (error) {
    renderFailure();
    console.error(error);
  }
};

const configureCitationCopy = () => {
  const button = document.querySelector("#copy-citation");
  const citation = document.querySelector("#citation-code");
  const status = document.querySelector("#copy-status");
  if (!button || !citation || !status) return;

  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(citation.textContent.trim());
      button.textContent = "Copied";
      status.textContent = "Citation copied to clipboard.";
      window.setTimeout(() => {
        button.textContent = "Copy citation";
      }, 1800);
    } catch (error) {
      status.textContent = "Copy failed. Select the citation text manually.";
      console.error(error);
    }
  });
};

configureCitationCopy();
loadData();
