import joblib
import pandas as pd
import shap


class WelfarePredictor:

    def __init__(self, model_path="models/trained_model.pkl"):
        saved = joblib.load(model_path)
        self.model = saved["model"]
        self.feature_columns = saved["features"]

        # Initialize SHAP explainer
        self.explainer = shap.TreeExplainer(self.model)

    def preprocess_input(self, input_data):
        """
        input_data: dictionary of user inputs
        """

        df = pd.DataFrame([input_data])

        # One-hot encode
        df_encoded = pd.get_dummies(df)

        # Align columns with training data
        df_encoded = df_encoded.reindex(columns=self.feature_columns, fill_value=0)

        return df_encoded

    def predict(self, input_data):
        processed = self.preprocess_input(input_data)

        prediction = self.model.predict(processed)[0]
        probability = self.model.predict_proba(processed)[0][1]

        return prediction, probability, processed

    def explain(self, processed_input):
        shap_values = self.explainer.shap_values(processed_input)

        shap_contributions = pd.DataFrame({
            "feature": processed_input.columns,
            "impact": shap_values[0]
        })

        shap_contributions["abs_impact"] = shap_contributions["impact"].abs()

        top_features = shap_contributions.sort_values(
            by="abs_impact",
            ascending=False
        ).head(5)

        return top_features[["feature", "impact"]]
