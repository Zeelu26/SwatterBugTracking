# Swatter Bug Tracking System

Bug tracking app with role-based admin system, email notifications, and Supabase backend.

## Roles & Permissions

| | Admin | Manager | Moderator | User |
|---|---|---|---|---|
| Create admins | Yes | No | No | No |
| Create staff | Yes | Moderators only | No | No |
| View all bugs | Yes | Yes | Yes | Own only |
| Assign bugs | Yes | Yes | Yes | No |
| Change status | Yes | Yes | Yes | No |
| Resolve bugs | Yes | Yes | Yes | No |
| Delete bugs | Yes | Yes | No | No |
| Report bugs | Yes | Yes | Yes | Yes |
| Manage users | Yes | Below their level | View only | No |
| Delete users | Yes | No | No | No |

## Setup

1. Run `supabase_setup.sql` in Supabase SQL Editor
2. Update `backend/.env` with your keys
3. `cd backend && pip install -r requirements.txt`
4. `python app.py`
5. Login: zeelpatel9262@gmail.com / Zeel7821
6. Admin portal: http://localhost:5000/admin

## Email Notifications

Uses Resend. Add your API key to `.env` as `RESEND_API_KEY`.
Sends emails on: new bug reported, bug assigned, bug resolved.
