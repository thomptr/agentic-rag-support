# Multi-Factor Authentication (MFA) Setup

## What Is MFA?

Multi-factor authentication (MFA) adds a second layer of security to your account. After entering your password, you must provide a second verification method, making it significantly harder for attackers to access your account even if your password is compromised.

## Supported MFA Methods

| Method | Security Level | Recommendation |
|---|---|---|
| Authenticator app (TOTP) | High | Recommended |
| SMS text message | Medium | Acceptable |
| Hardware security key (FIDO2) | Highest | For high-security accounts |
| Backup recovery codes | — | For emergency access only |

## Setting Up an Authenticator App (TOTP)

1. Download an authenticator app (Google Authenticator, Authy, Microsoft Authenticator)
2. Log in to your account
3. Navigate to Settings → Security → Multi-Factor Authentication
4. Click "Add Authenticator App"
5. Scan the QR code with your authenticator app
6. Enter the 6-digit code shown in the app to verify
7. **Save your recovery codes** — displayed once; store them securely

## Setting Up SMS MFA

1. Navigate to Settings → Security → Multi-Factor Authentication
2. Click "Add SMS"
3. Enter your mobile phone number (include country code)
4. Click "Send Verification Code"
5. Enter the 6-digit code received via SMS
6. Click "Verify and Enable"

**Note**: SMS MFA is less secure than authenticator apps. We recommend TOTP if possible.

## Recovery Codes

Recovery codes are one-time-use codes that allow you to access your account if you lose your MFA device:
- 10 recovery codes are provided when MFA is first enabled
- Each code can only be used once
- Store codes in a secure location (password manager, printed and locked away)
- Regenerate codes in Settings → Security → MFA → Recovery Codes if compromised

## Troubleshooting MFA

**Code not working**:
- Ensure your device clock is synced (TOTP is time-sensitive; a 30-second drift causes failures)
- Confirm you're using the correct app entry (you may have multiple accounts)
- Try the next code generated (30-second window)

**Lost your MFA device**:
1. Use a recovery code at the login screen (click "Use recovery code")
2. If you have no recovery codes, contact account support for identity verification
3. Support will verify your identity and disable MFA after a security review (24–48 hour process)

**Phone number changed**:
1. Log in using your authenticator app or recovery code
2. Navigate to Settings → Security → MFA → Remove SMS
3. Add your new phone number

## Disabling MFA

Disabling MFA is allowed but not recommended:
1. Navigate to Settings → Security → Multi-Factor Authentication
2. Click "Disable MFA"
3. Confirm by entering your password and a current MFA code
4. MFA is disabled immediately

**Note**: Enterprise accounts may have MFA enforced by their administrator — individual users cannot disable organization-enforced MFA.
