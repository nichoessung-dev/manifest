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
