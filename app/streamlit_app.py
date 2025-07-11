import streamlit as st
from io import StringIO
import tempfile
import importlib.util
import os
from typing import Dict, Any, Optional, Set

from openfisca_core.parameters import ParameterScale
from openfisca_country_template import CountryTaxBenefitSystem
from openfisca_survey_manager.tests.test_scenario import create_randomly_initialized_survey_scenario

# Initialize OpenFisca system
@st.cache_resource
def get_tax_benefit_system():
    return CountryTaxBenefitSystem()

tbs = get_tax_benefit_system()
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

# Initialize session state
if 'param_tracker' not in st.session_state:
    st.session_state.param_tracker = SimpleParameterTracker()
if 'reform_code' not in st.session_state:
    st.session_state.reform_code = ""
if 'reform_class' not in st.session_state:
    st.session_state.reform_class = None

def build_param_ui(node, path: str = "", container=None, tracker: Optional[SimpleParameterTracker] = None):
    """
    Construit l'UI des paramètres avec tracking des changements pour Streamlit
    """
    if tracker is None:
        tracker = st.session_state.param_tracker

    if container is None:
        container = st

    if hasattr(node, "children") and node.children:
        # Use expander for child nodes
        for key, child in node.children.items():
            with container.expander(f"📁 {key}", expanded=False):
                build_param_ui(child, path=f"{path}.{key}" if path else key, container=st, tracker=tracker)
    else:
        full_id = path.replace(".", "")

        if isinstance(node, ParameterScale):
            container.markdown(f"**{node.name}**: {node.description}")
            return

        # Créer les inputs et enregistrer les valeurs initiales
        for param_at_instant in getattr(node, "values_list", []):
            field_id = f"{full_id}_value_at_{param_at_instant.instant_str.replace('-', '_')}"
            initial_value = str(param_at_instant.value)
            original_path = f"{path}.{param_at_instant.instant_str}"

            # Enregistrer avec le chemin original si pas déjà fait
            if field_id not in tracker.initial_values:
                tracker.set_initial_with_path(field_id, initial_value, original_path)

            # Créer l'input avec une clé unique et récupérer la valeur
            current_value = container.text_input(
                f"{param_at_instant.instant_str}",
                value=tracker.current_values.get(field_id, initial_value),
                key=field_id,
                help=f"Path: {original_path}"
            )
            
            # Mettre à jour le tracker
            tracker.update_value(field_id, current_value)

def build_reform_code(tracker: SimpleParameterTracker):
    if tracker is None or not tracker.has_changes():
        return ""

    changed_by_path = tracker.get_changed_by_path()
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

def main():
    st.set_page_config(
        page_title="Générateur de réforme OpenFisca",
        page_icon="🏛️",
        layout="wide"
    )

    st.title("🏛️ Générateur de réforme OpenFisca")

    # Create two columns for layout
    col1, col2 = st.columns([3, 2])

    with col1:
        st.header("📊 Paramètres")
        
        # Add a container for parameters with scrolling
        with st.container():
            build_param_ui(param_root, tracker=st.session_state.param_tracker)

        st.divider()
        
        # Reset button
        if st.button("🔄 Reset tout", type="secondary"):
            st.session_state.param_tracker.reset_to_initial()
            st.rerun()

    with col2:
        st.header("📝 Changements détectés")
        
        # Display changes
        tracker = st.session_state.param_tracker
        changed_by_path = tracker.get_changed_by_path()
        
        if changed_by_path:
            st.success(f"🔄 {len(changed_by_path)} changement(s) détecté(s)")
            for path, values in changed_by_path.items():
                st.write(f"• **{path}**: `{values['original']}` → `{values['current']}`")
        else:
            st.info("✅ Aucune modification détectée")

        st.divider()

        # Generate code button
        if st.button("🛠️ Générer le code", type="primary", disabled=not tracker.has_changes()):
            st.session_state.reform_code = build_reform_code(tracker)

        # Display generated code
        if st.session_state.reform_code:
            st.subheader("🔧 Code Python généré")
            st.code(st.session_state.reform_code, language="python")
            
            # Download button
            st.download_button(
                label="📅 Télécharger reform.py",
                data=st.session_state.reform_code,
                file_name="reform.py",
                mime="text/plain"
            )

            # Execute button
            if st.button("▶️ Exécuter", type="primary"):
                try:
                    with tempfile.TemporaryDirectory() as tempdir:
                        path = os.path.join(tempdir, "temp_module.py")
                        with open(path, "w") as f:
                            f.write(st.session_state.reform_code)
                        spec = importlib.util.spec_from_file_location("temp_module", path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        if hasattr(module, "CustomReform"):
                            st.session_state.reform_class = module.CustomReform
                            st.success("✅ Réforme appliquée avec succès.")
                        else:
                            st.error("❌ Classe CustomReform non trouvée dans le module.")
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'exécution: {str(e)}")

    # Results section
    if st.session_state.reform_class:
        st.divider()
        st.header("📊 Résultats")
        
        try:
            reform = st.session_state.reform_class
            scenario = create_randomly_initialized_survey_scenario(collection=None, reform=reform)
            
            st.subheader(f"Scénario généré avec la réforme `{reform.__name__}`")
            
            # Display aggregates
            st.subheader("Agrégats :")
            variables = ["basic_income", "income_tax", "housing_allowance"]
            
            results_data = []
            for variable in variables:
                try:
                    baseline_value = int(scenario.compute_aggregate(variable, period=period, use_baseline=True))
                    reform_value = int(scenario.compute_aggregate(variable, period=period))
                    diff = reform_value - baseline_value
                    results_data.append({
                        "Variable": variable,
                        "Baseline": baseline_value,
                        "Réforme": reform_value,
                        "Différence": diff
                    })
                except Exception as e:
                    st.warning(f"Impossible de calculer {variable}: {str(e)}")
            
            if results_data:
                import pandas as pd
                df = pd.DataFrame(results_data)
                st.dataframe(df, use_container_width=True)
                
                # Create a simple chart
                if len(results_data) > 0:
                    st.bar_chart(df.set_index("Variable")[["Baseline", "Réforme"]])
                    
        except Exception as e:
            st.error(f"❌ Erreur lors du calcul des résultats: {str(e)}")

if __name__ == "__main__":
    main()
