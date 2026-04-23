# Swatter Bug Tracking System V3

Bug tracking app with role-based admin, email verification, photo uploads, and reviews.

## Roles
- **Admin** — full control, create any role, delete bugs/users/reviews
- **Developer** — manage bugs, assign, resolve, reply to reviews
- **User** — report bugs, comment, write reviews

## Features
- Email verification on signup (via Resend)
- Photo/screenshot upload on bug reports (Supabase Storage)
- Reviews page with star ratings, replies, and moderation
- Admin dashboard with filters by role, status, priority, category
- Activity log tracking all actions
- Email notifications on new bugs, assignments, and resolutions

## Setup
1. Run `supabase_setup.sql` in Supabase SQL Editor
2. Create a `bug-photos` storage bucket (public) in Supabase
3. Update `backend/.env` with your keys
4. `cd backend && pip install -r requirements.txt`
5. `python app.py`
6. Admin login: zeelpatel9262@gmail.com / Zeel7821
