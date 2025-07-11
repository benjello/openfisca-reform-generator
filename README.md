# openfisca-reform-generator

Générateur Shiny Python d’une réforme OpenFisca, packagé avec Shinylive pour être déployé sur GitHub Pages.

## Installation locale

```bash
git clone https://github.com/benjello/openfisca-reform-generator.git
cd openfisca-reform-generator
uv run streamlit run app/streamlit_app.py --server.port 8502 --server.address 0.0.0.0
```

Ouvrir http://127.0.0.1:8502/

## Déploiement sur GitHub Pages

Ce dépôt inclut un workflow GitHub Actions pour exporter l'app statique avec shinylive et la publier automatiquement.
