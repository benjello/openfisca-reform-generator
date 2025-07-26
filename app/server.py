# from shiny import render, reactive
# from reform import build_reform_code
# from scenario import ScenarioAnalysis
# import tempfile
# import os
# import importlib.util


# def server_logic(input, output, session, param_tracker, tbs, period):
#     reform_code_rx = reactive.Value("")
#     reform_status = reactive.Value("")
#     store_rx = reactive.Value({})

#     param_tracker.set_session(session)

#     @reactive.effect
#     def track_changes():
#         for field_id in param_tracker.initial_values.keys():
#             input_attr = field_id.replace('-', '_')
#             if hasattr(input, input_attr):
#                 current_value = getattr(input, input_attr)()
#                 param_tracker.update_value(field_id, current_value)

#     @output
#     @render.text
#     @reactive.event(input.reset_all, *[getattr(input, field_id.replace('-', '_')) for field_id in param_tracker.initial_values.keys()])
#     def changes_output():
#         changed_by_path = param_tracker.get_changed_by_path()
#         if changed_by_path:
#             result = "Changements détectés:\n"
#             for path, values in changed_by_path.items():
#                 result += f"• {path}: {values['original']} → {values['current']} \n"
#             return result
#         return "Aucune modification détectée"

#     @reactive.effect
#     @reactive.event(input.reset_all)
#     def reset_all():
#         param_tracker.reset_all_ui()
#         reform_code_rx.set("")
#         store_rx.set({"reform_class": None})
#         session.send_input_message("changes_output", {"value": "Aucune modification détectée"})

#     @output
#     @render.text
#     def reform_display():
#         return reform_code_rx.get()

#     @reactive.effect
#     @reactive.event(input.gen_code)
#     def generate():
#         reform_code = build_reform_code(param_tracker, period)
#         reform_code_rx.set(reform_code)

#     @output
#     @render.download(filename="reform.py")
#     def download_py():
#         from io import StringIO
#         return StringIO(reform_code_rx.get())

#     @reactive.effect
#     def execute_code():
#         if input.exec_btn() > 0:
#             code = reform_code_rx.get()
#             with tempfile.TemporaryDirectory() as tempdir:
#                 path = os.path.join(tempdir, "temp_module.py")
#                 with open(path, "w") as f:
#                     f.write(code)
#                 spec = importlib.util.spec_from_file_location("temp_module", path)
#                 module = importlib.util.module_from_spec(spec)
#                 spec.loader.exec_module(module)

#                 if hasattr(module, "CustomReform"):
#                     reform_class = module.CustomReform
#                     store_rx.set({"reform_class": reform_class})
#                     reform_status.set("Réforme appliquée avec succès.")
#                 else:
#                     reform_status.set("Classe CustomReform non trouvée dans le module.")

#     @output
#     @render.text
#     def exec_result():
#         return reform_status.get()

#     scenario_analysis = ScenarioAnalysis(store_rx, tbs, period)
#     scenario_analysis.register_outputs(input, output)










from shiny import render, reactive
from reform import build_reform_code
from scenario import ScenarioAnalysis
import tempfile
import os
import importlib.util

def server_logic(input, output, session, param_tracker, tbs, period):
    reform_code_rx = reactive.value("")
    reform_status = reactive.value("")
    store_rx = reactive.value({})

    # Flag to track if initialization is complete
    initialization_complete = reactive.value(False)

    param_tracker.set_session(session)

    # Delay initialization to prevent false change detection
    @reactive.effect
    def _delayed_initialization():
        # Use invalidate_later to delay the initialization
        reactive.invalidate_later(1.0)  # Wait 1 second
        initialization_complete.set(True)

    # Improved change tracking that waits for initialization
    @reactive.effect
    def track_changes():
        # Only start tracking after initialization is complete
        if not initialization_complete.get():
            return

        for field_id in param_tracker.initial_values.keys():
            input_attr = field_id.replace('-', '_')
            if hasattr(input, input_attr):
                try:
                    current_value = getattr(input, input_attr)()
                    # Only update if we have a meaningful change and value is not None
                    if current_value is not None:
                        param_tracker.update_value(field_id, current_value)
                except Exception:
                    # Skip inputs that aren't ready yet
                    continue

    @render.text
    @reactive.event(input.reset_all, *[getattr(input, field_id.replace('-', '_')) for field_id in param_tracker.initial_values.keys()])
    def changes_output():
        # Only show changes after initialization is complete
        if not initialization_complete.get():
            return "Initializing system..."

        changed_by_path = param_tracker.get_changed_by_path()
        if changed_by_path:
            result = "Changements détectés:\n\n"
            for path, values in changed_by_path.items():
                # Double-check that values are actually different
                original = str(values['original']).strip()
                current = str(values['current']).strip()
                if original != current:
                    result += f"• {path}:\n  {original} → {current}\n\n"

            if result == "Changements détectés:\n\n":
                return "Aucune modification détectée"
            return result
        return "Aucune modification détectée"

    @reactive.effect
    @reactive.event(input.reset_all)
    def reset_all():
        # Reset all values in the tracker
        param_tracker.reset_all_ui()
        reform_code_rx.set("")
        store_rx.set({"reform_class": None})
        reform_status.set("")

        # Force update the changes display
        session.send_input_message("changes_output", {"value": "Tous les paramètres ont été réinitialisés"})

    @render.text
    def reform_display():
        return reform_code_rx.get()

    @reactive.effect
    @reactive.event(input.gen_code)
    def generate():
        # Only generate code if there are actual changes and initialization is complete
        if not initialization_complete.get():
            reform_code_rx.set("# Initialisation en cours...")
            return

        changed_by_path = param_tracker.get_changed_by_path()
        if not changed_by_path:
            reform_code_rx.set("# Aucune modification détectée - aucun code à générer")
            return

        reform_code = build_reform_code(param_tracker, period)
        reform_code_rx.set(reform_code)

    @render.download(filename="reform.py")
    def download_py():
        from io import StringIO
        code = reform_code_rx.get()
        if not code or code.startswith("#"):
            # Return empty file if no actual code
            return StringIO("# No changes to download")
        return StringIO(code)

    @reactive.effect
    @reactive.event(input.exec_btn)
    def execute_code():
        if not initialization_complete.get():
            reform_status.set("Initialisation en cours...")
            return

        code = reform_code_rx.get()

        if not code or code.startswith("#"):
            reform_status.set("Aucun code à exécuter - générez d'abord le code de réforme")
            return

        try:
            with tempfile.TemporaryDirectory() as tempdir:
                path = os.path.join(tempdir, "temp_module.py")
                with open(path, "w", encoding='utf-8') as f:
                    f.write(code)

                spec = importlib.util.spec_from_file_location("temp_module", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, "CustomReform"):
                    reform_class = module.CustomReform
                    store_rx.set({"reform_class": reform_class})
                    reform_status.set("✅ Réforme appliquée avec succès.")
                else:
                    reform_status.set("❌ Erreur: Classe CustomReform non trouvée dans le module.")

        except Exception as e:
            reform_status.set(f"❌ Erreur lors de l'exécution: {str(e)}")

    @render.text
    def exec_result():
        return reform_status.get()

    # Initialize scenario analysis
    scenario_analysis = ScenarioAnalysis(store_rx, tbs, period)
    scenario_analysis.register_outputs(input, output)
