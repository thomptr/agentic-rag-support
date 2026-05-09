# Subscription Management

## Overview

This guide covers how to change your subscription plan, understand billing cycle adjustments, and how your plan tier affects account permissions and API usage.

## Changing Your Plan

### Upgrading Your Plan

Upgrades take effect immediately.

1. Go to **Account Settings → Billing → Plan**
2. Select your desired plan and click **Upgrade**
3. A prorated charge is applied for the remainder of the current billing period

**Example**: If you are on the Basic plan at $9.99/month and upgrade to Professional ($29.99/month) on day 15 of a 30-day billing cycle, you are charged approximately $10.00 for the remaining 15 days at the Professional rate, minus the unused $5.00 from your Basic plan.

### Downgrading Your Plan

Downgrades take effect at the **end of the current billing period**.

- You retain access to higher-tier features until the period ends
- No immediate refund is issued
- Your next invoice reflects the lower plan price

### Canceling a Subscription

Cancellation is distinct from downgrading. See the **Cancellation Terms** document for the full cancellation policy, data retention details, and final invoice information.

## Billing Cycle Adjustments

- Your billing cycle date is set at the time of your initial subscription
- When you upgrade, your billing cycle date does not change — only a prorated charge is added
- Downgrading does not change your cycle date
- Annual subscribers: upgrades within the annual period generate a prorated invoice; the annual renewal date remains unchanged

## Prorated Charges

Prorated charges appear on your invoice as a line item labeled **"Plan upgrade — prorated"**. The calculation:

```
Daily rate = (new plan price - old plan price) / days in billing period
Prorated charge = daily rate × remaining days in period
```

If the prorated amount is less than $0.50, it is rounded up to $0.50 (minimum charge).

## How Plan Tier Affects Account Permissions

| Feature | Basic | Professional | Enterprise |
|---------|-------|-------------|------------|
| Team seats | 5 | 25 | Unlimited |
| API access | No | Yes | Yes |
| Webhook endpoints | 0 | 5 | Unlimited |
| Data export | Manual (CSV) | Scheduled (CSV/JSON) | Full API + scheduled |
| Audit logs | No | 30-day retention | 1-year retention |
| SSO/SAML | No | No | Yes |

## How Plan Tier Affects API Rate Limits

API rate limits are tied to your plan. See the **Rate Limits** document for per-plan limits and how to handle 429 responses.

- **Basic**: No API access
- **Professional**: 300 requests/minute, 100,000 requests/day
- **Enterprise**: Custom limits; contact your account manager

Upgrading your plan takes effect for API rate limits immediately upon plan change.

## Escalation

If you believe a prorated charge is incorrect, or your plan change did not apply correctly:

1. Check your invoice in **Account Settings → Billing → Invoices**
2. Contact billing support with your invoice number and the expected versus actual charge
3. Billing disputes must be raised within 30 days of the invoice date
