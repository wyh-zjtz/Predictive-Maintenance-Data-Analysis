from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# ============================================================
# Configuration
# ============================================================
FILE_PATH = "ai4i2020.csv"
OUTPUT_DIR = Path("analysis_output")
OUTPUT_DIR.mkdir(exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams["axes.unicode_minus"] = False

ID_COL = "UDI"
PRODUCT_ID_COL = "Product ID"
PRODUCT_TYPE_COL = "Type"
FAILURE_COL = "Machine failure"

METRICS = [
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
]

FAULT_COLS = ["TWF", "HDF", "PWF", "OSF", "RNF"]

FAULT_NAME_MAP = {
    "TWF": "Tool Wear Failure",
    "HDF": "Heat Dissipation Failure",
    "PWF": "Power Failure",
    "OSF": "Overstrain Failure",
    "RNF": "Random Failure",
}

# ============================================================
# Helper functions
# ============================================================
def save_dataframe(dataframe, filename, index=False):
    """Save a DataFrame with UTF-8 BOM for spreadsheet compatibility."""
    dataframe.to_csv(
        OUTPUT_DIR / filename,
        index=index,
        encoding="utf-8-sig",
    )

def percentage(numerator, denominator):
    """Return percentage while avoiding division by zero."""
    return numerator / denominator * 100 if denominator else 0

# ============================================================
# 1. Load data and preserve raw dataset dimensions
# ============================================================
df = pd.read_csv(FILE_PATH)
df.columns = df.columns.str.strip()

raw_record_count = len(df)
raw_column_count = df.shape[1]

print("=" * 70)
print("1. DATA QUALITY CHECK")
print("=" * 70)
print(f"Raw dataset shape: {df.shape}")

print("\nColumn data types:")
print(df.dtypes)

missing_values = df.isna().sum().sort_values(ascending=False)
duplicate_count = int(df.duplicated().sum())

print("\nMissing values by column:")
print(missing_values)

print(f"\nDuplicate records: {duplicate_count}")

descriptive_statistics = df.describe(include="all").T

print("\nDescriptive statistics:")
print(descriptive_statistics)

data_quality_summary = pd.DataFrame({
    "column": df.columns,
    "dtype": df.dtypes.astype(str).values,
    "missing_count": df.isna().sum().values,
    "missing_rate_pct": (df.isna().mean().values * 100).round(2),
    "unique_count": df.nunique().values,
})

save_dataframe(data_quality_summary, "data_quality_summary.csv")
save_dataframe(descriptive_statistics, "descriptive_statistics.csv", index=True)

if duplicate_count > 0:
    df = df.drop_duplicates().copy()

# ============================================================
# 2. Statistical anomaly screening
#
# Rule A: outside mean +/- 3 standard deviations
# Rule B: outside the 1st to 99th percentile interval
#
# A metric is flagged if either rule is triggered.
# Statistical anomaly is an initial screening signal only.
# It is not equivalent to confirmed machine failure.
# ============================================================
print("\n" + "=" * 70)
print("2. STATISTICAL ANOMALY SCREENING")
print("=" * 70)

anomaly_summary_rows = []

for metric in METRICS:
    mean_value = df[metric].mean()
    std_value = df[metric].std()

    lower_3sigma = mean_value - 3 * std_value
    upper_3sigma = mean_value + 3 * std_value

    q01 = df[metric].quantile(0.01)
    q99 = df[metric].quantile(0.99)

    sigma_anomaly = (
        (df[metric] < lower_3sigma)
        | (df[metric] > upper_3sigma)
    )

    quantile_anomaly = (
        (df[metric] < q01)
        | (df[metric] > q99)
    )

    anomaly_col = f"{metric}_anomaly"
    df[anomaly_col] = sigma_anomaly | quantile_anomaly

    anomaly_summary_rows.append({
        "metric": metric,
        "mean": round(mean_value, 4),
        "std": round(std_value, 4),
        "lower_3sigma": round(lower_3sigma, 4),
        "upper_3sigma": round(upper_3sigma, 4),
        "q01": round(q01, 4),
        "q99": round(q99, 4),
        "anomaly_count": int(df[anomaly_col].sum()),
        "anomaly_rate_pct": round(df[anomaly_col].mean() * 100, 2),
    })

anomaly_summary = pd.DataFrame(anomaly_summary_rows)
anomaly_flag_cols = [f"{metric}_anomaly" for metric in METRICS]

df["any_statistical_anomaly"] = df[anomaly_flag_cols].any(axis=1)
df["anomaly_metric_count"] = df[anomaly_flag_cols].sum(axis=1)

total_anomaly_count = int(df["any_statistical_anomaly"].sum())
total_anomaly_rate = percentage(total_anomaly_count, len(df))

print("\nAnomaly metric summary:")
print(anomaly_summary)

print(
    f"\nRecords with at least one statistical anomaly: "
    f"{total_anomaly_count} ({total_anomaly_rate:.2f}%)"
)

save_dataframe(anomaly_summary, "anomaly_metric_summary.csv")

# ============================================================
# 3. Statistical risk grouping
#
# The grouping is based on the number of anomalous metrics.
# It is used for review prioritization, not as an official
# machine fault severity level.
# ============================================================
print("\n" + "=" * 70)
print("3. STATISTICAL RISK GROUPING")
print("=" * 70)

df["risk_level"] = pd.cut(
    df["anomaly_metric_count"],
    bins=[-1, 0, 1, 2, float("inf")],
    labels=["Normal", "Low", "Medium", "High"],
)

risk_summary = (
    df.groupby("risk_level", observed=False)
    .agg(
        record_count=(ID_COL, "count"),
        machine_failure_count=(FAILURE_COL, "sum"),
        failure_rate=(FAILURE_COL, "mean"),
        avg_anomaly_metric_count=("anomaly_metric_count", "mean"),
        avg_rotational_speed=("Rotational speed [rpm]", "mean"),
        avg_torque=("Torque [Nm]", "mean"),
        avg_tool_wear=("Tool wear [min]", "mean"),
    )
    .reset_index()
)

risk_summary["failure_rate_pct"] = (
    risk_summary["failure_rate"] * 100
).round(2)

risk_summary["avg_anomaly_metric_count"] = (
    risk_summary["avg_anomaly_metric_count"].round(2)
)

risk_summary = risk_summary.drop(columns=["failure_rate"])

print("\nRisk-level summary:")
print(risk_summary)

save_dataframe(risk_summary, "risk_level_summary.csv")

# All records with at least one anomaly:
# This is the complete initial review pool.
statistical_anomaly_records = (
    df[df["any_statistical_anomaly"]]
    .sort_values(
        by=[
            "anomaly_metric_count",
            "Tool wear [min]",
            "Torque [Nm]",
        ],
        ascending=[False, False, False],
    )
    .copy()
)

save_dataframe(
    statistical_anomaly_records,
    "statistical_anomaly_records.csv",
)

# Multi-signal anomaly records:
# These are a prioritization subset, not the only records that require review.
priority_inspection_records = (
    df[df["risk_level"].isin(["Medium", "High"])]
    .sort_values(
        by=[
            "anomaly_metric_count",
            "Tool wear [min]",
            "Torque [Nm]",
        ],
        ascending=[False, False, False],
    )
    .copy()
)

save_dataframe(
    priority_inspection_records,
    "priority_inspection_records.csv",
)

print(
    f"\nInitial anomaly review pool: "
    f"{len(statistical_anomaly_records)} records"
)

print(
    f"Multi-signal priority review list: "
    f"{len(priority_inspection_records)} records"
)

# ============================================================
# 4. Product type analysis
#
# Type in this dataset represents a product quality variant.
# It should not be interpreted as a physical machine model.
# ============================================================
print("\n" + "=" * 70)
print("4. PRODUCT TYPE ANALYSIS")
print("=" * 70)

product_type_summary = (
    df.groupby(PRODUCT_TYPE_COL)
    .agg(
        record_count=(ID_COL, "count"),
        machine_failure_count=(FAILURE_COL, "sum"),
        failure_rate=(FAILURE_COL, "mean"),
        anomaly_record_count=("any_statistical_anomaly", "sum"),
        anomaly_rate=("any_statistical_anomaly", "mean"),
        avg_air_temperature=("Air temperature [K]", "mean"),
        avg_process_temperature=("Process temperature [K]", "mean"),
        avg_rotational_speed=("Rotational speed [rpm]", "mean"),
        avg_torque=("Torque [Nm]", "mean"),
        avg_tool_wear=("Tool wear [min]", "mean"),
    )
    .reset_index()
)

product_type_summary["failure_rate_pct"] = (
    product_type_summary["failure_rate"] * 100
).round(2)

product_type_summary["anomaly_rate_pct"] = (
    product_type_summary["anomaly_rate"] * 100
).round(2)

product_type_summary = product_type_summary.drop(
    columns=["failure_rate", "anomaly_rate"]
)

print("\nProduct-type summary:")
print(product_type_summary)

save_dataframe(product_type_summary, "product_type_summary.csv")

# ============================================================
# 5. Failure type analysis
#
# A record may have more than one failure label. Therefore,
# the sum of fault-label counts can exceed Machine failure count.
# ============================================================
print("\n" + "=" * 70)
print("5. FAILURE TYPE ANALYSIS")
print("=" * 70)

fault_summary = pd.DataFrame({
    "fault_code": FAULT_COLS,
    "fault_type": [FAULT_NAME_MAP[col] for col in FAULT_COLS],
    "failure_count": [int(df[col].sum()) for col in FAULT_COLS],
})

fault_summary = fault_summary.sort_values(
    by="failure_count",
    ascending=False,
).reset_index(drop=True)

fault_label_total = fault_summary["failure_count"].sum()

fault_summary["share_of_fault_labels_pct"] = (
    fault_summary["failure_count"] / fault_label_total * 100
).round(2)

print("\nFailure-type summary:")
print(fault_summary)

save_dataframe(fault_summary, "failure_type_summary.csv")

# ============================================================
# 6. Normal vs. machine failure comparison
# ============================================================
print("\n" + "=" * 70)
print("6. NORMAL VS FAILURE FEATURE COMPARISON")
print("=" * 70)

normal_vs_failure = (
    df.groupby(FAILURE_COL)[METRICS]
    .mean()
    .T
    .rename(columns={
        0: "normal_mean",
        1: "failure_mean",
    })
)

normal_vs_failure["difference_failure_minus_normal"] = (
    normal_vs_failure["failure_mean"]
    - normal_vs_failure["normal_mean"]
)

normal_vs_failure["change_pct"] = (
    normal_vs_failure["difference_failure_minus_normal"]
    / normal_vs_failure["normal_mean"]
    * 100
).round(2)

print("\nNormal vs. failure mean comparison:")
print(normal_vs_failure)

save_dataframe(
    normal_vs_failure,
    "normal_vs_failure_metric_comparison.csv",
    index=True,
)

# ============================================================
# 7. Validate anomaly screening against machine failure label
#
# Statistical anomaly is not treated as a fault diagnosis.
# This section evaluates its usefulness as an initial screening rule.
# ============================================================
print("\n" + "=" * 70)
print("7. ANOMALY RULE VALIDATION")
print("=" * 70)

validation_crosstab = pd.crosstab(
    df["any_statistical_anomaly"],
    df[FAILURE_COL],
    rownames=["statistical_anomaly"],
    colnames=["machine_failure"],
)

# Ensure all expected rows and columns exist.
validation_crosstab = validation_crosstab.reindex(
    index=[False, True],
    columns=[0, 1],
    fill_value=0,
)

validation_crosstab.index = ["No anomaly", "At least one anomaly"]
validation_crosstab.columns = ["No machine failure", "Machine failure"]

print("\nCross-tabulation:")
print(validation_crosstab)

y_true = df[FAILURE_COL]
y_pred = df["any_statistical_anomaly"].astype(int)

tp = int(((y_pred == 1) & (y_true == 1)).sum())
fp = int(((y_pred == 1) & (y_true == 0)).sum())
fn = int(((y_pred == 0) & (y_true == 1)).sum())
tn = int(((y_pred == 0) & (y_true == 0)).sum())

precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
specificity = tn / (tn + fp) if (tn + fp) > 0 else 0

validation_summary = pd.DataFrame([{
    "true_failure_count": int(y_true.sum()),
    "statistical_anomaly_count": int(y_pred.sum()),
    "true_positive_TP": tp,
    "false_positive_FP": fp,
    "false_negative_FN": fn,
    "true_negative_TN": tn,
    "precision_pct": round(precision * 100, 2),
    "recall_pct": round(recall * 100, 2),
    "specificity_pct": round(specificity * 100, 2),
}])

print("\nAnomaly-rule validation summary:")
print(validation_summary)

save_dataframe(
    validation_crosstab.reset_index(),
    "anomaly_failure_crosstab.csv",
)

save_dataframe(
    validation_summary,
    "anomaly_rule_validation_summary.csv",
)

# ============================================================
# 8. Visualization: process temperature by record index
#
# Important: UDI is a record index, not a timestamp.
# ============================================================
plot_df = df.sort_values(ID_COL)

plt.figure(figsize=(14, 5))

plt.plot(
    plot_df[ID_COL],
    plot_df["Process temperature [K]"],
    color="#c0392b",
    linewidth=0.8,
    label="Process temperature",
)

temperature_anomaly_df = plot_df[
    plot_df["Process temperature [K]_anomaly"]
]

plt.scatter(
    temperature_anomaly_df[ID_COL],
    temperature_anomaly_df["Process temperature [K]"],
    color="black",
    s=14,
    alpha=0.8,
    label="Statistical anomaly",
)

plt.title("Process Temperature by Record Index (UDI)")
plt.xlabel("UDI (record index, not timestamp)")
plt.ylabel("Process temperature [K]")
plt.legend()
plt.grid(alpha=0.25)
plt.tight_layout()

plt.savefig(
    OUTPUT_DIR / "process_temperature_by_record_index.png",
    dpi=180,
)
plt.show()

# ============================================================
# 9. Visualization: rotational speed and torque distributions
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

axes[0].hist(
    df["Rotational speed [rpm]"],
    bins=40,
    color="#2874a6",
    edgecolor="white",
)

axes[0].set_title("Rotational Speed Distribution")
axes[0].set_xlabel("Rotational speed [rpm]")
axes[0].set_ylabel("Record count")
axes[0].grid(axis="y", alpha=0.25)

axes[1].hist(
    df["Torque [Nm]"],
    bins=40,
    color="#ca6f1e",
    edgecolor="white",
)

axes[1].set_title("Torque Distribution")
axes[1].set_xlabel("Torque [Nm]")
axes[1].set_ylabel("Record count")
axes[1].grid(axis="y", alpha=0.25)

plt.tight_layout()

plt.savefig(
    OUTPUT_DIR / "rotational_speed_and_torque_distribution.png",
    dpi=180,
)
plt.show()

# ============================================================
# 10. Visualization: torque and tool wear by failure status
# ============================================================
normal_df = df[df[FAILURE_COL] == 0]
failure_df = df[df[FAILURE_COL] == 1]

plt.figure(figsize=(8, 6))

plt.scatter(
    normal_df["Tool wear [min]"],
    normal_df["Torque [Nm]"],
    s=12,
    alpha=0.25,
    color="#2874a6",
    label="Normal",
)

plt.scatter(
    failure_df["Tool wear [min]"],
    failure_df["Torque [Nm]"],
    s=24,
    alpha=0.85,
    color="#c0392b",
    label="Machine failure",
)

plt.title("Torque vs Tool Wear: Normal and Failure Records")
plt.xlabel("Tool wear [min]")
plt.ylabel("Torque [Nm]")
plt.grid(alpha=0.25)
plt.legend()
plt.tight_layout()

plt.savefig(
    OUTPUT_DIR / "torque_vs_tool_wear_by_failure.png",
    dpi=180,
)
plt.show()

# ============================================================
# 11. Visualization: observed failure rate by risk level
#
# This is an observed rate, not model accuracy or predicted probability.
# ============================================================
risk_plot_df = risk_summary.copy()

plt.figure(figsize=(8, 5))

bars = plt.bar(
    risk_plot_df["risk_level"],
    risk_plot_df["failure_rate_pct"],
    color=["#5dade2", "#f5b041", "#e67e22", "#c0392b"],
)

plt.title("Observed Failure Rate by Statistical Risk Level")
plt.xlabel("Statistical risk level")
plt.ylabel("Observed machine failure rate (%)")
plt.ylim(0, risk_plot_df["failure_rate_pct"].max() + 6)
plt.grid(axis="y", alpha=0.25)

for bar, rate, count in zip(
    bars,
    risk_plot_df["failure_rate_pct"],
    risk_plot_df["record_count"],
):
    plt.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 0.6,
        f"{rate:.2f}%\n(n={count})",
        ha="center",
        va="bottom",
        fontsize=10,
    )

plt.tight_layout()

plt.savefig(
    OUTPUT_DIR / "observed_failure_rate_by_risk_level.png",
    dpi=180,
)
plt.show()

# ============================================================
# 12. Executive summary
# ============================================================
total_failure_count = int(df[FAILURE_COL].sum())
overall_failure_rate = percentage(total_failure_count, len(df))

highest_anomaly_metric = anomaly_summary.loc[
    anomaly_summary["anomaly_rate_pct"].idxmax()
]

highest_failure_product_type = product_type_summary.loc[
    product_type_summary["failure_rate_pct"].idxmax()
]

top_failure_type = fault_summary.iloc[0]

torque_change_pct = float(
    normal_vs_failure.loc["Torque [Nm]", "change_pct"]
)

tool_wear_change_pct = float(
    normal_vs_failure.loc["Tool wear [min]", "change_pct"]
)

speed_change_pct = float(
    normal_vs_failure.loc["Rotational speed [rpm]", "change_pct"]
)

normal_risk_row = risk_summary[
    risk_summary["risk_level"] == "Normal"
].iloc[0]

non_normal_df = df[df["risk_level"] != "Normal"]

non_normal_failure_rate = percentage(
    int(non_normal_df[FAILURE_COL].sum()),
    len(non_normal_df),
)

executive_summary_text = f"""
PREDICTIVE MAINTENANCE DATA ANALYSIS - EXECUTIVE SUMMARY
======================================================================

1. Data Quality
- Raw dataset size: {raw_record_count:,} records and {raw_column_count} source columns.
- Derived analysis fields were added: anomaly flags, anomaly count, and risk level.
- Missing values: {int(missing_values.sum())}.
- Duplicate records: {duplicate_count}.
- UDI is a record index, not a timestamp.
- Product ID is unique per record in this dataset and cannot be used to
  track degradation of a single physical machine over time.

2. Statistical Anomaly Screening
- Rule: mean +/- 3 standard deviations OR outside the 1st/99th percentile.
- Records with at least one statistical anomaly:
  {total_anomaly_count:,} ({total_anomaly_rate:.2f}%).
- Highest anomaly rate:
  {highest_anomaly_metric["metric"]}
  ({highest_anomaly_metric["anomaly_rate_pct"]:.2f}%).
- Statistical anomalies are screening signals, not confirmed failures.

3. Failure Overview
- Machine failure records: {total_failure_count:,}.
- Overall observed machine failure rate: {overall_failure_rate:.2f}%.
- Most frequent fault label:
  {top_failure_type["fault_type"]}
  ({int(top_failure_type["failure_count"])} occurrences).
- Multiple fault labels may be present in one record, so fault-label totals
  can exceed the number of machine failure records.

4. Failure-related Operating Signals
- Failure records show the following mean changes compared with normal records:
  * Torque: {torque_change_pct:.2f}%.
  * Tool wear: {tool_wear_change_pct:.2f}%.
  * Rotational speed: {speed_change_pct:.2f}%.
- Failure records show substantially higher average torque and tool wear than
  normal records. These features are useful for risk screening, but their
  distributions overlap with normal records and should not be used as
  standalone failure criteria.

5. Product Type Comparison
- Product type with the highest observed failure rate:
  {highest_failure_product_type[PRODUCT_TYPE_COL]}
  ({highest_failure_product_type["failure_rate_pct"]:.2f}%).
- Type represents a product-quality variant in this simulated dataset, not a
  physical machine model.

6. Validation of Statistical Anomaly Rule
- Precision: {precision * 100:.2f}%.
- Recall: {recall * 100:.2f}%.
- Specificity: {specificity * 100:.2f}%.
- Observed failure rate in the Normal group:
  {normal_risk_row["failure_rate_pct"]:.2f}%.
- Observed failure rate among all non-Normal groups:
  {non_normal_failure_rate:.2f}%.
- The anomaly rule concentrates higher observed failure rates in non-Normal
  records, but it produces both false positives and false negatives.

7. Risk-level Interpretation
- Statistical risk levels are screening categories, not official fault
  severity labels.
- Observed failure rates do not increase strictly with anomaly count.
- The High group has a small sample size, so its observed rate should not be
  interpreted as a stable estimate without additional data.

8. Maintenance Recommendations
- Include all statistically anomalous records in the initial review pool.
- Use multi-signal anomaly records as one prioritization factor, rather than
  as a standalone fault severity label.
- Combine torque, tool wear, alarm logs, process conditions, and maintenance
  history to determine actual inspection priority.
- Inspect cooling and heat-dissipation components because Heat Dissipation
  Failure is the most frequent failure label.
- Recheck isolated extreme readings by sensor calibration or repeated
  measurement before major maintenance action.
"""

print("\n" + "=" * 70)
print("12. EXECUTIVE SUMMARY")
print("=" * 70)
print(executive_summary_text)

with open(
    OUTPUT_DIR / "executive_summary.txt",
    "w",
    encoding="utf-8",
) as file:
    file.write(executive_summary_text.strip())

print("\nAnalysis completed successfully.")
print(f"All files are saved to: {OUTPUT_DIR.resolve()}")