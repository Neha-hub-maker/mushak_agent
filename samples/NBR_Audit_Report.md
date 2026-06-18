

# NBR Mushak 9.1 Audit Report
## 1. Executive Summary
- The audit detected 12 HIGH-severity anomalies, 3 MEDIUM-severity anomalies, and 0 LOW-severity anomalies.
- The standard VAT rate of 15% is applicable to all transactions.
- The findings indicate potential non-compliance with the **Value Added Tax and Supplementary Duty Act, 2012** and the **VAT & SD Rules, 2016**.

## 2. Anomalies by Category

### VAT_RATE_MISMATCH
The VAT rate mismatch occurs when the declared VAT rate does not match the standard VAT rate of 15%. This is a HIGH-severity anomaly as it may lead to incorrect input tax credit and potential disallowance under **section 46 of the Value Added Tax and Supplementary Duty Act, 2012**. The affected invoices are INV-S-1003, INV-P-2001, INV-P-2002, INV-P-2003, and INV-S-1003. The VAT payable declared in Mushak 9.1 must equal the VAT actually deposited via valid **Mushak 6.3** challans.

### MISSING_CHALLAN_REF
The missing challan reference occurs when a valid Mushak 6.3 Tax Challan reference is not provided for a purchase invoice. This is a HIGH-severity anomaly as it may lead to disallowance of input tax credit under **section 46 of the Value Added Tax and Supplementary Duty Act, 2012**. The affected invoices are INV-P-2001, INV-P-2002, INV-P-2003, INV-P-2003, and INV-S-1003.

### TOTAL_MISMATCH
The total mismatch occurs when the declared total does not reconcile with the line components. This is a MEDIUM-severity anomaly as it may lead to incorrect input tax credit and potential disallowance under **section 46 of the Value Added Tax and Supplementary Duty Act, 2012**. The affected invoices are INV-S-1004, INV-P-2003, and INV-P-2003.

### TIN_MISSING
The TIN missing occurs when a 12-digit TIN is not provided for a sales invoice. This is a HIGH-severity anomaly as it may lead to disallowance of input tax credit under **section 46 of the Value Added Tax and Supplementary Duty Act, 2012**. The affected invoice is INV-S-1002.

### TIN_FORMAT_INVALID
The TIN format invalid occurs when a TIN does not conform to the 12-digit numeric format. This is a MEDIUM-severity anomaly as it may lead to incorrect input tax credit and potential disallowance under **section 46 of the Value Added Tax and Supplementary Duty Act, 2012**. The affected invoice is INV-P-2002.

### DUPLICATE_INVOICE
The duplicate invoice occurs when an invoice number is repeated within the register. This is a HIGH-severity anomaly as it may lead to disallowance of input tax credit under **section 46 of the Value Added Tax and Supplementary Duty Act, 2012**. The affected invoice is INV-S-1003.

### CROSS_SHEET_INVOICE_COLLISION
The cross-sheet invoice collision occurs when an invoice number is used for both sales and purchase. This is a HIGH-severity anomaly as it may lead to disallowance of input tax credit under **section 46 of the Value Added Tax and Supplementary Duty Act, 2012**. The affected invoice is INV-S-1003.

### NEGATIVE_TOTAL
The negative total occurs when a total is declared as negative. This is a HIGH-severity anomaly as it may lead to incorrect input tax credit and potential disallowance under **section 46 of the Value Added Tax and Supplementary Duty Act, 2012**. The affected invoice is INV-S-1004.

## 3. Corrective Actions
| Invoice No | Source Sheet | Issue Detected | Legal Compliance Action |
| --- | --- | --- | --- |
| INV-S-1002 | sales | TIN_MISSING | Re-issue invoice with a valid 12-digit TIN. |
| INV-S-1003 | sales | VAT_RATE_MISMATCH; DUPLICATE_INVOICE; CROSS_SHEET_INVOICE_COLLISION | Re-issue invoice with the standard VAT rate of 15%, ensure unique invoice numbers, and distinct invoice numbering between sales and purchase. |
| INV-P-2001 | purchase | MISSING_CHALLAN_REF | Provide a valid Mushak 6.3 Tax Challan reference. |
| INV-P-2002 | purchase | MISSING_CHALLAN_REF; TIN_FORMAT_INVALID | Provide a valid Mushak 6.3 Tax Challan reference and a 12-digit numeric TIN. |
| INV-P-2003 | purchase | MISSING_CHALLAN_REF; TOTAL_MISMATCH | Provide a valid Mushak 6.3 Tax Challan reference and ensure the declared total reconciles with the line components. |
| INV-S-1004 | sales | NEGATIVE_TOTAL; TOTAL_MISMATCH | Re-issue invoice with a non-negative total and ensure the declared total reconciles with the line components. |

## 4. Mushak 9.1 Filing Notes
- Mushak 9.1 is filed monthly by the **15th of the following month** under the **VAT & SD Rules, 2016** (specifically Rule 25). Late entries pose statutory interest penalties.
- Input VAT on Mushak 9.1 is admissible **only** against a valid Tax Invoice (Mushak 6.1) from a registered person with a verified 12-digit TIN, backed strictly by a corresponding **Mushak 6.3** tax challan, and must reconcile with the supporting Mushak 6.6 (Purchase & Sales Statement).
- The tax payable declared in Mushak 9.1 must equal the VAT actually deposited via valid **Mushak 6.3** challans; any mismatch is a red-flag for a desk audit under **section 53 of the Value Added Tax and Supplementary Duty Act, 2012**, and may trigger disallowance of input tax credit under **section 46** of the same Act.
