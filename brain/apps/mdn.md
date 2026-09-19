---
name: mdn
description: MDN Web Docs navigation. Covers finding the site search box and reaching reference pages. Load for tasks that search MDN or read API reference pages.
type: app-map
apps: [mdn]
status: candidate
wins: 1
losses: 0
last_verified: 2026-09-19
---

## Search trap
The nav bar has items like "JavaScript", "Tools", "All", "About" and a "Skip to main content" link,
but repeatedly clicking these does NOT open a search input — it just navigates category pages and
loops (observed: 20+ clicks cycling through JavaScript/Tools/All/About/MDN logo with no progress,
task failed, score 0).

There is a dedicated search input/icon (magnifying glass) distinct from all nav dropdown items and
from "Skip to search" link — it must be clicked directly, not reached via the JavaScript/Tools/All
category menus. (unconfirmed exact selector/location — next run should look specifically for a
search icon or box near the top-right of the header, not the category nav links.)

## Lesson
If several clicks on nav items produce no new UI element (input box) appearing, stop repeating the
same nav item clicks — try scrolling/looking for a distinct search icon element instead, or use
browser find-in-page as fallback is not applicable (site search needed for reference lookup).

## Reference pages
Not yet reached in any run. Once search works, path should be:
Reference page = JavaScript > Reference > {Global_Object} > {method}, containing a "Return value"
section describing what the method returns.
