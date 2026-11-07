# Mini MV Studio: notes for agents

This repo produces square pixel-art music videos for phones. `docs/PRODUCTION.md` is the working method. Read it before any production work, and follow it step by step. `mvs/noroshi/` is the reference film.

"The owner" in these notes is the person who directs the film.

## First run

1. Run `python tools/doctor.py`. Report each FAIL to the owner.
2. Read `docs/PRODUCTION.md`, then `mvs/noroshi/film.py`.
3. Ask the owner for the song and the story. Then start with `python tools/new_film.py <id> "<title>"`.

Tell the owner the cost before you spend on a paid service.

## Studio rules

- The style is pixel art on floating dioramas over plain paper, tidy and minimal.
- A song is a complete composition of about 1:30.
- People need natural movement and limb physics. Use motion clips, the Blender rig and bake, and a 3D model.
- Occlusion on each plate must be exact.
- Each sung line has a first-class translation below the sung lyrics. Prefer poetic wording to a literal translation.
- `tools/render.py` adds the end card after the song. Do not remove it. Do not draw an end card in a film.
- The final product is the one mp4 from `render.py`.
- Human ears judge the song. The owner chooses a take before you spend on plates, characters or motion.
- Human eyes judge the film. The owner approves it in the review canvas before it is final.

## Run

- Check the machine: `python tools/doctor.py`
- Render: `python tools/render.py mvs/<id> --full`
- Stop a scripted render on frozen people: add `--strict`
- Review canvas: `python tools/review_server.py 5350`
- Owner notes: `mvs/<id>/review/notes.json`

## Rules

- Keep film code in `mvs/<id>/film.py`. Keep shared drawing in `tools/pixkit.py`.
- `build/` and `output/` are generated. Git ignores them. Each film delivers into `output/<id>/`.
- Keep paid assets in the film folder until approval. A tool must skip an asset that exists.
- After approval, clean up the film. See the cleanup rule in `docs/PRODUCTION.md`.
- Read frame strips at each place where a person meets scenery, before you report a film.
- Say what you could not verify. You cannot hear the song.
- All UI text, captions, credits and docs follow `docs/COPY.md`. Lyrics and their translations are exempt. Scan before a commit.
- Never print or commit an API key. Never commit `.env`.
- Add each new trap to `docs/PRODUCTION.md`.

## Rights

Do not name a living artist in a music prompt. Do not make a film from characters, stories or songs that other people own. If you have the rights, you can. Read `NOTICE.md`.
