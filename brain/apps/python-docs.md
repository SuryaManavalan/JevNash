---
name: python-docs
description: Navigating docs.python.org - searching for a module/topic and opening its library page. Use for tasks about finding Python API/module info.
type: app-map
apps: [python-docs]
status: candidate
---
1. On the docs homepage, use "Quick search" input (type {query}, e.g. module name).
2. Click "Go" to submit search.
3. Results page lists matches; click the entry matching "{query} (Python module, in {query} — ...)" to open the module's library page.
4. Module pages often have a "high-level APIs" or similar summary section near the top listing key functions before deeper API reference - check there first for "first/top API" style questions.

Verify: URL becomes /3/library/{module}.html#module-{module} and page content matches the queried module.
