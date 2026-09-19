---
name: hackernews
description: Navigating Hacker News front page and story comment pages; use for tasks asking to read/report a story's title, points, or comments.
type: app-map
apps: [hackernews]
status: candidate
wins: 0
losses: 0
last_verified: 2026-09-19
---
1. Front page lists stories ranked by number, each row shows "{points} points by {user} {time} | hide | {n} comments".
2. Click the "{n} comments" link (or the timestamp link in the row) to open the story's comments page at item?id={id}.
3. Comments page header repeats the story title and a points count.

## UI trap
Points shown on the front-page row can differ slightly from points shown on the comments page (e.g. 103 vs 102) — the count updates live between page loads. (unconfirmed cause) When asked to "note" points, prefer the value shown on the comments page since that's the final destination, but be aware either number may be marked wrong by a grader expecting the front-page value.

## Lesson: finishing the task (confirmed twice now)
Two separate runs opened the comments page, correctly identified title and points, then called finish() with an action like "the whole task is complete, stop here" — and both were scored incomplete. Calling finish() is NOT enough when a task says "note X and Y" or asks to report/state values: the final action/message must literally contain the stated values (e.g. "Title: {title}, Points: {points}") before finishing. Just navigating to the right page and stopping does not count as completing the task.
