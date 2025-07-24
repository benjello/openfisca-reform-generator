from io import StringIO
import tempfile
import importlib.util
import os


import pandas as pd
import matplotlib.pyplot as plt



from shiny import App, ui, render, reactive
from typing import Dict, Optional, Set


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
        scale_df = pd.DataFrame()
        if isinstance(node, ParameterScale):
            inputs = []
            for rank, bracket in enumerate(node.brackets):
                bracket_df = pd.DataFrame()

                for key in ['threshold', 'rate', 'amount']:
                    print("\n")
                    # print(f"bracket: {bracket.__dict__}")
                    # print("\n")

                    child = bracket.children.get(key)
                    print(f"key: {rank, key}")
                    if child is None:
                        continue
                    for param_at_instant in getattr(child, "values_list", []):
                        initial_value = str(param_at_instant.value)
                        date = f"{param_at_instant.instant_str}"
                        bracket_df.at[date, key] = initial_value
                scale_df = pd.concat([scale_df, pd.concat([bracket_df], keys=[rank], axis=1)], axis=1)

            scale_df = scale_df.sort_index()
            for col in scale_df.columns:
                first_valid = scale_df[col].first_valid_index()
                if first_valid is not None:
                    scale_df.loc[first_valid:, col] = scale_df.loc[first_valid:, col].ffill()

            scale_df = scale_df.sort_index(ascending=False)
            print(scale_df)

            for instant in scale_df.index:
                input_elements = []
                for col, series in scale_df.items():
                    rank, key = col

                    initial_value = series[instant]
                    if pd.isna(initial_value):
                        continue
                    field_id = f"{full_id}_bracket_{rank}_{key}_value_at_{instant.replace('-', '_')}"
                    original_path = f"{path}.brackets[{rank}].{key}.{instant.replace('-', '_')}"
                    print(f"field_id: {field_id} = {initial_value}")
                    # Enregistrer avec le chemin original
                    tracker.set_initial_with_path(field_id, initial_value, original_path)
                    input_elements.append(
                        ui.input_text(
                            field_id,
                            f"bracket {rank} {key}",
                            value=initial_value
                            )
                        )
                print(f"Input elements for {instant}: {input_elements}")
                if input_elements:
                    inputs.append(
                        ui.p(f"{instant}")  # Ajouter les inputs pour chaque instant
                        )
                    inputs.append(
                        ui.row(
                            [
                                ui.column(6, element)
                                for element in input_elements
                            ]
                        )
                    )
                    inputs.append(
                        ui.hr()
                    )
            return inputs

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
        ui.output_ui("exec_reform_md"),
        ui.output_plot("scenario_plot"),
        ui.output_plot("scenario_pivot_plot"),
        ),
)

# Serveur
def server(input, output, session):

    reform_code_rx = reactive.Value("")
    result = reactive.Value("")
    store_rx = reactive.Value({})
    scenario_rx = reactive.Value(None)

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
                    # Generate scenario once and store it
                    scenario = create_randomly_initialized_survey_scenario(collection=None, reform=reform_class)
                    scenario_rx.set(scenario)
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


    @output
    @render.plot
    def scenario_plot():
        store = store_rx.get()
        if "reform_class" in store:
            reform_class = store["reform_class"]
            scenario = create_randomly_initialized_survey_scenario(collection=None, reform=reform_class)

            variables = ["basic_income", "income_tax", "housing_allowance", "social_security_contribution"]
            data = []

            for var in variables:
                baseline = scenario.compute_aggregate(var, period=period, use_baseline=True)
                reform = scenario.compute_aggregate(var, period=period)
                data.append((var, baseline, reform))

            df = pd.DataFrame(data, columns=["Variable", "Baseline", "Reform"])
            df["Difference"] = df["Reform"] - df["Baseline"]

            ax = df.set_index("Variable")[["Baseline", "Reform"]].plot.bar(rot=0)
            ax.set_ylabel("Montants agrégés")
            ax.set_title("Comparaison réforme vs baseline")
            plt.tight_layout()
            return ax


    @output
    @render.plot
    def scenario_pivot_plot():
        store = store_rx.get()
        if "reform_class" in store:
            reform_class = store["reform_class"]

            housing_occupancy_status_names = tbs.variables['housing_occupancy_status'].possible_values.names

            scenario = create_randomly_initialized_survey_scenario(collection=None, reform=reform_class)

            df = scenario.compute_pivot_table(values=["total_benefits"], columns=['housing_occupancy_status'], period=period, difference=True, weighted=False)
            df = df.rename(columns=dict(zip(range(len(housing_occupancy_status_names)), housing_occupancy_status_names)))

            print("Pivot table computed:", df)

            ax = df.plot.bar(rot=0)
            ax.set_ylabel("Basic Income")
            ax.set_title("Comparaison Différence par Housing Occupancy Status")
            ax.legend(title="Housing Occupancy Status")
            ax.grid(axis='y')
            plt.ylabel("Total Benefits")
            plt.title("Total Benefits by Housing Occupancy Status")
            plt.legend(title="Housing Occupancy Status")
            plt.tight_layout()
            return ax


# Créer l'application
app = App(app_ui, server)

if __name__ == "__main__":
    app.run()
