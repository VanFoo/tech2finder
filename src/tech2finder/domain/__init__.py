"""Plain dataclasses that cross the boundary out of the domain.

ADR-0012 constrains this project so a later swap from server-rendered HTMX to
an SPA stays cheap: the cost model and scan-result layer return plain
dataclasses, and templates only render them. No domain arithmetic in a
template, no database rows reaching a view.

Types that the scan result is built from belong here. `tech2finder.web.status`
shows the shape in miniature: a frozen dataclass assembled by a function, with
any derivation done as a property rather than in the template.
"""
