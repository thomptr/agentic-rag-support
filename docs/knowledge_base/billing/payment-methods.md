# Payment Methods

## Supported Payment Methods

We support the following payment methods:

| Method | Plans | Notes |
|--------|-------|-------|
| Credit/Debit Card (Visa, Mastercard, Amex, Discover) | All plans | Charged automatically each billing cycle |
| ACH Bank Transfer (US accounts only) | Professional, Enterprise | 3–5 business day processing; must verify bank account first |
| Purchase Order (PO) | Enterprise only | Net-30 invoicing; requires signed contract |

## Adding or Updating Payment Information

1. Go to **Account Settings → Billing → Payment Methods**
2. Click **Add Payment Method**
3. Enter your card details or initiate ACH verification
4. Set the new method as **Primary** to use it for future charges
5. Remove the old payment method if desired

**Credit/debit cards**: Changes take effect immediately for the next billing cycle. If a payment is already processing, the new card will be used on the next attempt.

**ACH transfers**: Bank accounts must be verified with micro-deposits (2–3 business days) before they can be set as primary. ACH is not available for Basic plan customers.

## Payment Security

- All card data is processed by our PCI-compliant payment processor; we do not store raw card numbers
- Card details are tokenized — only the last 4 digits and expiration date are stored on our end
- ACH account numbers are stored using bank-grade encryption
- We comply with **PCI DSS Level 1** requirements

## PCI Compliance Notes

Our platform is certified to **PCI DSS Level 1**, the highest level of payment card industry compliance. This means:

- Cardholder data is never transmitted through our servers unencrypted
- Regular security audits and penetration tests are conducted
- A compliance certificate is available upon request for Enterprise customers

## Failed Payment Consequences

When a payment fails (declined card, insufficient funds, expired card), the following process applies:

### Grace Period

1. **Immediate notification**: You receive an email with the failure reason
2. **Day 1–3**: Automatic retry every 24 hours; account remains fully functional
3. **Day 4–7**: Account enters **restricted mode** — read access only; no new data writes or API calls
4. **Day 8+**: Account is **suspended** — login is blocked; data is retained for 30 days

### Resolving a Failed Payment

1. Update your payment method in **Account Settings → Billing → Payment Methods**
2. Click **Retry Payment** on the failed invoice
3. Once payment succeeds, your account is restored within 15 minutes

### Account Suspension vs. Cancellation

Account suspension due to failed payment is not the same as cancellation. Your data is retained. Once payment is resolved, your account and all data are fully restored.

If an account remains suspended for 30 days without payment resolution, it moves to **scheduled for deletion**. You receive 3 email warnings before deletion occurs.

## Escalation

For payment issues not resolvable through the portal (e.g., bank disputes, PO invoicing questions):

- Email: billing-support@example.com
- Phone (Enterprise only): available in your contract or account portal
- Disputes must be raised within 30 days of the invoice date
