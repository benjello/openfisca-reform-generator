from io import StringIO
from slugify import slugify
import tempfile
import importlib.util
import os

from shiny import App, ui, reactive, render

from openfisca_country_template import CountryTaxBenefitSystem
from openfisca_core.parameters import ParameterScale
from openfisca_survey_manager.tests.test_scenario import create_randomly_initialized_survey_scenario

cts = CountryTaxBenefitSystem()
param_root = cts.parameters
period = 2016

def build_param_ui(node, path=""):
    items = []
    if hasattr(node, "children") and node.children:
        for key, child in node.children.items():
            items.append(
                ui.accordion_panel(
                    key,
                    *build_param_ui(child, path=f"{path}.{key}" if path else key)
                )
            )
        return [ui.accordion(*items, open_all=False)]
    else:
        full_id = path.replace(".", "_")

        if isinstance(node, ParameterScale):
            return [ui.markdown(f"**{node.__dict__}**")]

        return [
            ui.input_text(
            f"{full_id}_value_at_{param_at_instant.instant_str.replace('-', '_')}",
            f"{param_at_instant.instant_str}",
            value=str(param_at_instant.value)
            )
            for param_at_instant in getattr(node, "values_list", [])
        ]


def build_reform_code(inputs):
    lines = [
        "from openfisca_core.reforms import Reform",
        "",
        "class CustomReform(Reform):",
        "    def apply(self):",
        "        self.modify_parameter(modifier_function=self.modify_my_parameters)",
        "",
        "    @staticmethod",
        "    def modify_my_parameters(parameters):",
    ]
    for key in inputs._map.keys():
        if "_value_at_" not in key:
            print(f"⚠️ Clé non éligible : {key}")
            continue

        print(f"🔍 Traitement de la clé : {key}")
        base = key[:-20]
        print(f"  - Base : {base}")
        param_path = base.replace("_", ".")
        value = inputs[key]()
        lines += [
            f"        parameters.{param_path}(period={period}, value={value})",
            "",
        ]
    return "\n".join(lines)

app_ui = ui.layout_columns(
    ui.page_fluid(
        ui.panel_title("🤲 Générateur de réforme OpenFisca"),
        *build_param_ui(param_root),
        ui.hr(),
        ui.input_action_button("gen_code", "🛠 Générer le code"),
        ui.h4("🔧 Code Python généré"),
        ui.output_text_verbatim("reform_display", placeholder=True),
        ui.input_action_button("exec_btn", "Exécuter"),
        ui.output_text("exec_result"),
        ui.download_button("download_py", "📅 Télécharger reform.py"),
    ),
    ui.page_fluid(
        ui.panel_title("🤲 Résultats"),
        ui.markdown("Cette section est réservée aux résultats de la réforme appliquée."),
        ui.output_text("exec_reform"),
    )
)

def server(input, output, session):
    code_rx = reactive.Value("")
    result = reactive.Value("")
    store_rx = reactive.Value({})

    @reactive.Effect
    @reactive.event(input.gen_code)
    def generate():
        print("🔄 Génération déclenchée")
        code = build_reform_code(input)
        print("✅ Code généré :\n", code)
        code_rx.set(code)

    @output
    @render.text
    def reform_display():
        return code_rx.get()

    @reactive.Effect
    def execute_code():
        if input.exec_btn() > 0:
            code = code_rx.get()
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
    @render.text
    def exec_reform():
        store = store_rx.get()
        if "reform_class" in store:
            # reform_class = store.get("reform_class")
            # reform_instance = reform_class(baseline=cts)
            scenario = create_randomly_initialized_survey_scenario(collection=None)
            return str(scenario)
        else:
            return "Aucune réforme appliquée."

    @output
    @render.download(filename="reform.py")
    def download_py():
        return StringIO(code_rx.get())

app = App(app_ui, server)
