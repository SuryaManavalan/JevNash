#!/usr/bin/env bash
# Back-to-back demo on one dashboard (http://localhost:8765). Each act frees the port for the next;
# the dashboard page reconnects by itself.
R="uv run python -u -m jevnash.run --dashboard --no-hold --headed --pace 0.8 --usd 1"
echo "ACT 1: cross-app refund under chaos (helpdesk -> billing -> helpdesk)"
$R --env suite --chaos --family refund --episodes 1 --seed 101
echo "ACT 2: restock a warehouse from a stock table (chaos)"
$R --env suite --chaos --family reorder --episodes 1 --seed 102
echo "ACT 3: live web - MDN search inside a shadow-DOM component"
$R --env web_open --v2 --episodes 1 --run-dir runs/show_mdn --url https://developer.mozilla.org/en-US/ \
   --task 'Use the site search to find "flatMap" and open the reference page for Array.prototype.flatMap. Note which value it returns.'
echo "ACT 4: live web - Wikipedia fact lookup"
$R --env web_open --v2 --episodes 1 --run-dir runs/show_wiki --url https://en.wikipedia.org/wiki/Main_Page \
   --task 'Use the search box to open the encyclopedia article on the "Golden Gate Bridge" and note its total length and opening year.'
echo "ACT 5: link race across Wikipedia with menus of 250-1500 links"
$R --env web_race --episodes 1 --seed 9
echo "SHOWCASE DONE"
