# Biobank Bingo — free GitHub Pages + Supabase edition

This is a static HTML/CSS/JavaScript multiplayer bingo game. No Python server, paid Render plan, or installation for participants is required. The Supabase Free tier has quotas and may pause inactive projects; see Supabase pricing for current terms.

## Publish in 8 steps

1. Create a free Supabase account at https://supabase.com/ and choose **New project**. Keep the database password private.
2. Open **SQL Editor** in your project. Paste all of `schema.sql` and click **Run** once. This creates the database tables and server-side game functions.
3. In Supabase **Project Settings → API** (or **Connect**), copy your **Project URL** and the **publishable key** (or legacy **anon** key). **Never use the secret/service_role key in browser files.**
4. Open `config.js` and replace the two `PASTE_...` values with your project URL and publishable/anon key, keeping quotation marks.
5. Create a GitHub repository (for example `biobank-bingo`) at https://github.com/new. Upload the **contents** of this folder into the repository root: `index.html`, `app.js`, `style.css`, `config.js`, `schema.sql`, `README.md`.
6. On GitHub, open **Settings → Pages**. Under **Build and deployment**, select **Deploy from a branch**, choose `main` and `/(root)`, then **Save**.
7. Wait for GitHub Pages to publish. Your site will usually be `https://YOUR-USERNAME.github.io/biobank-bingo/`.
8. Open the site, click **Create a game**, then scan the QR code from two different phones. Call clues, mark squares and claim a Bingo.

## How it works

- The facilitator creates a game and gets a six-character code and a join QR code.
- Each player enters a name and receives a randomly shuffled 4×4 card containing the same 16 terms.
- The host reads clues and reveals answers. Player devices poll every three seconds to update the called-answer list.
- Players tap squares to mark them. Bingo claims are verified in the database against both marked squares and called terms.
- A completed line (row, column or diagonal) wins; a full card is separately recognised when all 16 terms are called and marked.
- Game and player data persist in Supabase rather than disappearing on browser refresh.

## Important operational notes

- The host credential is saved in **that browser's local storage**. Keep the host tab/browser, or you may lose control of that game. There is no host account recovery in this version.
- Player identity is also saved in browser local storage. Clearing site data or switching browsers creates a new player.
- This version uses short display names only. **Do not enter real sample or patient information.**
- The 16 clues are in `app.js` in the `TERMS` array. Edit the terms/clues there and redeploy **between events**, not during a live game. Existing cards store term indexes.
- Because this is a public game with anonymous joins, malicious visitors who know a game code could join and inflate the player count. Do not use it for sensitive data or high-stakes prizes without stronger authentication and abuse controls.
- Public SQL RPCs allow anyone to create games. For larger public use, add rate limiting, CAPTCHA and administrative cleanup of old games.
- GitHub Pages is public; `config.js` is visible. This is safe only for the **publishable/anon** key because direct table access is denied and RPC functions check player/host tokens.
- If the Supabase free project pauses after inactivity, restore it from your Supabase dashboard before the event. Verify the current free-tier quotas and inactivity rules.
- Test on your actual event Wi-Fi/mobile connections before launch. The QR generator and Supabase client load from public CDNs, so internet access is required.

## Troubleshooting

- **Setup required**: check the URL/key in `config.js` and that GitHub has published the updated file.
- **Could not find function**: run the complete `schema.sql` in Supabase SQL Editor, then reload the page.
- **Permission denied**: ensure SQL completed successfully; check the browser console and Supabase logs.
- **QR code missing**: check internet/CDN access, or copy the join URL shown below the QR code.
- **Game not found**: check the six-character code and confirm the Supabase project is active.
