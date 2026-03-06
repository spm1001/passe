// Extract thread list from Google Groups conversation list page
// DOM structure per row:
//   div.VWSb7b → a.ZLl54 (participants), div.tRlaM (date)
//   div.Pa1AFb → a.ZLl54.Dysyo → div.t17a0d (SUBJECT), div.WzoK (preview)
const rows = document.querySelectorAll('.yhgbKd');
const threads = [];

rows.forEach(row => {
  const link = row.querySelector('a.ZLl54[href*="/c/"]');
  if (!link) return;
  const href = link.getAttribute('href');
  const threadId = href.match(/\/c\/([^/?]+)/)?.[1];
  if (!threadId) return;

  // Subject from div.t17a0d (clean, no preview text)
  const subjectEl = row.querySelector('.t17a0d');
  const subject = subjectEl ? subjectEl.textContent.trim() : '';

  // Date from div.tRlaM
  const dateEl = row.querySelector('.tRlaM');
  const date = dateEl ? dateEl.textContent.trim() : '';

  // Participants from the first a.ZLl54
  const participantsEl = row.querySelector('.VWSb7b a.ZLl54');
  const participants = participantsEl ? participantsEl.textContent.trim() : '';

  const url = new URL(href, window.location.origin).href;

  threads.push({
    thread_id: threadId,
    subject: subject,
    url: url,
    date: date,
    participants: participants
  });
});

// Check "Next page" button
const nextBtn = document.querySelector('[aria-label="Next page"]');
const hasNext = nextBtn && !nextBtn.hasAttribute('disabled')
  && nextBtn.getAttribute('aria-disabled') !== 'true';

JSON.stringify({
  thread_count: threads.length,
  has_next_page: !!hasNext,
  page_url: window.location.href,
  threads: threads
}, null, 2);
