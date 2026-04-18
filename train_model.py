import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
import os

# -----------------------------
# 1. Load Dataset
# -----------------------------
def load_data(filepath):
    columns = [
        "age",
        "workclass",
        "fnlwgt",
        "education",
        "education_num",
        "marital_status",
        "occupation",
        "relationship",
        "race",
        "sex",
        "capital_gain",
        "capital_loss",
        "hours_per_week",
        "native_country",
        "income"
    ]

    df = pd.read_csv(filepath, names=columns)

    # Strip spaces
    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

    # Replace ? with NaN
    df.replace("?", np.nan, inplace=True)

    # Drop missing
    df.dropna(inplace=True)

    # Drop unnecessary column
    df.drop(columns=["fnlwgt"], inplace=True)

    return df


# -----------------------------
# 2. Preprocess Data
# -----------------------------
def preprocess_data(df):
    X = df.drop("income", axis=1)
    y = df["income"].map({"<=50K": 0, ">50K": 1})

    categorical_cols = X.select_dtypes(include=["object"]).columns

    X_encoded = pd.get_dummies(X, columns=categorical_cols, drop_first=True)

    return X_encoded, y


# -----------------------------
# 3. Train Model
# -----------------------------
def train_model(X, y):
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    model = XGBClassifier(
        subsample=0.8,
        n_estimators=300,
        max_depth=8,
        learning_rate=0.05,
        gamma=0.1,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric='logloss'
    )

    model.fit(X_train, y_train)

    return model, X.columns


# -----------------------------
# 4. Save Model
# -----------------------------
def save_model(model, feature_columns, model_path="models/trained_model.pkl"):
    os.makedirs("models", exist_ok=True)

    joblib.dump({
        "model": model,
        "features": feature_columns
    }, model_path)

    print(f"Model saved successfully at {model_path}")


# -----------------------------
# 5. Main Execution
# -----------------------------
if __name__ == "__main__":
    data_path = "datas/adult.csv"

    df = load_data(data_path)
    X, y = preprocess_data(df)
    model, feature_columns = train_model(X, y)

    save_model(model, feature_columns)
