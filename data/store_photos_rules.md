# Store photo rules (the owner's reviews, 20 Nov 2026). scripts/store_photos_pick.py follows these.

1. No holes in cut-outs: only background connected to the photo's edges is removed; gaps enclosed by the item (between
   two shoes, inside a strap) keep the original pixels. A see-through gap reads as a white hole in the product.
2. No cropped photos: an angle where the item is cut off by the frame (touches an edge of the photo) is dropped.
3. Model photos always go last, after every product-only angle.
4. Sharp, high-quality photos only: soft, blurry, low-resolution or badly cut-out photos are dropped (the eye test:
   would a premium store show it?).
5. One store per set: every photo of a find (main and angles) comes from the same store's photoshoot, so lighting,
   angle style and finish match. Pick the store with the best complete set and take the main from that set; when a
   photo does not look like the rest, look at another store instead of mixing.
6. Every photo shows the whole item: no detail crops or close-ups (a logo alone is "not the t-shirt").
7. Fewer, better photos: the best product-only FRONT (the main) and the best product-only BACK, then ONE model photo
   (the best front view, kept as the full photo, never cut out). No near-duplicates (three similar model poses: keep one).
   Extra product angles (side, top, sole for shoes) only when they are as good as the front and back.
8. The main photo is never a model photo.
9. A 3/4 standing product shot (the item shaped as if worn, no person) beats a flat lay for the main; drop the flat lay
   when the 3/4 shot exists.
10. No padding: if there is no good back photo, the set is just main + one model photo. Never fill with weaker shots.
11. The model photo: the one that best matches the main's photoshoot (same store and lighting), straight front view, the
    item clearly the focus (owner's pick on the Arc'teryx Beta: the brand's own studio shot, not a second store's).
12. Exact version: details must match the find's photo (hood lining pattern and colour, hardware, pockets, logos). The
    Burberry puffer: a beige-check lining is a different jacket from the grey-check "Bideford". Name the exact model
    first, then search for that name, also in European stores (miinto, Farfetch-fed shops) and in other languages; the
    owner found a full set on miinto.no that the first search missed. Keep searching until a store with a full,
    matching set turns up instead of settling for a near match.
13. A full set from one store beats picking: when one store has a complete, consistent professional set of the exact item
    (one photoshoot: front, back, close-up, model full body, side), use ALL of it, product-only shots first and model shots
    after (owner on the Burberry Bideford set from miinto.no: "use all of them"). Rule 7 (fewer, better) is for when
    photos would have to be picked from mixed or weaker sources. Close-ups are fine when they come from that same full set
    and show the item in context (rule 6 is about loose detail crops like a floating logo).
14. The brand's official studio photo is the best main (Nike Tech Fleece: Nike's crisp 3/4 studio shot on a light grey
    background). It is fine to take it from wherever it turns up, eBay included: resellers often reuse the official
    photo. Skip a source for the photo TYPE (homemade: floors, hangers, phone light, people's rooms), never for the
    website it is on.
15. A set like a tracksuit can use the top's photo as the main when no clean full-set photo exists.
16. Colour: the find's own colour is preferred; a close shade of the same design (Essentials heather grey vs taupe) is
    acceptable when no store has the exact one, but keep searching for the exact colour first.
17. No repeated angle: a second back view (even on a different background) is a duplicate, not a model photo. Essentials
    hoodie: owner kept main + back only.
18. More is better when it is good: from the chosen store, keep every good photo, one per angle (front, back, side,
    3/4, top, sole, close-up of the item, model shots), not only main + back + one model. Owner on the Ralph Lauren grey
    zip hoodie and the Rolex: "perfect images but id prefer more if there are any". Rule 7 now only means: never pad
    with weaker or repeated shots.
19. Item alone: no packaging, boxes, bags, tags or props in a photo (Pampeano belt: the shot with the branded box was
    dropped; the rolled belt alone became the main, plus the worn shot).
20. The main shows the item's FRONT the way it is worn or seen first: a watch's dial facing the camera, never the caseback
    (AP Royal Oak: the caseback was picked as main by mistake). A caseback, sole or inside view is a good EXTRA photo
    after the main.
21. Keep the current main when it is already a clean official studio front shot (Arc'teryx Beta LT: the site's photo
    stayed the main, the store's model shots follow). The store photos are added after it; no second front shot.
22. Design on the back: when the main graphic or logo is on the back (Acne Studios Stockholm 1996 hoodie), the back is the
    main and the plain front follows.
23. No logo or print close-ups: a close-up of only the print/text is a bad shot (Acne hoodie). Close-ups must show a
    recognisable part of the item (collar, zip, buckle).
24. Unsure matches (confidence under 0.7, or second-hand photo quality) never replace the main: the current photo stays
    first and the found photos are added after it (Ralph Lauren jeans from poshmark). Each find gets a "photo_score"
    (3 full store set, 2 picked set, 1 weak, 0 nothing).
25. Ranking: the best photos and the most popular finds first. When the photos go live, photo_score is part of the
    spreadsheet's order (with popularity), so finds with weak photos sit a bit lower.
26. A store photo that is the very photo already on the site proves the match (Parajumpers Ivor: the AI said 40%); then
    take that store's whole gallery (Care of Carl had 7 photos of it). The owner wants more photos whenever the store has
    them.
27. More photos per store page: up to 16 photos of one page are considered (was 9), up to 12 product photos kept. Close-ups
    of a real part (handle, name tag, clasp, strap clip, inside) are kept; pure texture and wear/damage details from
    pre-owned listings are skipped (Louis Vuitton Keepall: owner wants more photos of the bag).
28. Model photos show the whole item on the person; tight model crops (chest and collar only, item cut off) are skipped
    (Ralph Lauren glossy puffer).
