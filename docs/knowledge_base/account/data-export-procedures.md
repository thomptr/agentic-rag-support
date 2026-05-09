# Data Export Procedures

## Overview

You can export your account data at any time. Exports are useful for backups, migrations, and compliance purposes. We strongly recommend exporting your data before canceling your account.

## Export Formats

| Format | Contents | Plans |
|--------|----------|-------|
| **CSV** | Tabular data (resources, users, activity logs) | All plans |
| **JSON** | Full structured export including all metadata | Professional, Enterprise |

CSV exports are suitable for spreadsheet analysis. JSON exports include complete data fidelity and are recommended for migrations or re-importing to another platform.

## Requesting a Full Export via Dashboard

1. Go to **Account Settings → Data → Export**
2. Select the export format (CSV or JSON)
3. Optionally select a date range to limit the export
4. Click **Request Export**
5. You receive an email notification when the export is ready (see processing times below)
6. Download the file from **Account Settings → Data → Export History** within 7 days

Exports are available for download for **7 days** after generation. After that, you must request a new export.

## Requesting a Full Export via API

Professional and Enterprise customers can trigger exports programmatically:

```bash
# Request export
curl -X POST https://api.example.com/v1/exports \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"format": "json", "include": ["resources", "users", "logs"]}'

# Returns:
# { "export_id": "exp_abc123", "status": "pending", "estimated_ready_at": "..." }

# Check status
curl https://api.example.com/v1/exports/exp_abc123 \
  -H "Authorization: Bearer YOUR_API_KEY"

# Download when ready
curl https://api.example.com/v1/exports/exp_abc123/download \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -o export.json
```

## Export Size Limits and Processing Time

| Account Size | Estimated Processing Time |
|-------------|--------------------------|
| < 10,000 records | < 5 minutes |
| 10,000 – 100,000 records | 15–60 minutes |
| 100,000 – 1,000,000 records | 2–6 hours |
| > 1,000,000 records | Up to 24 hours |

For very large accounts, you will receive email updates as the export progresses. If an export takes longer than 24 hours, contact support.

## Partial and Filtered Exports

You can export specific subsets of your data:

**By data type**:
- Resources only
- Users and roles only
- Activity/audit logs only
- Billing history only

**By date range**:
- Set start and end dates in the dashboard or API request

**By project/workspace** (Professional and Enterprise):
- Select specific workspaces to include

Partial exports are faster than full exports and are useful when you only need a specific data set.

## Recommendation: Export Before Cancellation

**We strongly recommend exporting all your data before canceling your account.** After cancellation:

- Account access is retained for the remainder of the paid billing period
- After the billing period ends, your account enters a **90-day retention window**
- During the retention window, you can still log in and export data
- After 90 days, all data is **permanently deleted** and cannot be recovered

See **Account Deletion** for the full data retention and deletion policy.

## Related Documents

- **Account Deletion**: Permanent deletion process and 90-day retention window
- **Cancellation Terms**: What happens when you cancel vs. delete your account
- **Subscription Management**: How to change or cancel your plan
