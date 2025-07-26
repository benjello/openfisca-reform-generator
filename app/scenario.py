import pandas as pd
from shiny import ui, render, reactive
from shinywidgets import render_widget
import plotly.express as px


from openfisca_nouvelle_caledonie_data.survey_scenario import DSFSurveyScenario
from openfisca_nouvelle_caledonie_data.aggregates import NouvelleCaledonieAggregates


class AbstractScenarioAnalysis:
    def __init__(self, store_rx, tbs, period):
        self.store_rx = store_rx
        self.tbs = tbs
        self.period = period
        self.scenario = None

    def _get_reform_class(self):
        store = self.store_rx.get()
        return store.get("reform_class")

    def aggregates(self, variables=["revenu_net_global_imposable", "impot_brut", "impot_net"], ignore_labels=False):
        scenario = self._create_scenario()
        aggregates = NouvelleCaledonieAggregates(scenario)
        aggregates_df = aggregates.get_data_frame(default="baseline", ignore_labels=ignore_labels)
        return aggregates_df

class ScenarioAnalysis(AbstractScenarioAnalysis):
    def __init__(self, store_rx, tbs, period):
        super().__init__(store_rx, tbs, period)

    def _create_scenario(self):
        reform_class = self._get_reform_class()
        if reform_class:
            if self.scenario is not None:
                return self.scenario

            self.scenario = DSFSurveyScenario(self.period, reform=reform_class)
            print(f"Scenario created with reform class: {reform_class.__name__}")
        else:
            self.scenario = DSFSurveyScenario(self.period)
        return self.scenario

    def render_aggregates(self):
        return self.aggregates()

    def render_aggregates_plot(self, measure: str = "beneficiaries"):
        """
        Render a bar plot for either 'beneficiaries' or 'amount' aggregates.
        measure: "beneficiaries" or "amount"
        """
        scenario = self._create_scenario()
        if not scenario:
            return None

        aggregates_df = self.aggregates(ignore_labels=True)
        df = pd.wide_to_long(
            aggregates_df,
            i=["label", "entity"],
            j="type",
            stubnames=["baseline", "reform", "relative_difference", "absolute_difference"],
            sep="_",
            suffix=r'\w+'
        ).reset_index()
        df_melted = df.melt(
            id_vars=["label", "type"],
            value_vars=["baseline", "reform", "absolute_difference"],
            var_name="simulation",
            value_name="value"
        ).astype({'value': 'float'})
        fig = px.bar(
            df_melted[df_melted["type"] == measure],
            x="value",
            y="label",
            color="simulation",
            barmode="group",
            orientation="h",
            title=f"Baseline vs Reform : {'Bénéficiaires' if measure == 'beneficiaries' else 'Montant'}"
        )
        fig.update_xaxes(title_text="Bénéficiaires" if measure == "beneficiaries" else "Montant")
        fig.update_yaxes(title_text=None)
        return fig

    def render_scenario_pivot_plot(self):
        scenario = self._create_scenario()
        if not scenario:
            return None

        df = scenario.compute_pivot_table(values=["impot_brut"], columns=['parts_fiscales'], period=self.period, difference=True, weighted=False)
        df_reset = df.reset_index()
        df_melted = df_reset.melt(id_vars=df_reset.columns[0], var_name="Parts Fiscales", value_name="Total Impôts Bruts")
        print(df_melted)  # Debugging line to check the DataFrame structure
        fig = px.bar(
            df_melted,
            x=df_reset.columns[0],
            y="Total Impôts Bruts",
            color="Parts Fiscales",
            barmode="group",
            title="Répartition des impôts bruts par parts fiscales",
            labels={df_reset.columns[0]: "Parts Fiscales", "Total Impôts Bruts": "Total Impôts Bruts"}
        )
        fig.update_layout(
            xaxis_title="Parts Fiscales",
            yaxis_title="Total Impôts Bruts",
            legend_title="Parts Fiscales"
        )
        return fig

    def register_outputs(self, input, output):

        @output
        @render.data_frame
        def aggregates_table():
            aggregates_df = self.render_aggregates()
            return render.DataTable(aggregates_df, filters=True, width="100%")

        @output
        @render_widget
        def aggregates_amounts_plot():
            return self.render_aggregates_plot(measure="amount")

        @output
        @render_widget
        def aggregates_beneficiaries_plot():
            return self.render_aggregates_plot(measure="beneficiaries")

        @output
        @render_widget
        def scenario_pivot_plot():
            return self.render_scenario_pivot_plot()
