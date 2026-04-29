# Crowd management platform

## Local setup

1. Install dependencies:
   `npm install`
2. Create a local env file from the template:
   `Copy-Item .env.example .env.local`
3. Fill these required keys in `.env.local`:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
4. Start the app:
   `npm run dev`

## Production build

Run:
`npm run build`

