# Permissions Management

## User Roles

Our platform uses role-based access control (RBAC) with the following built-in roles:

| Role | Description | Capabilities |
|---|---|---|
| Owner | Account owner | Full access including billing, can transfer ownership |
| Admin | Organization administrator | User management, settings, all features (no billing) |
| Manager | Team lead | Manage team members, create/delete projects |
| Member | Standard user | Create and edit content within assigned projects |
| Viewer | Read-only user | View content only, no edit capabilities |
| Guest | External collaborator | Limited access to specific shared resources |

## Viewing User Permissions

1. Navigate to Settings → Team → Members
2. Click on a user's name to view their current role and permissions
3. Use the "Permissions" tab to see detailed resource-level permissions

## Assigning and Changing Roles

**Requirements**: You must be an Owner or Admin to change user roles.

1. Navigate to Settings → Team → Members
2. Find the user (search by name or email)
3. Click the role badge next to their name
4. Select the new role from the dropdown
5. Click "Save" — change takes effect immediately

**Restrictions**:
- You cannot assign a role higher than your own
- Only the Owner can grant Admin access
- The Owner role can only be transferred (Settings → Account → Transfer Ownership)

## Inviting New Users

1. Navigate to Settings → Team → Members
2. Click "Invite Member"
3. Enter the email address and select their role
4. Click "Send Invitation"
5. The invitation email is valid for 7 days

## Revoking Access

To remove a user from your organization:
1. Navigate to Settings → Team → Members
2. Find the user
3. Click the "..." menu → "Remove from Organization"
4. Confirm removal
5. The user's session is terminated immediately; they lose all access

**Note**: Removing a user does not delete their created content. Content is reassigned to the admin who removed them.

## Project-Level Permissions

In addition to organization roles, you can set project-specific permissions:
1. Open the project
2. Click Settings (gear icon) → Access
3. Add members with project-specific roles (can be more or less restrictive than their org role)

## Custom Permission Sets (Enterprise)

Enterprise accounts can create custom roles:
1. Navigate to Settings → Team → Roles
2. Click "Create Custom Role"
3. Enable/disable individual permissions
4. Assign the custom role to users like any other role

## Troubleshooting Access Issues

**User cannot access a resource they should have access to**:
1. Verify their organization role has the required permissions
2. Check project-level permissions (may override org role)
3. Confirm their account is active (not suspended)
4. If using SSO, verify their group mappings in the SSO configuration

**Admin cannot manage a specific setting**:
- Some settings are Owner-only (billing, ownership transfer, account deletion)
- Contact the account Owner to make these changes
