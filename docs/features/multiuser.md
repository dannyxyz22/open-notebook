# Multiuser Support

Open Notebook now supports multiple users with individual accounts, allowing teams and organizations to use a shared Open Notebook instance while keeping their research data private and isolated.

## Overview

The multiuser feature provides:
- **Individual user accounts** with username/password authentication
- **JWT-based authentication** for secure API access
- **Data isolation** - each user can only see and access their own notebooks, sources, and notes
- **Backward compatibility** - existing single-user installations continue to work without changes
- **Seamless migration** - existing data is automatically assigned to a default admin user

## Architecture

### Authentication Flow

1. **User Registration**: New users create accounts with username, email, and password
2. **Login**: Users authenticate with username/email and password
3. **JWT Token**: Upon successful login, users receive a JWT access token
4. **API Requests**: All API requests include the JWT token in the Authorization header
5. **User Context**: The middleware validates the token and sets the user context for each request
6. **Data Filtering**: All database queries automatically filter by the current user

### User Model

Each user has:
- `username`: Unique username (3-50 characters, alphanumeric with underscore and hyphen)
- `email`: Unique email address
- `password_hash`: Bcrypt-hashed password (never stored in plain text)
- `full_name`: Optional full name
- `is_active`: Whether the account is active (inactive users cannot login)
- `is_admin`: Admin flag (for future use)
- `last_login`: Timestamp of last successful login

### Data Ownership

All user-created resources (notebooks, sources, notes) are associated with the user who created them:
- Each notebook, source, and note has a `user` field linking to the creator
- Users can only view, edit, and delete their own resources
- In single-user mode (backward compatibility), the `user` field is `None` and all resources are accessible

## Setup and Configuration

### Environment Variables

```bash
# JWT Secret Key (REQUIRED for production)
JWT_SECRET_KEY=your-secure-random-secret-key-here

# JWT Token Expiration (default: 168 hours = 7 days)
JWT_EXPIRATION_HOURS=168

# Optional: Keep old password auth for backward compatibility
OPEN_NOTEBOOK_PASSWORD=your-old-password
```

**Important**: In production, always set a strong, randomly generated `JWT_SECRET_KEY`. You can generate one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Docker Compose Example

```yaml
services:
  open_notebook:
    image: lfnovo/open_notebook:v1-latest-single
    ports:
      - "8502:8502"
      - "5055:5055"
    environment:
      - OPENAI_API_KEY=your_key_here
      - JWT_SECRET_KEY=your-secure-random-secret-key-here
      - JWT_EXPIRATION_HOURS=168
      - SURREAL_URL=ws://localhost:8000/rpc
      - SURREAL_USER=root
      - SURREAL_PASSWORD=root
      - SURREAL_NAMESPACE=open_notebook
      - SURREAL_DATABASE=production
    volumes:
      - ./notebook_data:/app/data
      - ./surreal_data:/mydata
    restart: always
```

## Migration from Single-User

When upgrading from a single-user installation:

1. **Automatic Migration**: On first startup with the multiuser migration, all existing data is automatically assigned to a default admin user:
   - Username: `admin`
   - Email: `admin@localhost`
   - Password: `admin` (CHANGE THIS IMMEDIATELY!)

2. **Login as Admin**: Use the default credentials to login for the first time

3. **Change Password**: Immediately change the admin password via the API:
   ```bash
   curl -X POST http://localhost:5055/api/auth/change-password \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"current_password": "admin", "new_password": "your-secure-password"}'
   ```

4. **Create User Accounts**: Register additional user accounts as needed

## API Usage

### Register a New User

```bash
POST /api/auth/register
Content-Type: application/json

{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "secure-password",
  "full_name": "John Doe"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "user:abc123",
    "username": "johndoe",
    "email": "john@example.com",
    "full_name": "John Doe",
    "is_active": true,
    "is_admin": false,
    "last_login": "2024-01-01T12:00:00Z",
    "created": "2024-01-01T12:00:00Z",
    "updated": "2024-01-01T12:00:00Z"
  }
}
```

### Login

```bash
POST /api/auth/login
Content-Type: application/json

{
  "username": "johndoe",
  "password": "secure-password"
}
```

**Response:** Same as registration (includes token and user info)

### Using the Token

Include the JWT token in the Authorization header for all API requests:

```bash
GET /api/notebooks
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Get Current User Profile

```bash
GET /api/auth/me
Authorization: Bearer YOUR_TOKEN
```

### Update Profile

```bash
PUT /api/auth/me
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "email": "newemail@example.com",
  "full_name": "John M. Doe"
}
```

### Change Password

```bash
POST /api/auth/change-password
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "current_password": "old-password",
  "new_password": "new-secure-password"
}
```

## Security Best Practices

### For Administrators

1. **Strong JWT Secret**: Always use a strong, randomly generated JWT secret key in production
2. **HTTPS**: Use HTTPS (TLS/SSL) in production to protect tokens in transit
3. **Token Expiration**: Configure an appropriate token expiration time (default: 7 days)
4. **Change Default Password**: If migrating from single-user, change the default admin password immediately
5. **Backup Database**: Regular backups of the SurrealDB database protect user data

### For Users

1. **Strong Passwords**: Use passwords with at least 6 characters (longer is better)
2. **Unique Passwords**: Don't reuse passwords from other services
3. **Secure Storage**: Store your JWT tokens securely (browser local storage is used by the frontend)
4. **Logout**: Logout when done, especially on shared computers

## Backward Compatibility

Open Notebook maintains full backward compatibility with existing installations:

### Old Password Authentication

If you have `OPEN_NOTEBOOK_PASSWORD` set, it continues to work:
- Requests with the old password in the Bearer token are accepted
- These requests have no user context (act as single-user mode)
- All resources are accessible regardless of owner

### Single-User Mode

If no users exist in the database:
- The system operates in single-user mode
- No authentication is required (unless `OPEN_NOTEBOOK_PASSWORD` is set)
- All resources are accessible to everyone

### Upgrading Safely

1. **Test First**: Test the upgrade on a non-production instance
2. **Backup Data**: Always backup your SurrealDB data directory before upgrading
3. **Verify Migration**: After upgrade, verify that the admin user exists and all data is accessible
4. **Update Clients**: Update any API clients to use JWT authentication

## Troubleshooting

### "Invalid token" errors

- **Cause**: Token expired, invalid, or JWT secret changed
- **Solution**: Login again to get a new token

### "Access denied" errors

- **Cause**: Trying to access resources owned by another user
- **Solution**: Verify you're accessing your own resources or contact the resource owner

### Cannot login with admin account after migration

- **Cause**: Migration may have failed or admin user not created
- **Solution**: Check logs, ensure database migration ran successfully

### Token expires too quickly

- **Cause**: JWT_EXPIRATION_HOURS is too low
- **Solution**: Increase JWT_EXPIRATION_HOURS environment variable

## Limitations and Future Enhancements

### Current Limitations

- **No sharing**: Users cannot share notebooks or sources with other users
- **No admin panel**: No web UI for user management (API only)
- **No password reset**: Users cannot reset forgotten passwords (must contact admin)
- **No email verification**: Email addresses are not verified

### Planned Enhancements

- **Sharing**: Share notebooks and sources with specific users or teams
- **Teams**: Group users into teams with shared resources
- **Admin Dashboard**: Web UI for user management
- **Password Reset**: Self-service password reset via email
- **Email Verification**: Verify email addresses during registration
- **OAuth**: Login with Google, GitHub, etc.
- **Audit Logs**: Track user actions for compliance and debugging

## API Reference

### Authentication Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/status` | GET | Check authentication status |
| `/api/auth/register` | POST | Register new user |
| `/api/auth/login` | POST | Login and get token |
| `/api/auth/me` | GET | Get current user profile |
| `/api/auth/me` | PUT | Update current user profile |
| `/api/auth/change-password` | POST | Change user password |

### Token Format

JWT tokens contain:
- `sub`: User ID (subject)
- `username`: Username
- `exp`: Expiration timestamp
- `iat`: Issued at timestamp

### Error Responses

| Status Code | Description |
|-------------|-------------|
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (valid token but insufficient permissions) |
| 400 | Bad Request (validation error) |
| 404 | Not Found (user or resource doesn't exist) |
| 500 | Internal Server Error |

## Support

For questions, issues, or feature requests:
- 💬 [Discord Community](https://discord.gg/37XJPXfz2w)
- 🐛 [GitHub Issues](https://github.com/lfnovo/open-notebook/issues)
- 📧 [Email Support](mailto:luis@lfnovo.com)
