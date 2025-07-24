from shiny import App

from openfisca_country_template import CountryTaxBenefitSystem


from parameter import SimpleParameterTracker
from ui import app_ui
from server import server_logic

param_tracker = SimpleParameterTracker()

# Configuration
period = 2017

# Initialisation
tbs = CountryTaxBenefitSystem()


# Interface utilisateur
ui = app_ui(tbs, param_tracker)

# Serveur
def server(input, output, session):
    server_logic(input, output, session, param_tracker, tbs, period)

# Créer l'application
app = App(ui, server)

if __name__ == "__main__":
    app.run()
