// Extract threads from current page and store in global accumulator
// Called after each page navigation
(function() {
  if (!window.__gThreads) window.__gThreads = [];
  if (!window.__gSeen) window.__gSeen = new Set();

  const rows = document.querySelectorAll('.yhgbKd');
  let newCount = 0;

  rows.forEach(row => {
    const link = row.querySelector('a.ZLl54[href*="/c/"]');
    if (!link) return;
    const href = link.getAttribute('href');
    const threadId = href.match(/\/c\/([^/?]+)/)?.[1];
    if (!threadId || window.__gSeen.has(threadId)) return;
    window.__gSeen.add(threadId);
    newCount++;

    window.__gThreads.push({
      thread_id: threadId,
      subject: row.querySelector('.t17a0d')?.textContent?.trim() || '',
      url: new URL(href, window.location.origin).href,
      date: row.querySelector('.tRlaM')?.textContent?.trim() || '',
      participants: row.querySelector('.VWSb7b a.ZLl54')?.textContent?.trim() || ''
    });
  });

  // Check for next page
  const btn = document.querySelector('[aria-label="Next page"]');
  const hasNext = btn && btn.getAttribute('aria-disabled') !== 'true';

  // Page count indicator (e.g., "31–60 of 2232")
  const pageInfo = document.body.innerText.match(/(\d+)[–-](\d+)\s+of\s+(\d+)/);
  const rangeEnd = pageInfo ? parseInt(pageInfo[2]) : 0;
  const total = pageInfo ? parseInt(pageInfo[3]) : 0;

  return JSON.stringify({
    collected: window.__gThreads.length,
    new_on_page: newCount,
    has_next: hasNext,
    range_end: rangeEnd,
    total: total
  });
})()
