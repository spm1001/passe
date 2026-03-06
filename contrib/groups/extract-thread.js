// v4: Precise extraction with correct subject and clean body isolation
const sections = document.querySelectorAll('section.BkrUxb');

// Thread subject from h1 (h2 is the group name)
const subject = document.querySelector('h1')?.textContent?.trim()
  || document.title.replace(/ - Google Groups$/, '').trim();

// Thread URL for deduplication
const threadUrl = window.location.href;

const messages = [];
sections.forEach((section, i) => {
  const name = section.querySelector('h3')?.textContent?.trim() || '';

  // Date from the ELCJ4d class
  const dateEl = section.querySelector('.ELCJ4d');
  let date = dateEl ? dateEl.textContent.trim() : '';
  // Strip dd/mm/yyyy duplicate and relative time suffixes
  date = date.replace(/\d{2}\/\d{2}\/\d{4}.*/, '').trim();
  date = date.replace(/\s*\([\d\w\s]+ago\).*/, '').trim();

  // Body from jsname=yjbGtf (the message content container)
  const bodyEl = section.querySelector('[jsname="yjbGtf"]');
  let body = bodyEl ? bodyEl.innerText.trim() : '';

  if (name || body) {
    messages.push({ index: i, from: name, date: date, body: body });
  }
});

JSON.stringify({ subject, thread_url: threadUrl, message_count: messages.length, messages }, null, 2);
