# Login Procedures

## Standard Login

1. Go to app.example.com
2. Enter your registered email address
3. Enter your password
4. Click "Sign In"
5. Complete MFA verification if enabled

## Password Reset

If you've forgotten your password:

1. Click "Forgot password?" on the login page
2. Enter your registered email address
3. Check your email for a password reset link (expires in 1 hour)
4. Click the link and enter a new password
5. Password requirements:
   - Minimum 12 characters
   - At least one uppercase letter
   - At least one number
   - At least one special character (!@#$%^&*)

**Did not receive the email?**
- Check your spam/junk folder
- Verify you're using the correct email address
- Allow up to 5 minutes for delivery
- If still not received, contact account support

## Locked Account

Your account is locked after 10 consecutive failed login attempts. The lock lasts 30 minutes automatically.

To unlock immediately:
1. Click "Unlock Account" on the login error page
2. Follow the email verification link sent to your registered address
3. Once verified, reset your password before logging in again

## Troubleshooting Login Issues

**"Invalid email or password" error**:
- Verify your email address is typed correctly
- Check Caps Lock is not enabled
- Try a password reset if unsure of your password

**Account shows as inactive**:
- Your account subscription may have lapsed — check billing status
- Your account may have been deactivated by an admin — contact your organization admin

**Can't access the login page**:
- Clear your browser cache and cookies
- Try a different browser or incognito mode
- Check your network/firewall settings (see Troubleshooting Guide)

## Single Sign-On (SSO)

Enterprise accounts may use SSO via SAML 2.0 or OIDC:
1. Navigate to your company's SSO portal
2. Click the tile for our application
3. You are authenticated through your identity provider and logged in automatically

If SSO fails, contact your IT administrator — they manage SSO configuration.

## Supported Authentication Methods

| Method | Available For |
|---|---|
| Email + password | All plans |
| SSO/SAML 2.0 | Enterprise only |
| SSO/OIDC (Google, Microsoft) | Professional and Enterprise |
| Social login (Google) | Individual accounts |
