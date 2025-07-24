from shiny import render, reactive
from reform import build_reform_code
from scenario import ScenarioAnalysis
import tempfile
import os
import importlib.util

def server_logic(input, output, session, param_tracker, tbs, period):
    reform_code_rx = reactive.Value("")
    reform_status = reactive.Value("")
    store_rx = reactive.Value({})

    param_tracker.set_session(session)

    @reactive.effect
    def track_changes():
        for field_id in param_tracker.initial_values.keys():
            input_attr = field_id.replace('-', '_')
            if hasattr(input, input_attr):
                current_value = getattr(input, input_attr)()
                param_tracker.update_value(field_id, current_value)

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

    @reactive.effect
    @reactive.event(input.reset_all)
    def reset_all():
        param_tracker.reset_all_ui()
        session.send_input_message("changes_output", {"value": "Aucune modification détectée"})

    @output
    @render.text
    def reform_display():
        return reform_code_rx.get()

    @reactive.Effect
    @reactive.event(input.gen_code)
    def generate():
        reform_code = build_reform_code(param_tracker, period)
        reform_code_rx.set(reform_code)

    @output
    @render.download(filename="reform.py")
    def download_py():
        from io import StringIO
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
                    reform_status.set("Réforme appliquée avec succès.")
                else:
                    reform_status.set("Classe CustomReform non trouvée dans le module.")

    @output
    @render.text
    def exec_result():
        return reform_status.get()

    scenario_analysis = ScenarioAnalysis(store_rx, tbs, period)
    scenario_analysis.register_outputs(output)
