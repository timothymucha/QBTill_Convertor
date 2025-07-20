import streamlit as st
import pandas as pd
from io import StringIO

st.title("Bank CSV to QuickBooks IIF Generator (Invoice Payments)")

uploaded_file = st.file_uploader("Upload Merchant Bank Statement CSV", type=["csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file, skiprows=6)
        df.columns = df.columns.str.strip()  # Clean up column headers
        df.dropna(subset=['Completion Time'], inplace=True)

        # Convert 'Completion Time' to Date
        df['Date'] = pd.to_datetime(df['Completion Time'], errors='coerce').dt.strftime('%m/%d/%Y')
        df.dropna(subset=['Date'], inplace=True)

        output = StringIO()
        output.write("!TRNS\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO\n")
        output.write("!SPL\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO\n")

        for _, row in df.iterrows():
            date = row['Date']
            paid_in = row.get('Paid In', 0) or 0
            withdrawn = row.get('Withdrawn', 0) or 0
            details = str(row.get('Details', '')).strip()
            name = str(row.get('Other Party Info', '')).strip()
            memo = details

            # 1. RECEIVE PAYMENT (for existing invoices)
            if paid_in > 0:
                output.write(f"TRNS\tPAYMENT\t{date}\tMpesa Till\t{name}\t{paid_in:.2f}\t{memo}\n")
                output.write(f"SPL\tPAYMENT\t{date}\tAccounts Receivable\t{name}\t-{paid_in:.2f}\t{memo}\n")
                output.write("ENDTRNS\n")

            # 2. BANK FEES
            elif withdrawn > 0 and "pay merchant charge" in details.lower():
                output.write(f"TRNS\tGENERAL JOURNAL\t{date}\tMpesa Till\t{name}\t-{withdrawn:.2f}\t{memo}\n")
                output.write(f"SPL\tGENERAL JOURNAL\t{date}\tBank Fees\t{name}\t{withdrawn:.2f}\t{memo}\n")
                output.write("ENDTRNS\n")

            # 3. TRANSFER TO DTB
            elif withdrawn > 0 and details == "Merchant Account to Organization Settlement Account":
                output.write(f"TRNS\tTRANSFER\t{date}\tMpesa Till\t{name}\t-{withdrawn:.2f}\t{memo}\n")
                output.write(f"SPL\tTRANSFER\t{date}\tDiamond Trust Bank\t{name}\t{withdrawn:.2f}\t{memo}\n")
                output.write("ENDTRNS\n")

        st.success("✅ IIF file generated for invoice payments")

        st.download_button(
            label="📥 Download .IIF File",
            data=output.getvalue(),
            file_name="invoice_payments.iif",
            mime="text/plain"
        )

    except Exception as e:
        st.error(f"❌ Failed to process file: {e}")
