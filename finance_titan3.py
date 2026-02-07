import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from io import BytesIO

st.set_page_config(page_title="Collection Dashboard", layout="wide")

st.title("📊 Collection & Receivables Dashboard")

# ==========================================================
# SIDEBAR
# ==========================================================
st.sidebar.header("📂 Upload & Controls")

uploaded_file = st.sidebar.file_uploader(
    "Upload Collection Excel",
    type=["xlsx"]
)

month_input = st.sidebar.text_input("Enter Month (e.g. Jan-2026)")

page = st.sidebar.radio(
    "Navigate",
    [
        "Overview Dashboard",
        "Executive Performance",
        "Customer & Invoice Drilldown",
        "Action Tracker",
        "Reports & Export"
    ]
)

# ==========================================================
# LOAD DATA
# ==========================================================
if uploaded_file:

    try:
        ar_df = pd.read_excel(uploaded_file, sheet_name="AR_Aging")
        exec_df = pd.read_excel(uploaded_file, sheet_name="Executive_Targets")
        inv_df = pd.read_excel(uploaded_file, sheet_name="Invoice_Details")
    except Exception:
        st.error("❌ Error reading Excel. Check sheet names.")
        st.stop()

    # Clean column names
    for df in [ar_df, exec_df, inv_df]:
        df.columns = df.columns.str.strip()

    if not month_input:
        st.warning("⚠️ Please enter Month to proceed")
        st.stop()

    # Attach month
    ar_df["Month"] = month_input
    exec_df["Month"] = month_input
    inv_df["Month"] = month_input

    # ==========================================================
    # VALIDATION & CALCULATIONS
    # ==========================================================
    aging_cols = [
        "0-30", "31-60", "61-90", "91-120",
        "121-150", "151-180", "181-365", "Above 365"
    ]

    required_ar_cols = ["Customer Name", "Executive Name", "Amount"] + aging_cols
    for col in required_ar_cols:
        if col not in ar_df.columns:
            st.error(f"❌ Missing column in AR_Aging: {col}")
            st.stop()

    ar_df[aging_cols] = ar_df[aging_cols].apply(
        pd.to_numeric, errors="coerce"
    ).fillna(0)

    ar_df["Amount"] = pd.to_numeric(ar_df["Amount"], errors="coerce").fillna(0)

    ar_df["Aging Sum"] = ar_df[aging_cols].sum(axis=1)

    ar_df["Total Outstanding"] = np.where(
        ar_df["Amount"] > 0,
        ar_df["Amount"],
        ar_df["Aging Sum"]
    )

    ar_df[">90 Days"] = ar_df[
        ["91-120", "121-150", "151-180", "181-365", "Above 365"]
    ].sum(axis=1)

    if ar_df.empty:
        st.warning("No data available.")
        st.stop()

    # ==========================================================
    # FILTERS
    # ==========================================================
    executives = ["All"] + sorted(ar_df["Executive Name"].dropna().unique())
    selected_exec = st.sidebar.selectbox("Executive", executives)

    if selected_exec != "All":
        ar_df = ar_df[ar_df["Executive Name"] == selected_exec]
        exec_df = exec_df[exec_df["Executive Name"] == selected_exec]
        inv_df = inv_df[inv_df["Executive Name"] == selected_exec]

# ==========================================================
# PAGE 1 – OVERVIEW DASHBOARD
# ==========================================================
if uploaded_file and page == "Overview Dashboard":

    st.subheader(f"📌 Overview – {month_input}")

    total_outstanding = ar_df["Total Outstanding"].sum()
    overdue_90 = ar_df[">90 Days"].sum()
    overdue_pct = (overdue_90 / total_outstanding * 100) if total_outstanding > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Outstanding", f"₹ {total_outstanding:,.0f}")
    c2.metric("Above 90 Days", f"₹ {overdue_90:,.0f}")
    c3.metric("% Overdue", f"{overdue_pct:.1f}%")
    c4.metric("Customers", ar_df["Customer Name"].nunique())

    st.divider()

    aging_sum = ar_df[aging_cols].sum().reset_index()
    aging_sum.columns = ["Aging Bucket", "Amount"]

    fig = px.bar(
        aging_sum,
        x="Aging Bucket",
        y="Amount",
        title="Aging Distribution",
        text="Amount"
    )

    fig.update_traces(
        texttemplate="₹ %{y:,.0f}",
        hovertemplate="<b>%{x}</b><br>Amount: ₹ %{y:,.0f}<extra></extra>"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("🏆 Top 10 Overdue Customers")

    top10 = ar_df.sort_values(">90 Days", ascending=False).head(10)
    st.dataframe(
        top10[["Customer Name", "Executive Name", "Total Outstanding", ">90 Days"]]
    )

# ==========================================================
# PAGE 2 – EXECUTIVE PERFORMANCE
# ==========================================================
if uploaded_file and page == "Executive Performance":

    st.subheader(f"👤 Executive Performance – {month_input}")

    exec_df["Pending"] = exec_df["Target Amount"] - exec_df["Actual Collected"]
    exec_df["Achievement %"] = (
        exec_df["Actual Collected"] /
        exec_df["Target Amount"].replace(0, np.nan) * 100
    ).fillna(0)

    st.dataframe(exec_df)

    exec_chart = exec_df.groupby("Executive Name", as_index=False)[
        ["Target Amount", "Actual Collected"]
    ].sum()

    fig = px.bar(
        exec_chart,
        x="Executive Name",
        y=["Target Amount", "Actual Collected"],
        barmode="group",
        title="Target vs Actual Collection"
    )

    fig.update_traces(
        hovertemplate="Amount: ₹ %{y:,.0f}<extra></extra>"
    )

    st.plotly_chart(fig, use_container_width=True)

# ==========================================================
# PAGE 3 – CUSTOMER & INVOICE DRILLDOWN
# ==========================================================
if uploaded_file and page == "Customer & Invoice Drilldown":

    st.subheader("🧾 Customer & Invoice Drilldown")

    customer = st.selectbox(
        "Select Customer",
        sorted(inv_df["Customer Name"].dropna().unique())
    )

    cust_inv = inv_df[inv_df["Customer Name"] == customer]

    c1, c2 = st.columns(2)
    c1.metric("Total Outstanding", f"₹ {cust_inv['Outstanding Amount'].sum():,.0f}")
    c2.metric("Invoices", cust_inv["Invoice No"].nunique())

    display_cols = [
        "Customer Name",
        "Invoice No",
        "Invoice Date",
        "Outstanding Amount",
        "Aging Bucket",
        "Executive Name",
        "Remarks"
    ]

    st.dataframe(cust_inv[[c for c in display_cols if c in cust_inv.columns]])

# ==========================================================
# PAGE 4 – ACTION TRACKER
# ==========================================================
if uploaded_file and page == "Action Tracker":

    st.subheader("🚨 Overdue Action Tracker")

    overdue_df = inv_df[
        inv_df["Aging Bucket"].isin(
            ["91-120", "121-150", "151-180", "181-365", "Above 365"]
        )
    ]

    def highlight(row):
        if row["Aging Bucket"] in ["181-365", "Above 365"]:
            return ["background-color:#ffcccc"] * len(row)
        elif row["Aging Bucket"] in ["151-180", "121-150"]:
            return ["background-color:#ffe0b3"] * len(row)
        return [""] * len(row)

    st.dataframe(overdue_df.style.apply(highlight, axis=1))

# ==========================================================
# PAGE 5 – EXPORT
# ==========================================================
if uploaded_file and page == "Reports & Export":

    st.subheader("📤 Export Reports")

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        ar_df.to_excel(writer, index=False, sheet_name="AR Summary")

    st.download_button(
        "Download AR Summary (Excel)",
        data=buffer.getvalue(),
        file_name=f"AR_Summary_{month_input}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Please upload Excel and enter Month to start.")
