"""Export Neon/SQLite views -> data/*.json snapshots for GitHub Pages."""
import sqlite3
import json
import os

DB = os.path.join(os.path.dirname(__file__), "..", "data", "phuquoc.db")
OUT = os.path.join(os.path.dirname(__file__), "..", "data")


def rows(db, sql):
    db.row_factory = sqlite3.Row
    return [dict(r) for r in db.execute(sql)]


def main():
    db = sqlite3.connect(DB)
    # foods: executable first, then all ACTIVE/VERIFY places with key fields
    foods = rows(db, """SELECT notion_id,name,region,housing,cluster,time_slots,hours_text,
      maps_query,price_text,cuisine,worth,convenience,local_idx,pq_feature,kid_fit,
      grade,op_status,op_conf,atlas_state,data_conf,research_date,last_verified,
      evidence,neg_warn,summary,dish_ids,evidence_as_of FROM food_places
      ORDER BY
        CASE atlas_state WHEN 'ACTIVE' THEN 0 WHEN 'VERIFY' THEN 1 ELSE 2 END,
        grade, name""")
    carriers = rows(db, "SELECT title,dish_id,place_id,role,status,scope,food_conf,evidence_as_of,accepted_at FROM dish_carriers")
    points = rows(db, "SELECT slug,name,area,interest,mandatory,trip_priority,condition_gate,returnability,play_mode,durable_note,status,evidence_as_of FROM points")
    cards = rows(db, "SELECT slug,name,status,route,gates,transport,notes,evidence_as_of FROM cards")
    bookings = rows(db, "SELECT slug,kind,title,detail,amount,status,evidence,evidence_as_of FROM bookings")
    transport = rows(db, "SELECT slug,direction,plan,station,status,priority,note,evidence_as_of FROM transport_options")
    snap = {"foods": foods, "carriers": carriers, "points": points, "cards": cards,
            "bookings": bookings, "transport": transport,
            "meta": {"cards_rule": "5-card: onbird/vinwonders/cable/starfish/safari; anthoi=OPTIONAL satellite; khem=RETIRED",
                     "source": "Notion ETL 2026-09-20"}}
    for name, data in [("foods", foods), ("points", points), ("cards", cards),
                       ("bookings", bookings), ("snapshot", snap)]:
        p = os.path.join(OUT, f"{name}.json")
        json.dump(data, open(p, "w"), ensure_ascii=False, indent=1)
        print(name, len(json.dumps(data, ensure_ascii=False)), "bytes ->", p)
    print("counts:", {k: len(v) for k, v in snap.items() if isinstance(v, list)})


if __name__ == "__main__":
    main()
