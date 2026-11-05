# Stage 2 — Room image generation

You are given:

- a **photo of a real college dorm room** as it looks now (always the first
  image),
- optionally, **product reference photos** for some of the pieces below, on
  plain studio backgrounds — the prompt names each one as "[Image N]",
- a list of furniture / decor pieces to **add to or swap into** that room, each
  with a quantity, a rough placement note, and a short note on why it was
  chosen (which tells you whether it is an addition or a replacement),
- a one-to-two sentence description of the **intended overall look**.

Produce **one** photorealistic image of that same room with the plan applied.
This is a targeted redecoration, not a rebuild.

## Keep from the original room

- **Architecture, exactly:** walls, windows, doors, ceiling, radiators,
  built-in closets, floor material, room proportions.
- **Camera position and angle**, and the view through the windows.
- **Fixed finishes:** wall colour, flooring, trim. Do not repaint or re-floor
  to force the aesthetic — the new pieces sit against the room as it is.
- **Existing furniture and decor that the plan does not replace.** Render each
  one as-is: same colour, material, and wear. The **only** change allowed to a
  kept piece is adjusting how light and shadow fall on it so it sits naturally
  in the scene.
- Outlets, switches, vents, and light fixtures where they are.

## Apply the plan

- Add or swap in **only** the listed pieces, in the listed quantities — if the
  quantity is 2, show exactly 2, no more and no fewer.
- For a piece whose note indicates it **replaces** something, remove the
  existing item it stands in for (same function and location) and put the new
  piece there. For an **addition**, place it without removing anything.
- Match each product's described material and colour. When a piece has a
  reference photo ("[Image N]"), match that photo's actual product — its shape,
  proportions, material and colour — and ignore its studio background.
- Placement notes are approximate. Follow them, but place each piece where it
  makes **functional sense** for its type: a desk chair at the desk, a nightstand
  beside the bed head, a lamp next to a seat or work surface, a rug centred under
  the furniture it anchors, shelving and storage flat against a wall and within
  reach. Keep pieces that are used together next to each other.
- When a placement note collides with a real constraint — it blocks a door,
  window, radiator, or outlet, overlaps a kept piece, or there is no room at that
  wall — move the item to the nearest spot that still fits its function.
- Respect how people move through the room: keep a clear path between the door,
  bed, desk, and window, and do not box in a seat, drawer, or door so it cannot
  be used.
- Let the intended overall look guide the mood and how pieces are arranged,
  within all the rules above.
- Add **no** furniture or decor beyond the listed pieces, with one exception: a
  few live houseplants — a potted floor plant, or a small plant on a sill, shelf,
  or desk — may be added where they sit naturally and suit the intended look.
  Nothing else: no extra art, rugs, cushions, lamps, or accessories the plan did
  not ask for.
- Tidying loose clutter (stray clothes, papers, cables) is fine. Removing
  furniture is not.

## Realism

- Every piece rests properly on the floor or wall — nothing floating, clipping,
  or intersecting other objects.
- Perspective and vanishing lines match the source photo. Do not warp or
  resize the room to fit an item.
- Place items at believable real-world scale for their type. Keep walkways
  clear.
- Lighting: keep the source photo's light sources, their direction, and their
  colour temperature. Shadows on both kept and new pieces follow that same
  light.

## Output

- A single continuous photorealistic image, same aspect ratio and framing as
  the input.
- No text, labels, captions, watermarks, arrows, product call-outs, insets,
  collage, or before/after split. No people.
