---
name: wikipedia
description: Navigating Wikipedia search to open an article and read infobox facts (height, dates, etc). Load for tasks that search Wikipedia for an article.
type: app-map
apps: [wikipedia]
status: candidate
wins: 1
losses: 0
last_verified: 2026-09-19
---
1. On wiki/Main_Page, type the article title into the "Search Wikipedia" box.
2. Submitting via the search button click can TimeoutError/fail to register (unconfirmed cause), but the search often still navigates to the article page (wiki/{Article_Title}) anyway — check the resulting url/page before retrying the click.
3. The article's infobox (top right) usually contains the key facts (dates, measurements, etc) without needing to scroll/read body text.
4. TRAP: infobox may list multiple values for one field (e.g. multiple "height" entries: architectural, tip, top floor). Note which sub-label is relevant to the task, or report all if ambiguous.

## Lesson: finishing after a failed click
If a click action errors (e.g. TimeoutError) but the following step shows the target page already loaded, the action likely succeeded despite the error — do not stop before extracting the requested data. Only call finish after the required facts have actually been read and stated, not just because the page opened.
