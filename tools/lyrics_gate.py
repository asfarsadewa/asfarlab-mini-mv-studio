# The lyric review gate. The owner corrects the draft in tools/review/lyrics.html. This tool reads that review.
#   python tools/lyrics_gate.py status mvs/<id>   lists each line, its mark, its change and its comment
#   python tools/lyrics_gate.py apply mvs/<id>    writes the reviewed lyrics into brief.json, if the owner approved them
# Review by exception: an edited line is a change, Change with no edit asks for a rework, and any other line keeps the draft.
# The draft lives in mvs/<id>/lyrics_draft.json: a title, the language, a story, a style, and sections of lines.
# Each line has an id, the text, a gloss, an optional note and an optional flag. A repeat line names its first line in same_as.
import json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
cmd, root = sys.argv[1], Path(sys.argv[2])
draft = json.loads((root / "lyrics_draft.json").read_text(encoding="utf-8"))
path = root / "review" / "lyrics.json"
review = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"lines": {}, "general": "", "approved": None}
lines = [l for s in draft["sections"] for l in s["lines"]]
by_id = {l["id"]: l for l in lines}


def final(line):
    first = by_id[line.get("same_as", line["id"])]
    return review["lines"].get(first["id"], {}).get("text", first["text"]).strip()


if cmd == "status":
    for s in draft["sections"]:
        print(f"[{s['label']}]")
        for l in s["lines"]:
            if l.get("same_as"):
                print(f"  {l['id']:>3}  = line {l['same_as']}")
                continue
            e = review["lines"].get(l["id"], {})
            text = final(l)
            mark = "change" if text != l["text"].strip() else ("rework" if e.get("status") == "change" else "keep")
            change = f"  ->  {text}" if text != l["text"].strip() else ""
            comment = f"  # {e['comment']}" if e.get("comment") else ""
            print(f"  {l['id']:>3}  {mark:<6} {l['text']}{change}{comment}")
    if review.get("general"):
        print(f"\nGeneral note: {review['general']}")
    print(f"\nApproved: {review.get('approved') or 'no'}")
elif cmd == "apply":
    if not review.get("approved"):
        sys.exit("The owner has not approved the lyrics. Run status to see the review.")
    # A rework request has no words yet, so the brief must wait for a revised draft.
    rework = [l for l in lines if not l.get("same_as") and final(l) == l["text"].strip()
              and review["lines"].get(l["id"], {}).get("status") == "change"]
    if rework:
        sys.exit("These lines ask for a rework, with no new words: " + ", ".join(l["id"] for l in rework)
                 + ". Revise them in lyrics_draft.json and ask the owner again.")
    blocks = []
    for s in draft["sections"]:
        body = "\n".join(final(l) for l in s["lines"])
        blocks.append(f"[{s['label']}]\n{body}" if body else f"[{s['label']}]")
    brief_path = root / "brief.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["lyrics"] = "\n\n".join(blocks)
    brief["lyrics_approved"] = review["approved"]
    brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    changed = [l for l in lines if not l.get("same_as") and final(l) != l["text"].strip()]
    print(f"Wrote the lyrics into {brief_path}. The owner changed {len(changed)} lines:")
    for l in changed:
        print(f"  {l['id']:>3}  {l['text']}  ->  {final(l)}")
else:
    sys.exit("Usage: python tools/lyrics_gate.py status|apply mvs/<id>")
