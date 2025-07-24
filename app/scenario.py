import pandas as pd
from shiny import ui, render
from shinywidgets import render_widget
from openfisca_survey_manager.tests.test_scenario import create_randomly_initialized_survey_scenario
import plotly.graph_objects as go

class AbstractScenarioAnalysis:
    def __init__(self, store_rx, tbs, period):
        self.store_rx = store_rx
        self.tbs = tbs
        self.period = period

    def _get_reform_class(self):
        store = self.store_rx.get()
        return store.get("reform_class")


class ScenarioAnalysis(AbstractScenarioAnalysis):
    def __init__(self, store_rx, tbs, period):
        super().__init__(store_rx, tbs, period)

    def _create_scenario(self):
        reform_class = self._get_reform_class()
        if reform_class:
            return create_randomly_initialized_survey_scenario(collection=None, reform=reform_class)
        return None

    def render_reform_md(self):
        reform_class = self._get_reform_class()
        if not reform_class:
            return "Aucune réforme appliquée."

        scenario = self._create_scenario()
        if not scenario:
            return "Erreur lors de la création du scénario."

        md_content = f"### Scénario généré avec la réforme `{reform_class.__name__}`\n\n"
        variables = ["basic_income", "income_tax", "housing_allowance"]
        md_content += "Aggrégats : \n"
        for variable in variables:
            baseline_value = int(scenario.compute_aggregate(variable, period=self.period, use_baseline=True))
            reform_value = int(scenario.compute_aggregate(variable, period=self.period))
            diff = reform_value - baseline_value
            md_content += f"- **{variable}**: baseline {baseline_value}, réforme {reform_value}, différence {diff}\n"
        return ui.markdown(md_content)

    def render_scenario_plot(self):
        reform_class = self._get_reform_class()
        if not reform_class:
            return None

        scenario = self._create_scenario()
        if not scenario:
            return None

        variables = ["basic_income", "income_tax", "housing_allowance", "social_security_contribution"]
        data = []
        for var in variables:
            baseline = scenario.compute_aggregate(var, period=self.period, use_baseline=True)
            reform = scenario.compute_aggregate(var, period=self.period)
            data.append((var, baseline, reform))
        df = pd.DataFrame(data, columns=["Variable", "Baseline", "Reform"])
        df["Difference"] = df["Reform"] - df["Baseline"]
        fig = go.Figure(data=[
            go.Bar(name='Baseline', x=df['Variable'], y=df['Baseline']),
            go.Bar(name='Reform', x=df['Variable'], y=df['Reform'])
        ])
        fig.update_layout(barmode='group', title_text='Comparaison réforme vs baseline', yaxis_title='Montants agrégés')
        return fig

    def render_scenario_pivot_plot(self):
        reform_class = self._get_reform_class()
        if not reform_class:
            return None

        scenario = self._create_scenario()
        if not scenario:
            return None

        housing_occupancy_status_names = self.tbs.variables['housing_occupancy_status'].possible_values.names
        df = scenario.compute_pivot_table(values=["total_benefits"], columns=['housing_occupancy_status'], period=self.period, difference=True, weighted=False)
        df = df.rename(columns=dict(zip(range(len(housing_occupancy_status_names)), housing_occupancy_status_names)))
        fig = go.Figure(data=[
            go.Bar(x=df.index, y=df[col], name=col)
            for col in df.columns
        ])
        fig.update_layout(
            barmode='group',
            title_text="Total Benefits by Housing Occupancy Status",
            xaxis_title="Housing Occupancy Status",
            yaxis_title="Total Benefits",
            legend_title="Housing Occupancy Status"
        )
        return fig

    def register_outputs(self, output):
        @output
        @render.ui
        def exec_reform_md():
            return self.render_reform_md()

        @output
        @render_widget
        def scenario_plot():
            return self.render_scenario_plot()

        @output
        @render_widget
        def scenario_pivot_plot():
            return self.render_scenario_pivot_plot()
