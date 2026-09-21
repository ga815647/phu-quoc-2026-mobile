"""Export Neon/SQLite views -> JSON snapshots for GitHub Pages / candidate site.

Source selection (SSOT cutover 2026-09-22: Neon is now the source of truth):
- Default `PHUQUOC_DB_SOURCE=neon` -> production Postgres via `DATABASE_URL`
  (psycopg2). Same SELECT column order as SQLite so JSON contract is unchanged.
- `PHUQUOC_DB_SOURCE=sqlite` -> data/phuquoc.db (migration-frozen archive;
  explicit opt-in only, never the default write path).
  Secret rule: DATABASE_URL is read from env only; never printed or written to files.

Public projection (default, safe for any publishable output):
- bookings drops detail/evidence (may carry order IDs / ticket codes / contact info).
- points drops condition_note (not part of the public contract).
- Set `PHUQUOC_INTERNAL=1` for full-column internal output (migration comparison
  only; write to an isolated non-published directory, never over data/).
  Source DB rows are never modified by this tool.

Sort parity: foods ORDER BY uses explicit `NULLS FIRST` on grade so Postgres
matches SQLite's default NULL ordering (SQLite path behavior unchanged).
"""
import json
import os

DB = os.path.join(os.path.dirname(__file__), "..", "data", "phuquoc.db")
OUT = os.environ.get("PHUQUOC_OUT_DIR",
                      os.path.join(os.path.dirname(__file__), "..", "data"))
SOURCE = os.environ.get("PHUQUOC_DB_SOURCE", "neon").lower()
INTERNAL = os.environ.get("PHUQUOC_INTERNAL", "") == "1"


def rows_sqlite(db, sql):
    import sqlite3
    db.row_factory = sqlite3.Row
    return [dict(r) for r in db.execute(sql)]


def rows_neon(conn, sql):
    import psycopg2.extras
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]


def main():
    if SOURCE == "neon":
        try:
            import psycopg2
        except ImportError:
            raise SystemExit("PHUQUOC_DB_SOURCE=neon requires psycopg2 (pip install psycopg2-binary).")
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise SystemExit("PHUQUOC_DB_SOURCE=neon requires DATABASE_URL env (value never logged).")
        db = psycopg2.connect(dsn)
        fetch = lambda sql: rows_neon(db, sql)  # noqa: E731
        print("source: neon (DATABASE_URL host redacted)")
    elif SOURCE == "sqlite":
        import sqlite3
        db = sqlite3.connect(DB)
        fetch = lambda sql: rows_sqlite(db, sql)  # noqa: E731
        print("source: sqlite", DB)
    else:
        raise SystemExit("PHUQUOC_DB_SOURCE must be 'sqlite' or 'neon'.")
    # foods: executable first, then all ACTIVE/VERIFY places with key fields.
    # NULLS FIRST keeps Postgres order identical to SQLite's default NULL placement.
    foods = fetch("""SELECT notion_id,name,region,housing,cluster,time_slots,hours_text,
      maps_query,price_text,cuisine,worth,convenience,local_idx,pq_feature,kid_fit,
      grade,op_status,op_conf,atlas_state,data_conf,research_date,last_verified,
      evidence,neg_warn,summary,dish_ids,evidence_as_of FROM food_places
      ORDER BY
        CASE atlas_state WHEN 'ACTIVE' THEN 0 WHEN 'VERIFY' THEN 1 ELSE 2 END,
        grade NULLS FIRST, name""")
    carriers = fetch("SELECT title,dish_id,place_id,role,status,scope,food_conf,evidence_as_of,accepted_at FROM dish_carriers")
    points = fetch("SELECT slug,name,area,interest,mandatory,trip_priority,condition_gate,returnability,play_mode,durable_note,status,evidence_as_of FROM points")
    cards = fetch("SELECT slug,name,status,route,gates,transport,notes,summary,key_times,badges,stops,transport_out,transport_back,kid_note,dining,cut_order,callout,evidence_as_of FROM cards")
    bookings = fetch("SELECT slug,kind,title,detail,amount,status,evidence,evidence_as_of FROM bookings")
    transport = fetch("SELECT slug,direction,plan,station,status,priority,note,evidence_as_of FROM transport_options")
    snap = {"foods": foods, "carriers": carriers, "points": points, "cards": cards,
            "bookings": bookings, "transport": transport,
            "meta": {"cards_rule": "5-card: onbird/vinwonders/cable/starfish/safari; anthoi=OPTIONAL satellite; khem=RETIRED",
                     "source": "Notion ETL 2026-09-20"}}
    snap["meta"]["db_source"] = SOURCE
    if not INTERNAL:
        # Default public projection: same column contract as the read-only API.
        snap["bookings"] = bookings = [
            {k: b.get(k) for k in
             ("slug", "kind", "title", "amount", "status", "evidence_as_of")}
            for b in bookings]
        snap["meta"]["projection"] = "public-v1"
    else:
        snap["meta"]["projection"] = "internal-full"
    os.makedirs(OUT, exist_ok=True)
    for name, data in [("foods", foods), ("points", points), ("cards", cards),
                        ("bookings", bookings), ("snapshot", snap)]:
        p = os.path.join(OUT, f"{name}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print(name, len(json.dumps(data, ensure_ascii=False)), "bytes ->", p)
    print("counts:", {k: len(v) for k, v in snap.items() if isinstance(v, list)})
    try:
        db.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
