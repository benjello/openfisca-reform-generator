from typing import Optional
from shiny import ui
from shinywidgets import output_widget
import pandas as pd
from openfisca_core.parameters import ParameterScale
from parameter import SimpleParameterTracker

def build_param_ui(node, path: str = "", tracker: Optional[SimpleParameterTracker] = None):
    """
    Construit l'UI des paramètres avec tracking des changements
    """
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
                    child = bracket.children.get(key)
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

            for instant in scale_df.index:
                input_elements = []
                for col, series in scale_df.items():
                    rank, key = col

                    initial_value = series[instant]
                    if pd.isna(initial_value):
                        continue
                    field_id = f"{full_id}_bracket_{rank}_{key}_value_at_{instant.replace('-', '_')}"
                    original_path = f"{path}.brackets[{rank}].{key}.{instant.replace('-', '_')}"
                    # Enregistrer avec le chemin original
                    tracker.set_initial_with_path(field_id, initial_value, original_path)
                    input_elements.append(
                        ui.input_text(
                            field_id,
                            f"bracket {rank} {key}",
                            value=initial_value
                            )
                        )
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

def app_ui(tbs, tracker):
    param_root = tbs.parameters
    return ui.layout_columns(
        ui.page_fluid(
            ui.panel_title("Générateur de réforme OpenFisca"),
            ui.page_fluid(
                ui.card(
                    ui.card_header("Paramètres"),
                    ui.card_body(
                        *build_param_ui(param_root, tracker=tracker)
                    )
                ),
                ui.hr(),
                ui.row(
                    ui.column(3, ui.input_action_button("reset_all", "Reset tout", class_="btn-warning")),
                ),
                ui.hr(),
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
            output_widget("scenario_plot"),
            output_widget("scenario_pivot_plot"),
        ),
    )
