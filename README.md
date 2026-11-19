# Mapa kriminálních zpráv Japonska 日本犯罪ニュースマップ

Statická stránka na GitHub Pages + GitHub Actions, která každých ~15 minut stáhne RSS zpravodajství,
vyfiltruje kriminálky a přiřadí je k prefekturám. Žádný server není potřeba.

## Nasazení
1. Vytvořte nový repozitář na GitHubu a nahrajte všechny soubory.
2. **Settings → Pages → Source: Deploy from a branch → `main` / `/docs`**.
3. **Settings → Actions → General → Workflow permissions → Read and write permissions**.
4. **Actions → Update news → Run workflow** (první naplnění dat). Dál běží samo.

Lokálně: `python scripts/fetch_news.py && cd docs && python -m http.server`

## Úpravy
- Zdroje: seznam `FEEDS` ve `scripts/fetch_news.py` (ověřte, že URL kanálů fungují).
- Klíčová slova a města: `CATEGORIES` a `CITIES` ve stejném souboru.
- Zobrazují se jen titulek, krátký výtah a odkaz na originál (kvůli autorským právům).
- Mapa prefektur se načítá z `dataofjapan/land` (GeoJSON).
