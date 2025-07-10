from io import StringIO
import tempfile
import importlib.util
import os

from shiny import App, ui, render, reactive
from typing import Dict, Any, Optional, Set


from openfisca_core.parameters import ParameterScale
from openfisca_country_template import CountryTaxBenefitSystem
from openfisca_survey_manager.tests.test_scenario import create_randomly_initialized_survey_scenario

tbs = CountryTaxBenefitSystem()
param_root = tbs.parameters
period = 2017


# Tracker Classes
class ChangeTracker:
    def __init__(self):
        self.initial_values: Dict[str, str] = {}
        self.current_values: Dict[str, str] = {}
        self.changed_fields: Set[str] = set()

    def set_initial(self, field: str, value: str):
        self.initial_values[field] = value
        self.current_values[field] = value

    def update_value(self, field: str, value: str):
        self.current_values[field] = value
        if value != self.initial_values[field]:
            self.changed_fields.add(field)
        else:
            self.changed_fields.discard(field)

    def get_changed_values(self) -> Dict[str, str]:
        return {field: self.current_values[field]
                for field in self.changed_fields}

    def get_changed_fields(self) -> list:
        return list(self.changed_fields)

    def has_changes(self) -> bool:
        return len(self.changed_fields) > 0

class SimpleParameterTracker(ChangeTracker):
    def __init__(self):
        super().__init__()
        self.field_paths: Dict[str, str] = {}
        self.session = None

    def set_session(self, session):
        self.session = session

    def set_initial_with_path(self, field_id: str, value: str, original_path: str):
        self.set_initial(field_id, value)
        self.field_paths[field_id] = original_path

    def get_changed_by_path(self) -> Dict[str, str]:
        """Retourne les changements avec les valeurs ORIGINALES vs ACTUELLES"""
        changed = {}
        for field_id in self.changed_fields:
            original_path = self.field_paths.get(field_id, field_id)
            changed[original_path] = {
                'original': self.initial_values[field_id],
                'current': self.current_values[field_id]
            }
        return changed

    def get_changed_values_only(self) -> Dict[str, str]:
        """Retourne uniquement les valeurs actuelles des champs modifiés"""
        changed = {}
        for field_id in self.changed_fields:
            original_path = self.field_paths.get(field_id, field_id)
            changed[original_path] = self.current_values[field_id]
        return changed

    def reset_to_initial(self) -> Dict[str, str]:
        """Reset et retourne les valeurs initiales"""
        self.current_values = self.initial_values.copy()
        self.changed_fields.clear()
        return self.initial_values

    def reset_field_ui(self, field_id: str):
        """Reset un champ spécifique dans l'UI"""
        if field_id in self.initial_values and self.session:
            initial_value = self.initial_values[field_id]
            ui.update_text(field_id, value=initial_value, session=self.session)
            self.update_value(field_id, initial_value)

    def reset_all_ui(self):
        """Reset tous les champs dans l'UI"""
        if self.session:
            for field_id, initial_value in self.initial_values.items():
                ui.update_text(field_id, value=initial_value, session=self.session)
            self.reset_to_initial()



# Fonctions de construction de l'UI
def build_param_ui(node, path: str = "", tracker: Optional[SimpleParameterTracker] = None):
    """
    Construit l'UI des paramètres avec tracking des changements
    """
    if tracker is None:
        tracker = param_tracker

    items = []

    if hasattr(node, "children") and node.children:
        for key, child in node.children.items():
            items.append(
                ui.accordion_panel(
                    key,
                    *build_param_ui(child, path=f"{path}.{key}" if path else key, tracker=tracker)
                )
            )
        return [ui.accordion(*items, open_all=False)]
    else:
        full_id = path.replace(".", "")

        if isinstance(node, ParameterScale):
            return [ui.markdown(f"**{node.name}**: {node.description}")]

        # Créer les inputs et enregistrer les valeurs initiales
        inputs = []
        for param_at_instant in getattr(node, "values_list", []):
            field_id = f"{full_id}_value_at_{param_at_instant.instant_str.replace('-', '_')}"
            initial_value = str(param_at_instant.value)
            original_path = f"{path}.{param_at_instant.instant_str}"

            # Enregistrer avec le chemin original
            tracker.set_initial_with_path(field_id, initial_value, original_path)

            inputs.append(
                ui.input_text(
                    field_id,
                    f"{param_at_instant.instant_str}",
                    value=initial_value
                )
            )

        return inputs

def build_reform_code(tracker: SimpleParameterTracker):

    if tracker is None or not tracker.has_changes():
        return

    changed_by_path = param_tracker.get_changed_by_path()
    lines = [
        "from openfisca_core.reforms import Reform",
        "",
        "class CustomReform(Reform):",
        "    def apply(self):",
        "        self.modify_parameters(modifier_function=self.modify_my_parameters)",
        "",
        "    @staticmethod",
        "    def modify_my_parameters(parameters):",
    ]
    for path, value in changed_by_path.items():
        lines += [
            f"        parameters.{path[:-11]}.update(period=\"{period}\", value={value['current']})",
            "",
        ]
    lines += ["        return parameters"]
    return "\n".join(lines)


# Instance globale du tracker
param_tracker = SimpleParameterTracker()


# Interface utilisateur
app_ui = app_ui = ui.layout_columns(
    ui.page_fluid(
        ui.panel_title("Générateur de réforme OpenFisca"),

        ui.page_fluid(

            # Section principale avec les paramètres
            ui.card(
                ui.card_header("Paramètres"),
                ui.card_body(
                    *build_param_ui(param_root, tracker=param_tracker)
                )
            ),

            ui.hr(),

            # Boutons d'action
            ui.row(
                ui.column(3, ui.input_action_button("reset_all", "Reset tout", class_="btn-warning")),
            ),

            ui.hr(),

            # Outputs
            ui.row(
                ui.column(
                    8,
                    ui.card(
                        ui.card_header("📝 Changements détectés"),
                        ui.card_body(
                            ui.output_text_verbatim("changes_output", placeholder=True)
                        ),
                        class_="shadow-sm mb-4"
                    ),
                    align="center"
                )
            ),
            ui.input_action_button("gen_code", "🛠 Générer le code"),
            ui.h4("🔧 Code Python généré"),
            ui.output_text_verbatim("reform_display", placeholder=True),
            ui.input_action_button("exec_btn", "Exécuter"),
            ui.output_text("exec_result"),
            ui.download_button("download_py", "📅 Télécharger reform.py"),
            ),
        ),
    ui.page_fluid(
        ui.panel_title("Résultats"),
        ui.markdown("Cette section est réservée aux résultats de la réforme appliquée."),
        ui.output_ui("exec_reform_md")
        ),
)

# Serveur
def server(input, output, session):

    reform_code_rx = reactive.Value("")
    result = reactive.Value("")
    store_rx = reactive.Value({})

    # Initialiser le tracker avec la session
    param_tracker.set_session(session)

    # Tracking automatique des changements
    @reactive.effect
    def track_changes():
        for field_id in param_tracker.initial_values.keys():
            # Convertir le field_id pour l'accès aux inputs
            input_attr = field_id.replace('-', '_')
            if hasattr(input, input_attr):
                current_value = getattr(input, input_attr)()
                param_tracker.update_value(field_id, current_value)

    # Afficher les changements à chaque modification ou reset
    @output
    @render.text
    @reactive.event(input.reset_all, *[getattr(input, field_id.replace('-', '_')) for field_id in param_tracker.initial_values.keys()])
    def changes_output():
        changed_by_path = param_tracker.get_changed_by_path()
        if changed_by_path:
            result = "Changements détectés:\n"
            for path, values in changed_by_path.items():
                result += f"• {path}: {values['original']} → {values['current']} \n"
            return result
        return "Aucune modification détectée"

    # # Statut en temps réel
    # @output
    # @render.text
    # def status_output():
    #     if param_tracker.has_changes():
    #         changed_fields = param_tracker.get_changed_fields()
    #         return f"🔄 {len(changed_fields)} champ(s) modifié(s)"
    #     return "✅ Aucune modification en cours"

    # Reset tous les champs
    @reactive.effect
    @reactive.event(input.reset_all)
    def reset_all():
        param_tracker.reset_all_ui()
        # Nettoyer la sortie des changements détectés
        # Annule les changements affichés en forçant le composant output à se réinitialiser
        session.send_input_message("changes_output", {"value": "Aucune modification détectée"})


    @output
    @render.text
    def reform_display():
        return reform_code_rx.get()


    @reactive.Effect
    @reactive.event(input.gen_code)
    def generate():
        print("🔄 Génération déclenchée")
        reform_code = build_reform_code(param_tracker)
        print("✅ Code généré :\n", reform_code)
        reform_code_rx.set(reform_code)


    @output
    @render.download(filename="reform.py")
    def download_py():
        return StringIO(reform_code_rx.get())

    @reactive.Effect
    def execute_code():
        if input.exec_btn() > 0:
            code = reform_code_rx.get()
            with tempfile.TemporaryDirectory() as tempdir:
                path = os.path.join(tempdir, "temp_module.py")
                with open(path, "w") as f:
                    f.write(code)
                spec = importlib.util.spec_from_file_location("temp_module", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, "CustomReform"):
                    reform_class = module.CustomReform
                    store_rx.set({"reform_class": reform_class})
                    result.set("Réforme appliquée avec succès.")
                else:
                    result.set("Classe CustomReform non trouvée dans le module.")

    @output
    @render.text
    def exec_result():
        return result.get()

    @output
    @output
    @render.ui
    def exec_reform_md():
        store = store_rx.get()
        if "reform_class" in store:
            reform = store.get("reform_class")
            # reform_instance = reform_class(tbs)
            scenario = create_randomly_initialized_survey_scenario(collection=None, reform=reform)
            md_content = f"### Scénario généré avec la réforme `{reform.__name__}`\n\n"
            variables = ["basic_income", "income_tax", "housing_allowance"]  # Exemple de variables à afficher
            md_content += "Aggrégats : \n"
            for variable in variables:
                baseline_value = int(scenario.compute_aggregate(variable, period=period, use_baseline=True))
                reform_value = int(scenario.compute_aggregate(variable, period=period))
                diff = reform_value - baseline_value
                md_content += f"- **{variable}**: baseline {baseline_value}, réforme {reform_value}, différence {diff}\n"

            return ui.markdown(md_content)
        else:
            return "Aucune réforme appliquée."


# Créer l'application
app = App(app_ui, server)

if __name__ == "__main__":
    app.run()
