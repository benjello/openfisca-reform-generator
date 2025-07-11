# openfisca-reform-generator

Générateur Shiny Python d’une réforme OpenFisca, packagé avec Shinylive pour être déployé sur GitHub Pages.

## Installation locale

```bash
git clone https://github.com/benjello/openfisca-reform-generator.git
cd openfisca-reform-generator/app
uv run shinylive export app docs
uv run python -m http.server --directory docs --bind localhost 8008
```

## Déploiement sur GitHub Pages

Ce dépôt inclut un workflow GitHub Actions pour exporter l'app statique avec shinylive et la publier automatiquement.
