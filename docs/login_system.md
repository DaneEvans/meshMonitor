# Multi-User Login System Documentation

## Overview

MeshMonitor supports two UI modes, configurable via `config.yaml`:

- **Simple Mode** (default): Local network deployment, no login required, direct access to all features
- **Online Mode**: Cloud/deployed deployment, login required with user authentication

## Switching Between Modes

Edit `config.yaml` and change the `app.mode` setting:

```yaml
app:
  # UI Mode: 'simple' (local network, no login) or 'online' (deployed, with login)
  mode: "simple"    # Change to "online" for login-protected access
```

### Simple Mode (Local Network)
- **Best for:** Home networks, lab environments, local deployments
- **Features:** No login required, direct mesh network access
- **Config:** `mode: "simple"`

### Online Mode (Deployed/Cloud)
- **Best for:** Cloud deployments, shared hosting, internet-accessible instances
- **Features:** Multi-user login, account management, secure access
- **Config:** `mode: "online"`

## Default Credentials (Online Mode Only)

When running in online mode, a default admin account is automatically created:

- **Username:** `admin`
- **Password:** `admin`

**Important:** Change this password after first login for security!

## How to Use (Online Mode)
### First Login (Online Mode)
1. Open the application at `http://localhost:8080` (or your server IP)
2. You'll see the login screen
3. Enter the default credentials:
   - Username: `admin`
   - Password: `admin`
4. Click "Login"
5. The main application interface will load

### Create Additional Users (Online Mode)
1. On the login screen, click "New user? Create account"
2. Fill in the registration form:
   - **Username:** Must be at least 3 characters
   - **Password:** Must be at least 6 characters
   - **Confirm Password:** Must match the password field
3. Click "Register"
4. You'll be automatically logged in with your new account

### Logout (Online Mode)
- Click the "Logout" button in the top-right corner of the application
- You'll return to the login screen
- Your mesh/MQTT connections will be automatically disconnected

## User Management

### User Storage
User credentials are stored in `users.json` file in the project root:
```json
{
  "admin": {
    "password_hash": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",
    "is_admin": true,
    "created_at": "/path/to/project"
  },
  "user2": {
    "password_hash": "hash_of_password",
    "is_admin": false,
    "created_at": "/path/to/project"
  }
}
```

### Security
- Passwords are hashed using **SHA256** algorithm
- Plain-text passwords are never stored
- Each user has their own isolated session
- Session is cleared when logging out

## Architecture

### New Files

#### `src/gui/user_manager.py`
Manages user authentication and account management:
- Load/save users to `users.json`
- Authenticate users with hashed passwords
- Add new users
- Delete users
- Change passwords
- Check admin privileges

#### `src/gui/login.py`
Login UI template and authentication handler (integrated into main.py)

### Modified Files

#### `src/gui/main.py`
- Integrated login system into the main GUI flow
- Shows login screen before main application
- Tracks current logged-in user
- Provides logout functionality
- Displays current username in header

## Features

✅ **Multi-user Support** - Multiple users can have separate accounts
✅ **User Registration** - Self-service account creation with validation
✅ **Secure Passwords** - SHA256 hashing for password storage
✅ **Session Management** - Automatic session cleanup on logout
✅ **User Display** - Shows current logged-in user in application header
✅ **Admin Accounts** - Support for admin vs regular users (for future use)

## Future Enhancements

Possible improvements for future versions:

1. **Per-user Settings** - Store connection preferences per user
2. **Admin Panel** - Dedicated interface for managing users
3. **User Profiles** - Store preferences (themes, layouts, etc.) per user
4. **Password Reset** - Email-based password recovery
5. **Session Persistence** - Remember login across browser sessions
6. **Audit Logging** - Track login/logout events and user actions
7. **Two-Factor Authentication** - Add 2FA support
8. **LDAP Integration** - Connect to corporate directory servers

## Troubleshooting

### I forgot my password
1. Delete or edit the `users.json` file directly
2. Delete your user entry or reset the password hash
3. The admin user will be recreated with defaults on next start

### How do I delete a user?
Currently, users must be deleted by editing `users.json` and removing the user entry.
Future admin panel will provide UI for this.

### Can I change my password?
Future versions will include a password change feature. Currently:
1. Contact an admin to edit `users.json`
2. Or delete your account and re-register

### Multiple users seeing same data
This is by design. All users currently share the same mesh/MQTT data and settings.
Future versions may support per-user configurations.
