# Production notes

This file is the working method of Mini MV Studio. Follow it in order. Do not skip the human review.

`mvs/noroshi/` is the reference film. Read its `brief.json`, `film.py`, `occluders.json`, `review.json` and `hero/jobs.json` before you start a new film.

## The studio standard

Every film must meet each point.

| Point | Requirement |
|---|---|
| Format | Square, 1080 by 1080, 30 frames per second, H.264 with yuv420p |
| Art | True pixel grid of 360 by 360, scaled 3 times with nearest neighbour |
| Style | ANU pixel art: 30 degree orthographic view, hue-shifted ramps, Bayer dither, hard shadows to screen right, a floating diorama on paper |
| Presentation | Tidy and minimal. One visual idea. The arc ends when the music ends. Empty space stays inside the square |
| Song | A complete song of about 1:30, with vocals if the brief has lyrics |
| People | Natural motion from real clips, cloth physics and planted feet. Hand-drawn stick figures are not acceptable |
| Depth | Exact occlusion on every plate. Shadows and fire obey occlusion too. No person stands inside a solid object |
| Music | Every production is a music video. People move with the music. Crowds dance |
| Continuity | A person cannot jump to a new place on the same plate. Show the journey, or cut to a different plate |
| Subtitles | The sung lyrics on top. Bahasa Indonesia below. Both lines appear for every sung line. Indonesian is first class, and poetic wording is preferred. If the song is in Bahasa Indonesia, the subtitle is the sung line only. Set `id` to an empty string |
| End card | `Generated in Mini MV Studio`, your handle from `studio.json` and the year of production, after the song. `render.py` adds it |
| Weight | The delivery is the one mp4 from `render.py`. Do not build a separate mobile encode. Heavy 3D stays in the bake |
| Review | The owner approves the film in the review canvas before it is final |

## Copy rules

UI text, captions, credits, README and these notes follow the ASD-STE100 register in `docs/COPY.md`. Lyrics and their translations are in-fiction voice, so they are exempt. Scan the strings before a commit.

## Tools

| Job | Tool | Notes |
|---|---|---|
| Music | `lyria-3.5` through the Gemini interactions endpoint | Key: `GEMINI_API_KEY` |
| Plates | `gpt-image-2.6-sunburst` through `tools/paint.py` | Key: `OPENAI_API_KEY` |
| Word timings | ElevenLabs `scribe_v2` | Key: `ELEVENLABS_API_KEY` |
| Generic crowd | A second Tripo model and a tinted copy of the hero body, with `outfit: false` |
| Character | `tripo3d/p2/image-to-3d` on fal | Key: `FAL_AI_KEY` |
| Motion | PINOC connector, tools named `mcp__viggle__*` | Library clips are free. Generation costs 1 credit per second |
| Rig, cloth, bake | Blender 5.2 in background mode | Set `BLENDER` if the program is not on PATH |
| Encoding | ffmpeg | The render uses libx264 |
| Review | `tools/review/index.html` | Served by `tools/review_server.py` |

Install the Python packages with `pip install -r requirements.txt`. The tools also need ffmpeg and ffprobe on PATH.

Set `BLENDER` and `FONT_DIR` on a machine with other paths. `tools/studio_paths.py` holds the defaults. Each `film.py` can name fonts of its own, so check these paths in older films.

## Film folder

| Path | Contents |
|---|---|
| `brief.json` | Prompts, lyrics, take, window, hit, year, timed lines |
| `film.py` | Scenes and motion code. It exposes `make(ctx)` |
| `occluders.json` | Traced shapes, base rows and ground footprints |
| `review.json` | Scene list and check moments for the canvas |
| `plates/` | Raw plates, prompts, snapped plates |
| `hero/` | Concept, model, `motions/`, `jobs.json`, `sprites/` |
| `music/` | Takes, receipts, analysis, word timings |
| `occlusion/` | Label maps and previews, built by the tool |
| `review/notes.json` | Notes from the owner, written by the canvas |

Each film delivers into its own folder.

| Path | Contents |
|---|---|
| `output/<id>/<id>_mv.mp4` | The full film. This is the delivery |
| `output/<id>/<id>_test.mp4` | The test window. It is a working file |

## Step 1: Write the brief

Write one idea that nobody could use for another film. Plan the scenes against the song structure.

Put these fields in `brief.json`: `id`, `title`, `grid`, `fps`, `paper`, `year`, `take`, `plate`, `test`, `full`, `hit`, `lines`, `takes` and `lyrics`.

## Step 2: Make the song

Run this command. It skips a complete take. A complete take has audio and a receipt. If the receipt is missing, the tool replaces the audio. An approved film keeps its audio.

```bash
python tools/lyria.py mvs/<id>
```

- Ask for a complete song of about 1:30. It must feel finished, with a real ending.
- Name each section in the prompt: short intro, verse, pre-chorus, chorus, short bridge, final chorus and outro.
- Write enough lyrics for that length, and no more.
- Generate 2 takes.
- Describe the style in musical terms. Do not name an artist in the prompt.
- Describe music only. Lyria blocks prompts that name massacres, war or violence.
- `lyria.py` fails if a take is outside `min_seconds` and `max_seconds`. The defaults are 75 and 110. A brief can override them if the owner asks.

Earlier evidence: a request for 60 seconds gave 67 seconds. A request for about 3:20 gave 2:56. So the length follows the request, but not exactly.

The owner found Noroshi good but a little short at 1:09. Each scene costs plates, clips and review time, so a shorter song keeps a film tight.

## Step 3: Check and time the song

```bash
python tools/analyse.py mvs/<id>/music/take_a.mp3
```

```bash
python tools/transcribe.py mvs/<id>/music/take_a.mp3
```

- Reject a take if the transcript does not match the lyrics.
- Do not trust `rise_at` alone. It can mark the end of an intro.
- Set `hit` at the beat that lands on the first sung syllable of the chorus. Check the beat, the onset and the word time.
- Time each line from the word timings.
- Write the Indonesian as a lyric of its own. It must carry the image and the feeling of the sung line. Prefer poetic wording to a literal translation.
- Give the Indonesian the same care as the sung line, and keep it legible in the bar.
- Use the words that the singer sings. If the transcript differs from the lyrics, tell the owner.
- Set scene edges on beats.

### Ear review gate

You cannot hear the song. The owner must judge the vocals and the style.

Stop here. Do not spend on plates, characters or motion until the owner chooses a take.

1. Send the owner each take that passes the checks above.
2. Report the length, the tempo and the lyric differences for each take.
3. Wait for the owner to choose a take, or to ask for new takes.
4. Set `take` in `brief.json` to the chosen take.

## Step 4: Paint the plates

Use `tools/paint.py` with `--image`. Pass an approved plate as image 1, so that a new plate matches. The first plate of a film uses `mvs/noroshi/plates/island-raw.png` as a style reference.

Generate each plate at `--quality medium --size 1024x1024 --no-augment`. Save the prompt as `plates/<name>.prompt.txt`.

Paint animals and other moving props as their own transparent sheet. Do not draw them in code. Each prompt must keep out people, fire, smoke, text and borders. Code adds them. Each prompt must also leave empty space where people will stand.

Then snap the plate.

```bash
python tools/snap_plate.py mvs/<id>/plates/<name>-raw.png mvs/<id>/plates/<name>-360.png --grid 360 --colours 48
```

Run plate generation one job at a time, with a timeout. A parallel job hung once.

## Step 5: Build occlusion

Draw a grid over each plate. Zoom into each place where a person meets scenery.

```bash
python tools/plate_grid.py mvs/<id>/plates/<name>-360.png mvs/<id>/build/grid.png --crop 90,190,250,290 --zoom 7 --every 10
```

Trace each object that can hide a person in `occluders.json`.

| Field | Meaning |
|---|---|
| `poly` | The outline in grid pixels |
| `base` | The screen row where the object meets the ground |
| `refine` | True snaps the outline to the painting with GrabCut. Use it on buildings and solid masses |
| `footprint` | The ground ellipse of a solid object: centre x, centre y, radius x, radius y |

```bash
python tools/build_occlusion.py mvs/<id>
```

Read every preview in `occlusion/`.

Measure the door and one storey on each plate. Choose the `ppu` for each plate from these numbers. A person stands 2.14 units tall. Write the values in `brief.json` as `scale`, such as `{"yard": 17, "room": 32}`.

- Trace thin parts such as posts as separate shapes. Do not refine them.
- A flat terrace is not an occluder.
- Occlusion decides draw order only. It does not stop a person from walking through an object. Footprints do that.
- In `film.py`, check each path and each position against the footprints, and stop the render on a failure. See `clearance` in the reference film.

## Step 6: Build the character

Run `python tools/catalog.py`, then read `docs/CATALOG.md`. It lists every model and motion clip in your films, with a contact sheet. Reuse a model or a clip when it fits. Build a new one only when nothing fits. After each approved film, add the look line of each new model to `tools/catalog_looks.json`. Then run `python tools/catalog.py`.

Paint a concept with Sunburst. It must show a clean T-pose, from the front, with arms and legs clear of the body. Keep out cloaks, scarves and held items, because cloth and props come later.

```bash
python tools/tripo.py mvs/<id>/hero/concept.png mvs/<id>/hero/hero.glb --faces 30000
```

PINOC can also create characters. A PINOC character is a Gaussian splat, not a mesh. It renders only through the Viggle Splat Engine, so `hero.py`, Blender cloth and the current bake cannot use it. It suits a film that plays a character in the splat engine and needs no cloth. To use it here, add a splat bake tool first.

Check each concept for the final sprite size. Clothes must contrast with the skin. Pale cream reads as bare skin. A small detail that matters, such as glasses, needs a 3D prop from the start. Painted detail does not survive at small sizes.

Generate a new concept with the approved `mvs/noroshi/hero/concept.png` as image 1. It keeps the T-pose, so the `JOINTS` table fits. Keep long hair and long skirts out of the concept. The rig adds them as cloth.

Read the model from all sides. Check which way it faces. The rig faces -Y. The reference model faces +X, so `hero.py` turns it by -90 degrees. Set this turn and the `JOINTS` table for each new model.

## Step 7: Get the motion

This step uses the PINOC connector (https://viggle.ai/pinoc/app). Any GLB with a Mixamo rig also works. The rig needs `hero/motions/idle.glb`. The reference film leaves out its clips and its model, so a new film must get its own.

1. Call `list_motion_library`. Library clips are free.
2. Clip names repeat, so take them by asset ID.
3. Call `generate_motion` only for moments that the library lacks. Each generation gives 4 samples.
4. Call `get_assets`. Download the `mixamo-glb` format to `hero/motions/<clip>.glb`. Signed URLs expire.
5. Compare the samples.

```bash
python tools/motion_sheet.py mvs/<id>/hero mvs/<id>/build/motions.png climb_1:135 climb_4:135 --per 7
```

Generate dance clips for each film. Name the tempo and the style of the song in the motion prompt. Plan at least 2 dances, so that a crowd does not move as one. Noroshi used stock cheer and wave clips, and a future film must do better.

Sync each dance to the song. Set the clip speed so that its steps land on beats. Start each person on a beat, and stagger the starts. A dancer may lift by 1 pixel on the beat.

Generated clips may ignore part of the prompt. A clip may climb on the spot or keep the hands at the sides. Read the root travel, then read the sheet.

## Step 8: Rig and bake

```bash
blender --background --python tools/hero.py -- rig mvs/<id>/hero
```

Check that the log shows 0 unweighted vertices.

### Sprite proof gate

Do not start a batch bake before this gate. A contact sheet at a large scale on a plain background does not prove that a sprite reads.

```bash
python tools/proof.py mvs/<id> hero:room:32:150:250 hero_boy:yard:14:148:272:0.74,0.86,1.02
```

The tool bakes one idle frame per character at the final scale. It places the frame on the real plate, under the grade of that scene. Read `build/proof.png` at phone size, and read the close crop.

- Does the person read against the plate?
- Do the clothes read as clothes? Does any part look like bare skin?
- Does each detail that the owner asked for show?
- Does the person fit the door?

If a check fails, change the outfit, the prop or the scale. Then run the proof again. Use `--job` to test job fields, such as `spots`.

### Bake in two stages

1. Bake only the sprites of one scene. Render that scene, and read it.
2. Bake the other jobs after that scene passes.

Write one job per clip and view in `hero/jobs.json`.

| Field | Meaning |
|---|---|
| `clip` | The file name in `motions/` |
| `azimuth` | The camera angle around the person. See the table below |
| `ppu` | Pixels per unit. The person stands 2.14 units tall. Match the scale of the plate |
| `travel` | True for a clip with root motion |
| `cloth`, `outfit`, `torch` | Turn parts on or off |
| `wind`, `gust` | World wind. Keep it the same across views of one action |
| `ik`, `ik_ramp` | Pins a hand to a point relative to the chest. Example: `{"Right": [-0.55, 0, 0.12]}`. `ik_ramp` eases it in between 2 frames |
| `frames`, `canvas`, `tint` | Range, canvas units, colour multiplier |

The person walks along -Y. The azimuth sets the direction on screen.

| Azimuth | The person moves toward |
|---|---|
| 45 | Down and left |
| 315 | Down and right |
| 135 | Up and left, back view |
| 225 | Up and right, back view |
| 180 | Straight up, back view |
| 74 | Left, at a shallow downward angle |

```bash
python tools/bake_sprites.py mvs/<id>/hero
```

Pass job names to bake only those jobs.

## Step 9: Write the film

`film.py` imports from `tools/pixkit.py`. Do not copy the kit into a film.

- `Sprite.draw` handles occlusion, grades and light.
- `Occlusion.blocks(y)` marks every object nearer than row y.
- `contact_shadow` grounds the feet. Pass `occ`.
- `Fire` and `small_flame` draw fire. Pass the occlusion mask to `Fire.draw`.
- `Captions` draws the two-line subtitle bar.

Motion rules:

- Follow the recorded root path. If you fit a path to scenery, spread the clip across it, so that feet slide as little as possible.
- Work back from a sync point. The reference film starts at the hit, then fits the pivot, the walk and the climb before it.
- To turn a person, switch between baked views of the same clip at the same frame. Cloth stays close, because the world wind is the same.
- Keep a clip between about 1 and 2 times its speed.
- Use the same palette grade for sprites and plates.
- Do not add a hard rim outline. It reads as neon.
- Do not move the plate. The world stays still. A plate that lifts on the beat reads as an unstable picture. A short shake on one big hit is the limit.
- A heroic gesture beats a literal clip. If a clip aims the wrong way, use `ik` with `ik_ramp`. A shot must read well and stay coherent with the pose.
- A hero must read against each plate. Check the silhouette at full frame. A close crop is not enough. Do not stand a hero against an object of the same colour.
- Stage each scene as a sequence. The hero walks to a place, does the action on the lyric, then moves on. A scene of more than 4 s needs at least two actions.
- Keep the plate alive. Use subjects, water, birds or lights. The plate itself stays still.
- A person must never freeze. Do not hold the last frame of a clip. When a clip ends, switch to an idle clip, or use `pingpong`. `render.py` reports any sprite that holds one frame for more than 0.4 seconds, and you must fix each report.
- Aim a shot from the clip itself. Use the line between the hands, so that an arrow leaves along the bow.
- Do not draw the end card in a film.

Test a short window, then render the song. Add `--strict` to a scripted render, so that frozen people stop the script with an error. The mp4 is still written.

```bash
python tools/render.py mvs/<id>
```

```bash
python tools/render.py mvs/<id> --full
```

## Step 10: Check the frames yourself

Read runs of consecutive frames at each place where a person meets scenery. Each spec is `name:start:step:count:x:y:w:h`.

```bash
python tools/strip.py output/<id>/<id>_mv.mp4 mvs/<id>/build/qa.png --zoom 4 walk:13.2:0.35:8:130:185:85:60
```

Ask these questions at each place:

- Does the person pass through a solid object?
- Is the person in the right depth order?
- Do the feet stay on the ground?
- Does the shadow fall only on the ground?
- Does the person jump to a new place?
- Does a held item stay in the hand?
- Does anyone freeze? Read the `Frozen people` line that `render.py` prints.

Correct draw order does not prove a correct path. Compare the feet with the footprint.

Then compare the file with a simulated re-upload.

```bash
python tools/qa.py output/<id>/<id>_mv.mp4 --times 17,31.5,46,54 --crop 240,240,600,600
```

## Step 11: Human review

Write `review.json` for the film.

```json
{
  "scenes": [{ "name": "Ash town", "from": 0, "to": 22.84, "plate": "town", "night": true }],
  "checks": [{ "t": 15.05, "x": 170, "y": 210, "text": "The hero walks behind the well.", "slow": 0.5 }]
}
```

A film with several heroes adds `"heroes": ["hero", "hero_rong"]`, so the Motion tab shows all of them. Each scene covers a part of the song. Each check is a risky moment. `x` and `y` aim the zoom lens, in grid pixels. Write a check for each place in Step 10.

Start the canvas.

```bash
python tools/review_server.py 5350
```

In the desktop app, `.claude/launch.json` has a `review` config for `preview_start`. Open http://127.0.0.1:5350/. The page lists the films. Add `?film=<id>` to open one.

| Tab | Use |
|---|---|
| Film | Plays the film with frame steps, slow motion, zoom, occlusion overlay, footprints, pixel grid and phone size |
| Motion | Loops each baked clip at true pixels on 3 backgrounds |
| Subtitles | Lists each line. A click plays that line in the film |

Keys: Space plays. The arrow keys step 1 frame. Shift with an arrow steps 10 frames. O shows occlusion. G shows the grid. P shows phone size. N opens a note.

The canvas saves notes to `mvs/<id>/review/notes.json`. Read this file when the owner reports notes. A note can arrive while you work, so read the file again before you report.

Treat each render as a draft until the owner approves it. Fix each note, then render again. Reload the canvas. Tell the owner what you could not verify. You cannot hear the song, and you read still frames.

## Step 12: Finalise

Do this step only after the owner approves the film.

1. Read `review/notes.json` again. A late note can stop the approval.
2. Decode the file with ffmpeg. Check for errors.
3. Check that the file has the moov box before the mdat box.
4. Check that the loudness is near -14 LUFS.
5. Set `approved` in `brief.json` to the date. Add the film to the table in `README.md`.
6. Clean up the film. See the cleanup rule below.
7. Deliver the mp4 file.
8. Commit only if the owner asks.

### Cleanup rule

Clean up each film after the owner approves it. A film folder must hold only what the final film uses, plus what a re-render needs.

Delete these items:

- `build/`, including QA sheets, frame strips and contact sheets
- The test file and any QA sheet in `output/<id>/`
- Takes that the film does not use, with their receipts, analysis and word timings
- Motion clips and samples that no job in `jobs.json` uses
- Plate drafts and snapped plates that the film does not use
- Baked sprites that the film does not load, with their jobs
- Blender backups and other tool leftovers

Keep these items:

- `brief.json`, `film.py`, `occluders.json`, `review.json` and `review/notes.json`
- The chosen take, with its receipt, analysis and word timings
- The clips, plates, prompts, models, concepts and sprites that the film uses
- `occlusion/`, `hero.blend` and the final mp4

Before you delete, confirm each item from the code. Read which plates and sprites `film.py` loads. Read which clips `jobs.json` names. Then render a short window, so that the film still builds. List what you deleted in your report.

## Known traps

| Trap | Fix |
|---|---|
| Printing Japanese fails on this console | Set `PYTHONUTF8=1`, or call `sys.stdout.reconfigure(encoding="utf-8")` |
| `urllib` fails certificate checks on the fal CDN | Download with `requests`. Do not turn off certificate checks |
| A fal job finished, but the download failed | Fetch the result by request ID. Do not submit again |
| Bone heat fails on a generated mesh | `hero.py` solves on a voxel copy, then transfers the weights |
| The mesh flips or the arms stay in T-pose | Do not parent the mesh to the rig. The rig object holds a 90 degree turn |
| A long rod or a flap follows the person | Unweighted vertices or weight bleed. `clean_weights` applies anatomy rules |
| A person floats | The clip does not touch z = 0. The bake measures the real contact height |
| Feet slide | Scale root travel by leg length, then follow the recorded path |
| A thin item vanishes at small sizes | One-pixel sampling drops it. Make it at least 1 pixel wide at the smallest `ppu` |
| Colours flicker in a sprite | `bake_sprites.py` shares one palette across the clip |
| Blender 5 action data | Use slots and channel bags. See `fcurves_of` and `load_clip` |
| Parallel shell calls change the folder | Use absolute paths, or `cd` in the same command |
| Whisper can hang on long music | Use Scribe |
| A transcript has no spaces or wrong words | `transcribe.py` reads Japanese by default. Pass `--lang`, such as `--lang ind`. Delete the old `.words.json` first, because the tool reuses it |
| Lyria rushes the lyrics and leaves a long instrumental end | A fast tempo crams the words. Ask for one lyric line every 2 bars. Compare the last sung word with the song length |
| Lyria blocks a harmless style prompt and names no word | The block can be random. `lyria.py` retries once. If it fails twice, reword the style text |
| Cloth floats up over the head in still air | Set `wind_z` to 0 in the job. The default lift beats gravity at low wind |
| A generated concept has a dark or glowing background | Check the concept before Tripo. The Serment townsperson came back on black with a glow. The model was still clean. Read it from all sides before you repaint |
| A caption is too wide | At 16 pixels, a Latin line holds about 43 characters. Split a long line at a breath in the singing. `Captions` stops on a line that does not fit |
| A sprite looks grey or washed out | One large colour takes most of a small palette. `bake_sprites.py` now keeps 28 to 40 colours. Check skin and hair after each new outfit |
| A hero vanishes against the plate | Do not tint the whole body, because skin turns grey. Recolour pale cloth in the texture with `recolour` in `outfit.json`. Read the hero against each plate |
| A gown flies up or collapses | Do not pin cloth at the hips alone. Bind the tube softly to the hips and legs, with a soft goal at the hem. See the `skirt` part of `hero.py` |
| Long hair reads as a cape | Use several tapered ribbons in different shades, with light wind. See the `hair` part of `hero.py` |
| A motion sample ignores the key gesture | The oath samples only bowed. Use `idle` with `ik` and `ik_ramp` for a raised hand. Then keep it moving with a loop that skips the ramp |
| A clip looks wrong on the hero | The curtsey samples dived forward. Choose a different clip that keeps the meaning of the line. A hand on the heart served better |
| Gold motes look like insects | Keep particles few. Read them at full size. One mote every few frames is enough |
| A walk does not follow the road | Set `azimuth` from the slope on screen. The down ratio over the side ratio equals 0.5 times the cotangent of the azimuth |
| A scene feels stand-still | A breathing idle is not enough. The owner flagged this on three plates of Serment. Give each scene more than one action. Keep subjects walking in from the first frame |
| A square looks empty at the start of a scene | Do not fade dancers in one by one. Walk them in from doors and edges, so they arrive on the beat. Keep wavers and strollers in the back rows |
| Hair lies flat on a side walk | Air drag pushes light ribbons flat. Set `hair_drag` to 0.1 in the job. Bake a lead-in, then start the walk at about frame 40 |
| A side walk ends too soon | Height on screen is half the true distance. A walk across the screen covers twice the pixels of a walk up the screen. Read `path` for the true time |
| A crowd walker changes colour on arrival | Bake walks without a tint. Pass the tint of the dancer as `grade` at draw time |
| Bone heat gives 0 weights on a model | `hero.py` now retries other voxel sizes. If each size fails, replace the model. Tinted copies of other bodies can fill a crowd |
| Bone heat gives 0 weights on a model with a wide hat | A flat hat brim stopped bone heat at every voxel size. Set `solver_cap` in `outfit.json` to a fraction of the height below the brim, such as 0.87. The solver drops the hat. The hat takes the weights of the head. See `examples/film_code/memedi_hero_outfit.json` |
| A hat brim stretches to the shoulders or an arm | Set `head_lock` in `outfit.json`, such as 0.81. Each part above that fraction of the height, inside the shoulders, follows the head alone |
| An arm swings as one stiff plank | Bone heat left the forearm and the hand with no weights. Set `arm_split` to true in `outfit.json`. The rig weights each arm by its place along the T-pose. Read the weight groups if an arm looks wrong |
| A hat brim floats as a ring around the head | The generated model holds the brim as a loose ring. Set `drop_rings` to true in `outfit.json`. The rig removes each loose part above the shoulders that does not reach the middle of the head. See `examples/film_code/memedi_hero_tani_outfit.json` |
| A tint does not change a saturated colour | A multiplier cannot move mustard to blue, because mustard holds almost no blue. Move the hue of those pixels when the film loads the sprite. See `rehue` in `examples/film_code/wasuregasa.py` |
| A crowd woman looks like the heroine | Keep the colour of a hero unique. Check the crowd against each hero at full frame |
| A run clip travels too little | Library `Running` runs for 53 frames and starts from slow. Find 2 matching frames, loop between them, and add the root travel on each lap. See `run_at` in `examples/film_code/wasuregasa.py` |
| A walker starts off the island | A path can pass the footprint check and still leave the island. Bring crowds in from the back rows and sides. Read the first frames of the scene |
| A person walks over a canopy | A person under a roof needs the front of that roof as an occluder, with its base at the front posts |
| A hero prop must stay in the hand | Draw the prop at `Sprite.point(i, "right", x, y)`. Use `ik` to raise the arm in the walk clip |
| A train must pass behind people and props | Draw it after the plate, and mask it with `Occlusion.blocks` at the row of the rails. Draw people after it |
| The owner asks for subtitles in another language | The owner can replace the Indonesian line for one film. Put that language in the `id` field of each line. Set `sub_label` in `brief.json`, so that the canvas names the column |
| A prompt asks for a Javanese song | Lyria sings Javanese. Use `transcribe.py --lang jav` |
| A rising flood reads as a wipe | Give each pixel the flood progress at which water reaches it. Low ground goes first, shallow water is a dithered mirror, and foam marks the moving edge. See `flood_map` in `examples/film_code/damar.py` |
| One person in a hug vanishes | A hug clip steps forward into the embrace. Two people placed close together end up on the same spot. The nearer one then hides the other. Start them about 40 pixels apart at 18 `ppu`. Zoom on the frame |
| A looping walker reads as frozen | The frozen check remembers the last frame at each screen spot. A walker that loops a path passes the same spot on the same frame each lap. The check then counts the laps as one long hold. Shift each lap a few pixels to the side. See `strollers` in `examples/film_code/ngenteni.py` |
| A seated person reads as standing | A sit clip that faces the camera points the thighs at the lens. The legs then look straight. Bake the sit from a side angle, such as azimuth 300. Put the person on the seat. Read the bench in a strip |
| A vehicle reads as a flat cut-out | A painted vehicle that slides along a road looks pasted on. Build it with Tripo, and bake it with the camera, sun and `ppu` of the people. Bake drive, brake and idle frames. Draw people behind it before it. Draw people in front of it after it. See `examples/film_code/ngenteni_bake_bus.py` |
| A walk ends too early after the song | `beat()` snaps a time to the nearest beat. The beats stop when the music stops. A time in the outro then snaps back to the last beat. Use a set time after the last beat. See `T_QUAY` in `examples/film_code/hitomose.py` |
| A climber walks behind a building | Do not read stair points off a grid by eye. Draw the path on the plate at 3 times scale, and check that each point sits on a step. Then read the climb in a strip |
| A light source sits beside its lamp | Zoom on the lamp at 14 times. Use the brightest lamp pixel as the beam origin |
| A mirror shows the backs of the dancers | Dancers face the mirror, so the camera sees their backs. Bake each dance twice: from behind for the room and from the front for the mirror. Draw the front view flipped left to right. Set its feet at twice the mirror floor row minus the feet row. Clip it to the glass, and draw it before the bodies. See `reflect` in `examples/film_code/geoul.py` |
| A formation reads as a flat line | The 30 degree view halves depth. Give a V at least 25 rows from the point to the wings, and read it in a strip |
| A walker appears out of a wall | A lane that turns behind a building is the place to enter. Trace the occluder to the true edge of the building, and start the walker behind it. The building then reveals him. Do not fade a walker in at the end of a lane. See `CORNER` in `examples/film_code/geoul.py` |
| People vanish where they gather | A loose box around an object also covers the ground behind it. Each person who stands in that box disappears. Trace the outline tight to the object, and turn off `refine` if it stays loose. Read the strip where the people stop |
| A person stands on a table | A painted table can touch the wall behind it with no floor between them. A spot at that wall puts the feet above the table top. Check that free floor shows between the object and the wall. If no floor shows, move the code prop to a place where the person can stand |
| A pushed prop vanishes at phone size | At true scale a hand cart is a few pixels on a wide plate. Bake the prop about 1.5 times its true size. Darken its outline. See `examples/film_code/zaizou_bake_cart.py` |
| A small story beat does not read | A phone or a letter is a few pixels in a wide shot. Cut to a close-up plate for the beat, and draw the change in code. See `close_up` in `examples/film_code/zaizou.py` |
| People look tiny next to the props | Do not guess `ppu`. Measure a prop of known height on each plate: a door is 2 m, a desk is 0.75 m, a phone box is about 2 m. A person is about 1.7 m. Run the proof against that prop. Close-up rooms show this most, because their furniture is painted large. Several earlier films have people that are too small in close rooms |
| Blinking bulbs also catch windows and roof tiles | A colour test alone finds lit windows and tile highlights. Keep only small isolated lights inside the band where the strings hang. Pulse their brightness, and keep their colour. See `bulbs` in `examples/film_code/kirimsalam.py` |
| Bright snow turns into paper | The usual paper test also catches bright pixels inside the island. Count pale pixels as paper only where they connect to the frame edge. See `plate` in `examples/film_code/haojiao.py` |
| A warm grade turns snow into paper | Warm light on white snow lands on the paper colour, and the island loses its edge. Tint snow cool, such as rose or blue |
| The trudge clip walks sideways | Library `Injured Walk` turns about 90 degrees from `walking`. Trudge at 315 goes up and right. Trudge at 225 goes up and left. Read the net `path` after each bake |
| A walker moves backwards | The library carry clip walks the opposite way to the walking clip. Bake carry clips 180 degrees around. Compare the net `path` of each travel sprite with its direction on screen before a render |
| Fog reads as a checker lattice | A dither threshold over a large area makes a grid. Blend a slow cloud field into the plate. Draw most of the fog before the people, and only a light veil after. See `fog` in `examples/film_code/hyeong.py` |
| A crowd walks through a person who stands still | A footprint guard checks solid objects only. Route walkers around each standing person, and read the crossing in a strip |
| A Korean caption shows empty boxes | Use `malgun.ttf`. `studio_paths.py` has fallbacks for other machines |
| A spreading fire reads as a ring of lava | Keep the front band thin and ragged, under 1 second. Few embers follow it. See `burning` in `examples/film_code/zhebahuo.py` |
| Carried props turn a night crowd into pale ghosts | Scale a carried prop to the sprite, and give it the night grade of the scene |
| A torch flame floats beside the hand | Draw a handle from the `right` point to the `tip` point. The baked handle is too dark to read |
| A fire scene doubles the file size | Flames and embers change each frame. Slow the ember shimmer, and expect about 1.2 MB per second in fire scenes |
| A prop comes back on a black glow | Flat magenta can fail. Pass `--background transparent` to `tools/paint.py` |
| Amber light turns grey after snapping | Blue night plates take the palette. Copy the warm pixels back from the raw plate. See `examples/film_code/damar_fix_lit.py` |
| Walkers slide on a long path | Pick the frame from the distance walked. See `walk_between` in `examples/film_code/damar.py` |
| A test window fades to paper at its end | The film fade runs at the end of the window. Do not read the last 1.2 seconds of a window as a fault |
| Scribe rejects `--lang cmn` | Use `--lang zho` for Mandarin. The transcript of sung Mandarin has many wrong words, so trust its timing more than its text. Ask the owner to judge the words |
| A take runs past `max_seconds` | Read the loudness tail first. A song can stop on its last word, then hold silence and a stray sound. End the film at the last word with `full.end` |
| A generated sample ignores the hands again | The crying samples never reached the face. Pick the sample with the right body, and put the hand there with `ik` |
| A PINOC generation runs for a long time | It can time out, and PINOC refunds the credits. Do not wait with a batch. Bake a stand-in clip, and replace it later. A shorter, plainer prompt worked on the retry |
| A prop sheet has a painted background | Ask for flat magenta, then key it out. Read the cell borders, because a wide prop can cross the middle of the sheet |
| A seated person vanishes at a bench | The bench base row is below the feet. Set the base row at the seat, then raise the person onto the seat |
| A gown reads as a bell | The default skirt is wide. Set `skirt_shape` in `outfit.json` for a narrow wrap. An example is `[0.17, 0.08]` |
| A first-stage film needs sprites that do not exist yet | Let `film.py` use a stand-in for an unbaked sprite during the test. Remove the stand-in before the full render |
| A vehicle must pass quickly | The walk clip at speed slides. Put the person on the vehicle with `lift`, and play the walk on the spot to turn the pedals |
| People float over a road or walk into a shop | Footprints guard solid objects only. Measure the walkable area on each busy plate, and stop the render if a path leaves it. See `on_walkway` in `examples/film_code/layangan_zh.py` |
| The same place must age across scenes | Paint the first plate. Then `edit` it with a prompt that keeps every edge and changes the age and the light. Trace the occlusion of each plate on its own |
| An aged plate comes back on a colour wash | Key the pale wash back to paper from the image border. Then read the corners of the snapped plate for a stray blob |
| A model comes back grey | Read the mean colour of a sprite. A small glb file is a warning. Generate the model again |
| A generated clip barely moves the hand | Bake `idle` with `ik` and a short `ik_ramp`. Then pick the frame from the time since the beat. The arm lands on each beat |
| A thin prop keeps a magenta fringe | Thin parts blend with the key when they shrink. Drop pixels that are still magenta after you scale the prop |
| A hero vanishes in a night scene | Pass `light` to `Sprite.draw`, and aim it at the hero. A small lit pool also helps a hero in a crowd |
| A clip must clip to a surface | Draw the sprite on a copy of the frame. Then copy back only the pixels inside the surface mask. See `cast` in `examples/film_code/urip_maneh.py` |
| A scene change needs a big gesture | Render both scenes in the window and split them at one moving edge. Stamp the large prop on that edge. See `WIPES` in `examples/film_code/urip_maneh.py` |
| A walk freezes under a wipe | Start the walk when the wipe starts. The new scene is on screen before its cut time |
| Wind dashes cross a plate | Draw them over paper only |
| Captions show empty boxes | The font lacks those glyphs. Use `simsun.ttc` for simplified Chinese and `msgothic.ttc` for Japanese. `Captions` stops on a missing glyph |
| A code-drawn animal looks crude | Paint a flap or walk cycle with Sunburst, with `--background transparent`. Fix the head as the anchor of each frame |
| A clip ignores the hands that a scene needs | Add `ik` to the job. It needs no new clip |
| A long heredoc fails in this shell | Heredocs above about 10 KB truncate. Write a file with the Write tool, then run it |
| Pale cream clothes read as bare skin | Recolour the cloth with `recolour`. A warm cream needs `recolour_band` with a wider colour spread. Read the sprite at room scale |
| Glasses or spots vanish in a small sprite | Painted detail does not survive at 14 pixels per unit. Set `glasses` in `outfit.json` for a 3D prop with pale lenses. Set `spots` in the job, and raise `colours` to 64 so that the red stays in the palette |
| A person vanishes before a door | The base row of the house is below the feet at the door. Set the base row above the door approach, and read the walk in a strip |
| A small white shape reads as a censor bar | Do not draw a bandage across the body. Keep a prop small, and put it in a hand |
| The canvas shows a directory listing | The root path with `?film=<id>` does not redirect. Open `/tools/review/index.html?film=<id>` |
| A job path fails with no error | On Windows with Git Bash, a `/c/...` path renders to the wrong place. Pass `C:/...` to Blender |

## Work in parallel

Several agents can make films in this checkout at the same time. Follow these rules.

- Keep each film inside its own folder and its own output folder.
- Do not switch branches in this checkout. A switch moves the other agents too.
- Make each change to a shared tool opt-in. A job key or an outfit key turns it on, and other films stay the same.
- Commit a shared tool change at once, as a small commit.
- Stage files by name. Read `git diff` first. If a file holds the work of another agent, stage only your hunks with `git apply --cached`.
- After a change to `pixkit.py`, render a short window of another film before you commit. Use `--window` and `--out`.
- `bake_sprites.py` copies `hero.py` when a batch starts. One batch uses one version of the tool.
- Run plate generation one job at a time across all agents. Check for another image job before you start one.
- Two bakes share the GPU and run slower. Include this in a time estimate.
- Check `get_credit_balance` before a large motion job. All agents share the PINOC credits.

## Add a feature

Add shared drawing to `tools/pixkit.py`. Add a new fact or a new trap to this file in the same change. A cold agent reads only this file and the code.
