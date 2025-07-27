'''Parameters Tracker Module.

This module provides classes to track changes in parameters, allowing for
the management of initial and current values, as well as detecting changes.'''

from typing import Dict, Set
from shiny import ui

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
