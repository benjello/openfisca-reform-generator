from shiny import App, ui, reactive, render
from openfisca_core.parameters import load_parameter_file, ParameterNode

# Charger les paramètres
param_root: ParameterNode = load_parameter_file("openfisca_country_template/parameters.yaml")

def build_param_ui(node: ParameterNode, path=""):
    items = []
    if node.children:
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
        return [
            ui.input_text(f"{full_id}_value", "Value", str(node.value)),
            ui.input_text(f"{full_id}_start", "Start", str(node.start)),
            ui.input_text(f"{full_id}_end", "End", str(node.end)),
        ]

def build_reform_code(inputs):
    lines = [
        "from openfisca_core.reforms import Reform",
        "",
        "class CustomReform(Reform):",
        "    def apply(self):",
        "        super().apply()",
    ]
    for key in inputs.keys():
        if key.endswith("_value"):
            base = key[:-6]
            param_path = base.replace("_", ".")
            value = inputs[key]()
            start = inputs.get(f"{base}_start", lambda: "")()
            end = inputs.get(f"{base}_end", lambda: "")()
            lines += [
                f"        self.modify_parameter([{repr(param_path)}], {{",
                f"            '{start}': {{'value': {value}, 'end': '{end}'}}",
                "        })",
            ]
    return "\n".join(lines)

app_ui = ui.page_fluid(
    ui.panel_title("🧮 Générateur de réforme OpenFisca"),
    *build_param_ui(param_root),
    ui.hr(),
    ui.h4("🔧 Code Python généré"),
    ui.output_text_verbatim("reform_code", placeholder=True),
    ui.download_button("download_py", "Télécharger reform.py")
)

def server(input, output, session):
    code_rx = reactive.Value("")

    @output
    @render.text
    def reform_code():
        code = build_reform_code(input)
        code_rx.set(code)
        return code

    @output
    @render.download(filename="reform.py")
    def download_py():
        return code_rx.get().encode()

app = App(app_ui, server)
