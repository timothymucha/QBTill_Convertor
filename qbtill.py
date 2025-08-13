import streamlit as st
import pandas as pd
from io import StringIO
from datetime import datetime

st.set_page_config(page_title="Mnarani Mpesa Statement to QuickBooks IIF", layout="wide")
st.title("📄 Convert Mnarani Mpesa Statement to QuickBooks IIF")

uploaded_file = st.file_uploader("Upload Mpesa statement (.csv or .xlsx)", type=["csv", "xlsx"])

if uploaded_file:
    try:
        # Drop first 6 rows (metadata) before reading
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, skiprows=6)
        else:
            df = pd.read_excel(uploaded_file, skiprows=6)

        # Normalize and clean column names
        df.columns = df.columns.str.strip().str.replace(r"\s+", " ", regex=True)

        # Required columns
        required_cols = {'Completion Time', 'Paid In', 'Withdrawn', 'Details', 'Other Party Info'}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
            st.stop()

        # Preview uploaded data
        st.subheader("🔍 Preview of Uploaded Data (First 5 Rows)")
        st.dataframe(df.head())

        # Data type conversions
        df['Completion Time'] = pd.to_datetime(df['Completion Time'], errors='coerce')
        df['Paid In'] = pd.to_numeric(df['Paid In'], errors='coerce').fillna(0)
        df['Withdrawn'] = pd.to_numeric(df['Withdrawn'], errors='coerce').fillna(0)
        df['Details'] = df['Details'].astype(str)
        df['Other Party Info'] = df['Other Party Info'].astype(str)

        # Initialize IIF output
        output = StringIO()
        output.write("!TRNS\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO\n")
        output.write("!SPL\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO\n")
        output.write("!ENDTRNS\n")

        # 1️⃣ Payments from Walk In
        payments_df = df[df['Paid In'] > 0]
        for _, row in payments_df.iterrows():
            date_str = row['Completion Time'].strftime('%m/%d/%y')
            memo = f"{row['Other Party Info']} | {row['Details']}".strip(" |")
            amount = row['Paid In']

            output.write(f"TRNS\tPAYMENT\t{date_str}\tMpesa Till\tWalk In\t{amount:.2f}\t{memo}\n")
            output.write(f"SPL\tPAYMENT\t{date_str}\tAccounts Receivable\tWalk In\t{-amount:.2f}\t{memo}\n")
            output.write("ENDTRNS\n")

        # 2️⃣ DTB Transfers
        transfers_df = df[df['Details'].str.lower().str.contains("merchant account to organization settlement account")]
        for _, row in transfers_df.iterrows():
            date_str = row['Completion Time'].strftime('%m/%d/%y')
            memo = f"{row['Other Party Info']} | {row['Details']}".strip(" |")
            amount = abs(row['Withdrawn'])

            output.write(f"TRNS\tTRANSFER\t{date_str}\tMpesa Till\tDiamond Trust Bank\t{-amount:.2f}\t{memo}\n")
            output.write(f"SPL\tTRANSFER\t{date_str}\tDiamond Trust Bank\tMpesa Till\t{amount:.2f}\t{memo}\n")
            output.write("ENDTRNS\n")

        # 3️⃣ Pay merchant Charge → summarized by date
        charges_df = df[df['Details'].str.strip().str.lower() == "pay merchant charge"]
        charges_summary = charges_df.groupby(charges_df['Completion Time'].dt.date)['Withdrawn'].sum().reset_index()

        for _, row in charges_summary.iterrows():
            date_str = pd.to_datetime(row['Completion Time']).strftime('%m/%d/%y')
            memo = "Pay merchant Charge summary"
            amount = row['Withdrawn']

            output.write(f"TRNS\tCHECK\t{date_str}\tMpesa Till\tBank Charges - Mpesa\t{-amount:.2f}\t{memo}\n")
            output.write(f"SPL\tCHECK\t{date_str}\tBank Service Charges:Bank Charges - Mpesa\t\t{amount:.2f}\t{memo}\n")
            output.write("ENDTRNS\n")

        # 4️⃣ Other Withdrawals → Bank Service Charges generic
        other_withdrawals = df[
            (df['Withdrawn'] > 0) &
            (~df['Details'].str.lower().str.contains("merchant account to organization settlement account")) &
            (~df['Details'].str.strip().str.lower().eq("pay merchant charge"))
        ]
        for _, row in other_withdrawals.iterrows():
            date_str = row['Completion Time'].strftime('%m/%d/%y')
            memo = f"{row['Other Party Info']} | {row['Details']}".strip(" |")
            amount = row['Withdrawn']

            output.write(f"TRNS\tCHECK\t{date_str}\tMpesa Till\tBank Charges\t{-amount:.2f}\t{memo}\n")
            output.write(f"SPL\tCHECK\t{date_str}\tBank Service Charges\t\t{amount:.2f}\t{memo}\n")
            output.write("ENDTRNS\n")

        # Totals
        st.markdown(f"**Total Paid In:** KES {payments_df['Paid In'].sum():,.2f}")
        st.markdown(f"**Total Withdrawn:** KES {df['Withdrawn'].sum():,.2f}")
        st.markdown(f"**Total 'Pay merchant Charge':** KES {charges_df['Withdrawn'].sum():,.2f}")

        # Download button
        st.success("✅ IIF file generated successfully!")
        st.download_button("📥 Download IIF File", data=output.getvalue(), file_name="mpesa_transactions.iif", mime="text/plain")

    except Exception as e:
        st.error(f"❌ Error processing file: {e}")

else:
    st.info("👆 Please upload a bank statement file to begin.")
