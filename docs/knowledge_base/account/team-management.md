# Team Management

## Overview

Team management allows account administrators to invite colleagues, assign roles, and control access to the platform. Team seat limits and billing implications depend on your plan.

## Inviting Team Members

1. Go to **Account Settings → Team**
2. Click **Invite Member**
3. Enter the email address and select a role
4. Click **Send Invitation**

The invitee receives an email with a join link valid for 7 days. If they do not accept within 7 days, you can resend the invitation from the **Pending Invitations** tab.

## Roles and Permissions

| Role | Description | Capabilities |
|------|-------------|--------------|
| **Admin** | Full account control | Manage team, billing, API keys, all data, delete account |
| **Member** | Standard contributor | Create/edit/delete own resources, read all shared resources |
| **Viewer** | Read-only access | View all resources; cannot create, edit, or delete |

**Important**: Only Admins can invite or remove team members, change billing settings, or manage API keys.

Each account must have at least one Admin at all times. You cannot remove the last Admin.

## Per-Plan Seat Limits

| Plan | Included Seats | Overage |
|------|---------------|---------|
| Basic | 5 | Not available — must upgrade |
| Professional | 25 | Not available — must upgrade to Enterprise |
| Enterprise | Unlimited | N/A |

If you attempt to invite a member that would exceed your plan's seat limit, you will receive an error prompting you to upgrade your plan.

## Overage Billing (Enterprise)

Enterprise plans with negotiated per-seat pricing are billed based on the maximum number of active seats during the billing period. Seats are counted at the end of each day; the peak seat count for the month is used for billing.

## Removing Team Members

1. Go to **Account Settings → Team**
2. Find the member and click **Remove**
3. Confirm removal

Upon removal:
- The user's access is revoked immediately
- Resources they created remain under the account
- Any API keys they personally created are not automatically revoked — review and revoke them separately in **Settings → Developer → API Keys**
- The seat becomes available immediately for a new invite

## Transferring Account Ownership

To transfer ownership to another Admin:

1. Ensure the target user has the Admin role
2. Go to **Account Settings → Team → Transfer Ownership**
3. Select the new owner and confirm
4. The original owner retains Admin role unless manually changed

Account ownership transfer does not affect billing — invoices continue to be sent to the billing email address on file.

## How Team Changes Affect Billing

- **Adding a member** mid-cycle: No immediate charge on Professional. Enterprise customers are charged based on peak seat count at end of cycle.
- **Removing a member** mid-cycle: The seat becomes available immediately. No credit is issued for the partial period on Professional.
- **Upgrading a plan** to accommodate more seats: Prorated charge applies immediately. See **Subscription Management** for proration details.

## Related Documents

- **Subscription Management**: Plan changes and seat-limit enforcement
- **Account Deletion**: What happens to team members when an account is deleted
- **Permissions Management**: Detailed permission matrix for all features
