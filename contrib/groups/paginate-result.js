// Retrieve collected threads from global accumulator
JSON.stringify({
  thread_count: (window.__gThreads || []).length,
  threads: window.__gThreads || []
}, null, 2)
