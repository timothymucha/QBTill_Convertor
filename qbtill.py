import streamlit as st
import pandas as pd
from io import StringIO
from datetime import datetime

st.set_page_config(page_title="Bank Statement to QuickBooks IIF", layout="wide")

st.title("📄 Convert Bank Statement to QuickBooks IIF")

uploaded_file = st.file_uploader("Upload bank statement (.csv or .xlsx)", type=["csv", "xlsx"])

if uploaded_file:
    try:
        # Drop first 6 rows (metadata) before reading
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, skiprows=6)
        else:
            df = pd.read_excel(uploaded_file, skiprows=6)

        # Show data preview
        st.subheader("🔍 Preview of Uploaded Data (First 5 Rows)")
        st.dataframe(df.head())

        # Clean column names and ensure types
        df.columns = [col.strip() for col in df.columns]
        df['Completion Time'] = pd.to_datetime(df['Completion Time'], errors='coerce')
        df['Paid In'] = pd.to_numeric(df['Paid In'], errors='coerce').fillna(0)
        df['Withdrawn'] = pd.to_numeric(df['Withdrawn'], errors='coerce').fillna(0)

        # Initialize IIF output
        output = StringIO()
        output.write("!TRNS\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO\n")
        output.write("!SPL\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO\n")
        output.write("!ENDTRNS\n")

        for _, row in df.iterrows():
            date_str = row['Completion Time'].strftime('%m/%d/%Y') if pd.notnull(row['Completion Time']) else None
            if not date_str:
                continue  # Skip rows without valid dates

            details = str(row.get("Details", "")).strip()
            memo = details
            name = str(row.get("Other Party Info", "")).strip()

            if row['Paid In'] > 0:
                # Customer Payment
                amount = row['Paid In']
                output.write(f"TRNS\tPAYMENT\t{date_str}\tMpesa Till\t{name}\t{amount:.2f}\t{memo}\n")
                output.write(f"SPL\tPAYMENT\t{date_str}\tAccounts Receivable\t{name}\t{-amount:.2f}\t{memo}\n")
                output.write("ENDTRNS\n")

            elif "merchant account to organization settlement account" in details.lower():
                # DTB Transfer
                amount = abs(row['Withdrawn'])
                output.write(f"TRNS\tTRANSFER\t{date_str}\tMpesa Till\tDiamond Trust Bank\t{-amount:.2f}\t{memo}\n")
                output.write(f"SPL\tTRANSFER\t{date_str}\tDiamond Trust Bank\tMpesa Till\t{amount:.2f}\t{memo}\n")
                output.write("ENDTRNS\n")

            elif row['Withdrawn'] < 0:
                # Bank Fee
                amount = abs(row['Withdrawn'])
                output.write(f"TRNS\tCHECK\t{date_str}\tMpesa Till\tBank Charges\t{-amount:.2f}\t{memo}\n")
                output.write(f"SPL\tCHECK\t{date_str}\tBank Service Charges\t\t{amount:.2f}\t{memo}\n")
                output.write("ENDTRNS\n")

        # Download link
        st.success("✅ IIF file generated successfully!")
        st.download_button("📥 Download IIF File", data=output.getvalue(), file_name="bank_transactions.iif", mime="text/plain")

    except Exception as e:
        st.error(f"❌ Error processing file: {e}")
else:
    st.info("👆 Please upload a bank statement file to begin.")
