from typing import Optional
from shiny import ui
from shinywidgets import output_widget
import pandas as pd
from openfisca_core.parameters import ParameterScale
from parameter import SimpleParameterTracker

def _create_bracket_inputs(node: ParameterScale, path: str, full_id: str, tracker: SimpleParameterTracker) -> list:
    """Helper function to create bracket inputs for ParameterScale nodes."""
    scale_df = pd.DataFrame()

    # Build the DataFrame for scale parameters
    for rank, bracket in enumerate(node.brackets):
        bracket_df = pd.DataFrame()

        for key in ['threshold', 'rate', 'amount']:
            child = bracket.children.get(key)
            if child is None:
                continue

            for param_at_instant in getattr(child, "values_list", []):
                initial_value = str(param_at_instant.value)
                date = param_at_instant.instant_str
                bracket_df.at[date, key] = initial_value

        if not bracket_df.empty:
            scale_df = pd.concat([scale_df, pd.concat([bracket_df], keys=[rank], axis=1)], axis=1)

    if scale_df.empty:
        return []

    # Sort and forward fill
    scale_df = scale_df.sort_index()
    for col in scale_df.columns:
        first_valid = scale_df[col].first_valid_index()
        if first_valid is not None:
            scale_df.loc[first_valid:, col] = scale_df.loc[first_valid:, col].ffill()

    scale_df = scale_df.sort_index(ascending=False)

    # Create input elements
    inputs = []
    for instant in scale_df.index:
        input_elements = []

        for col, series in scale_df.items():
            rank, key = col
            initial_value = series[instant]

            if pd.isna(initial_value):
                continue

            field_id = f"{full_id}_bracket_{rank}_{key}_value_at_{instant.replace('-', '_')}"
            original_path = f"{path}.brackets[{rank}].{key}.{instant.replace('-', '_')}"

            # Register with tracker - this should happen BEFORE input creation
            # and we need to ensure the tracker doesn't immediately flag this as changed
            tracker.set_initial_with_path(field_id, initial_value, original_path)

            input_elements.append(
                ui.input_text(
                    field_id,
                    f"Bracket {rank} {key}",
                    value=initial_value
                )
            )

        if input_elements:
            inputs.extend([
                ui.h6(f"Date: {instant}", class_="text-muted mt-3"),
                ui.div(
                    *[ui.div(element, class_="col-md-6 mb-2") for element in input_elements],
                    class_="row"
                ),
                ui.hr(class_="my-2")
            ])

    return inputs

def _create_simple_inputs(node, path: str, full_id: str, tracker: SimpleParameterTracker) -> list:
    """Helper function to create simple parameter inputs."""
    inputs = []

    for param_at_instant in getattr(node, "values_list", []):
        field_id = f"{full_id}_value_at_{param_at_instant.instant_str.replace('-', '_')}"
        initial_value = str(param_at_instant.value)
        original_path = f"{path}.{param_at_instant.instant_str}"

        # Register with tracker BEFORE input creation
        tracker.set_initial_with_path(field_id, initial_value, original_path)

        inputs.append(
            ui.div(
                ui.input_text(
                    field_id,
                    f"Value at {param_at_instant.instant_str}",
                    value=initial_value
                ),
                class_="mb-2"
            )
        )

    return inputs

def build_param_ui(node, path: str = "", tracker: Optional[SimpleParameterTracker] = None):
    """
    Build parameter UI with change tracking.

    Args:
        node: Parameter node to build UI for
        path: Current parameter path
        tracker: Parameter change tracker

    Returns:
        List of UI elements
    """
    if tracker is None:
        raise ValueError("Tracker is required for parameter UI building")

    items = []

    # Handle nodes with children (create accordion)
    if hasattr(node, "children") and node.children:
        for key, child in node.children.items():
            child_path = f"{path}.{key}" if path else key
            child_ui = build_param_ui(child, path=child_path, tracker=tracker)

            if child_ui:  # Only add if there are UI elements
                items.append(
                    ui.accordion_panel(
                        key,  #.replace("_", " ").title(),  # Better display name
                        *child_ui
                    )
                )

        return [ui.accordion(*items, open=False, multiple=True)] if items else []

    # Handle leaf nodes
    # full_id = path.replace(".", "_")  # Use underscore for cleaner IDs
    full_id = path.replace(".", "")

    if isinstance(node, ParameterScale):
        return _create_bracket_inputs(node, path, full_id, tracker)
    else:
        return _create_simple_inputs(node, path, full_id, tracker)

def build_results_ui():
    """Build the results section UI."""
    return ui.div(
        ui.card(
            ui.card_header(
                ui.h4("📊 Results Overview", class_="mb-0")
            ),
            ui.card_body(
                ui.p("This section displays the results of the applied reform.",
                     class_="text-muted mb-3"),
                ui.output_data_frame("aggregates_table")
            )
        ),
        ui.card(
            ui.card_header(
                ui.h4("📈 Scenario Analysis", class_="mb-0")
            ),
            ui.card_body(
                output_widget("aggregates_amounts_plot"),
                ui.hr(),
                output_widget("aggregates_beneficiaries_plot"),
                ui.hr(),
                output_widget("scenario_pivot_plot")

            )
        ),
        class_="mt-3"
    )

def app_ui(tbs, tracker):
    """
    Main application UI with improved change detection.

    Args:
        tbs: Tax benefit system
        tracker: Parameter change tracker

    Returns:
        UI layout
    """
    param_root = tbs.parameters

    # Clear any existing tracked changes before building UI
    # This is crucial to prevent false positives
    if hasattr(tracker, 'clear_all_changes'):
        tracker.clear_all_changes()

    return ui.page_navbar(
        # Reform Panel
        ui.nav_panel(
            "🔧 Reform Configuration",
            ui.layout_columns(
                # Parameters Card
                ui.card(
                    ui.card_header(
                        ui.h3("⚙️ Parameters", class_="mb-0")
                    ),
                    ui.card_body(
                        ui.div(
                            *build_param_ui(param_root, tracker=tracker),
                            style="max-height: 600px; overflow-y: auto;"
                        )
                    ),
                    class_="mb-3"
                ),

                # Controls and Code Generation
                ui.div(
                    # Reset Button
                    ui.card(
                        ui.card_body(
                            ui.input_action_button(
                                "reset_all",
                                "🔄 Reset All Parameters",
                                class_="btn-warning btn-lg w-100"
                            )
                        )
                    ),

                    # Changes Display
                    ui.card(
                        ui.card_header(
                            ui.h4("📝 Detected Changes", class_="mb-0")
                        ),
                        ui.card_body(
                            ui.output_text_verbatim(
                                "changes_output",
                                placeholder="No changes detected yet..."
                            )
                        ),
                        class_="mt-3"
                    ),

                    # Code Generation
                    ui.card(
                        ui.card_header(
                            ui.h4("🛠️ Code Generation", class_="mb-0")
                        ),
                        ui.card_body(
                            ui.div(
                                ui.input_action_button(
                                    "gen_code",
                                    "Generate Python Code",
                                    class_="btn-primary me-2"
                                ),
                                ui.input_action_button(
                                    "exec_btn",
                                    "Execute Reform",
                                    class_="btn-success me-2"
                                ),
                                ui.download_button(
                                    "download_py",
                                    "📥 Download reform.py",
                                    class_="btn-outline-secondary"
                                ),
                                class_="mb-3"
                            ),
                            ui.output_text_verbatim(
                                "reform_display",
                                placeholder="Generated code will appear here..."
                            ),
                            ui.output_text("exec_result")
                        ),
                        class_="mt-3"
                    ),
                    class_="col-md-6"
                ),
                col_widths=[6, 6]
            )
        ),

        # Results Panel
        ui.nav_panel(
            "📊 Results",
            build_results_ui()
        ),

        title="Tax Reform Tool",
        id="main_navbar"
    )
