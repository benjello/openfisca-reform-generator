import pandas as pd
from shiny import ui, render, reactive
from shinywidgets import render_widget
from openfisca_nouvelle_caledonie_data.survey_scenario import DSFSurveyScenario
import plotly.graph_objects as go


class AbstractScenarioAnalysis:
    def __init__(self, store_rx, tbs, period):
        self.store_rx = store_rx
        self.tbs = tbs
        self.period = period
        self.scenario = None

    def _get_reform_class(self):
        store = self.store_rx.get()
        return store.get("reform_class")


class ScenarioAnalysis(AbstractScenarioAnalysis):
    def __init__(self, store_rx, tbs, period):
        super().__init__(store_rx, tbs, period)

    def _create_scenario(self):
        reform_class = self._get_reform_class()
        if reform_class:
            if self.scenario is not None:
                return self.scenario

            self.scenario = DSFSurveyScenario(self.period, reform=reform_class)
        return self.scenario

    def render_reform_md(self):
        reform_class = self._get_reform_class()
        if not reform_class:
            return "Aucune réforme appliquée."

        scenario = self._create_scenario()
        if not scenario:
            return "Erreur lors de la création du scénario."

        md_content = f"### Scénario généré avec la réforme `{reform_class.__name__}`\n\n"
        variables = ["revenu_net_global_imposable", "impot_brut", "impot_net"]
        md_content += "Aggrégats : \n"
        for variable in variables:
            baseline_value = int(scenario.compute_aggregate(variable, period=self.period, use_baseline=True, weighted=False))
            reform_value = int(scenario.compute_aggregate(variable, period=self.period, weighted=False))
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

        variables = ["revenu_net_global_imposable", "impot_brut", "impot_net"]
        data = []
        for var in variables:
            baseline = scenario.compute_aggregate(var, period=self.period, use_baseline=True, weighted=False)
            reform = scenario.compute_aggregate(var, period=self.period, weighted=False)
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

        df = scenario.compute_pivot_table(values=["impot_brut"], columns=['parts_fiscales'], period=self.period, difference=True, weighted=False)
        fig = go.Figure(data=[
            go.Bar(x=df.index, y=df[col], name=col)
            for col in df.columns
        ])
        fig.update_layout(
            barmode='group',
            title_text="Répartition des impôts bruts par parts fiscales",
            xaxis_title="Parts Fiscales",
            yaxis_title="Total Impôts Bruts",
            legend_title="Parts Fiscales"
        )
        return fig

    def register_outputs(self, input, output):
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
