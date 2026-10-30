# Výsledky ověření referenční verze

- Datum: 2026-10-30.
- Základ forku: 01df3fc8, integrační verze referenčního přenosu 2026.10.0.post1.
- Před přenosem: `uv run pytest -q --tb=short` — 431 passed, 83.96 s.
- První cílená sada po přenosu: 118 passed, 28.77 s.
- Test načtení uložených refresh_dpids: 2 passed, 47 deselected, 0.20 s.
- Ruff check, import order a format check prošly.
- Yamllint: úspěšný návrat; již existující upozornění comments-indentation v devices/marpou_ceiling_lamp_ledlight.yaml:3. Tento profil nebyl změněn.
- Kompletní sada po přenosu: 453 passed, 83.27 s. Dva následně doplněné parametrizované testy zachování nastavení prošly samostatně; celkem ověřeno 455 případů.
- Fyzický test a přechod HACS: neprovedeno.

Podklady z instalace a diagnostiky jsou uložené mimo Git a nejsou součástí vydání. Testy používají pouze smyšlené identifikátory a adresy.
