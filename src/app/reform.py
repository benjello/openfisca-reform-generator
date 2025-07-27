from parameter import SimpleParameterTracker

def build_reform_code(tracker: SimpleParameterTracker, period: int) -> str:
    """
    Builds the Python code for the reform based on the changes tracked.
    """
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
