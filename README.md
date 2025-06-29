# openfisca-reform-generator

Générateur Shiny Python d’une réforme OpenFisca, packagé avec Shinylive pour être déployé sur GitHub Pages.

## Installation locale

```bash
git clone https://github.com/benjello/openfisca-reform-generator.git
cd openfisca-reform-generator/app
pip install -r requirements.txt
shiny run app.py
```

## Déploiement sur GitHub Pages

Ce dépôt inclut un workflow GitHub Actions pour exporter l'app statique avec shinylive et la publier automatiquement.
