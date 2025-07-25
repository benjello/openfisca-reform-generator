from shiny import App

from openfisca_nouvelle_caledonie import CountryTaxBenefitSystem


from parameter import SimpleParameterTracker
from ui import app_ui
from server import server_logic

param_tracker = SimpleParameterTracker()

# Configuration
period = 2023

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
