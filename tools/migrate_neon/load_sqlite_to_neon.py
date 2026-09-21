"""Load SQLite phuquoc.db into an isolated Neon test branch (psycopg2).

Reads:
  app/data/phuquoc.db (read-only; never written)
  app/tools/migrate_neon/neon_schema_candidate.sql (DDL, IF NOT EXISTS)
Writes:
  Neon branch given by --dsn / DATABASE_URL only. No default-branch fallback:
  caller must pass an explicit test-branch DSN.

FK normalization (verified 2026-09-21, isolated load only, source untouched):
  dish_carriers.dish_id / place_id are stored dashless in SQLite while
  dishes/food_places notion_ids carry dashes. Each of the 7x2 values was
  verified to match exactly one master row after stripping '-'. The loader
  re-verifies this 1:1 mapping at runtime and aborts on any miss/ambiguity.

Secret rule: DSN comes from env/argv only; never printed, logged, or written.
Usage:
  DATABASE_URL='postgresql://...' python3 load_sqlite_to_neon.py --verify-only
  DATABASE_URL='postgresql://...' python3 load_sqlite_to_neon.py --apply
"""
import argparse
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(os.path.dirname(HERE))
SQLITE_DB = os.path.join(APP, "data", "phuquoc.db")
DDL = os.path.join(HERE, "neon_schema_candidate.sql")

TABLES = ["dishes", "food_places", "dish_carriers", "points", "cards",
          "bookings", "transport_options", "evidence_log"]

# Columns in stable SELECT order per table (matches SQLite schema column order).
COLUMNS = {
    "dishes": ["notion_id", "name", "type", "flavor_note", "price_hint",
               "kid_fit", "pq_feature", "time_slots", "order_note",
               "evidence_as_of", "updated_at"],
    "food_places": ["notion_id", "name", "region", "housing", "cluster",
                    "time_slots", "hours_text", "maps_query", "price_text",
                    "cuisine", "worth", "convenience", "local_idx",
                    "pq_feature", "kid_fit", "grade", "op_status", "op_conf",
                    "atlas_state", "migration", "data_conf", "research_date",
                    "last_verified", "evidence", "neg_warn", "summary",
                    "kid_plan", "dish_ids", "v2_run", "v2_proto",
                    "evidence_as_of", "updated_at"],
    "dish_carriers": ["notion_id", "title", "dish_id", "place_id", "role",
                      "status", "scope", "food_verdict", "food_conf",
                      "avail_verdict", "risk_exec", "txn_risk", "rationale",
                      "decision_set", "worker_run", "evidence_as_of",
                      "accepted_at", "updated_at"],
    "points": ["slug", "name", "area", "interest", "mandatory",
               "trip_priority", "condition_gate", "convenience",
               "returnability", "play_mode", "condition_note", "kid_note",
               "status", "durable_note", "source_notion_id",
               "evidence_as_of", "updated_at"],
    "cards": ["slug", "name", "status", "route", "gates", "transport",
              "notes", "summary", "key_times", "badges", "stops",
              "transport_out", "transport_back", "kid_note", "dining",
              "cut_order", "callout", "evidence_as_of", "updated_at"],
    "bookings": ["slug", "kind", "title", "detail", "amount", "status",
                   "evidence", "evidence_as_of", "updated_at"],
    "transport_options": ["slug", "direction", "plan", "station", "status",
                          "priority", "note", "source_notion_id",
                          "evidence_as_of", "updated_at"],
    "evidence_log": ["id", "ref_type", "ref_id", "note", "created_at"],
}


def norm(u):
    return u.replace("-", "") if isinstance(u, str) else u


def load_sqlite():
    if not os.path.exists(SQLITE_DB):
        sys.exit("SQLite source missing: %s" % SQLITE_DB)
    src = sqlite3.connect("file:%s?mode=ro" % SQLITE_DB, uri=True)
    data = {}
    for t in TABLES:
        cols = COLUMNS[t]
        data[t] = [dict(zip(cols, r)) for r in
                   src.execute("SELECT %s FROM %s" % (",".join(cols), t))]
    src.close()
    return data


def verify_fk(data):
    """Re-verify normalized 1:1 FK mapping; return (ok, normalized_rows, report)."""
    dishes = {r["notion_id"] for r in data["dishes"]}
    places = {r["notion_id"] for r in data["food_places"]}
    dn = {}
    for u in dishes:
        dn.setdefault(norm(u), []).append(u)
    pn = {}
    for u in places:
        pn.setdefault(norm(u), []).append(u)
    report = []
    out = []
    ok = True
    for r in data["dish_carriers"]:
        row = dict(r)
        for col, master in (("dish_id", dn), ("place_id", pn)):
            cands = master.get(norm(r[col]), [])
            if len(cands) != 1:
                ok = False
                report.append("FAIL %s %s: %d matches" %
                              (r["title"], col, len(cands)))
            else:
                if cands[0] != r[col]:
                    report.append("NORM %s %s: %s -> %s" %
                                  (r["title"], col, r[col], cands[0]))
                row[col] = cands[0]
        out.append(row)
    return ok, out, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    a = ap.parse_args()
    if not (a.verify_only or a.apply) or (a.verify_only and a.apply):
        sys.exit("pass exactly one of --verify-only / --apply")
    data = load_sqlite()
    print("sqlite counts:",
          {t: len(v) for t, v in data.items()})
    ok, normalized, report = verify_fk(data)
    for line in report:
        print(line)
    print("fk 1:1 mapping:", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit("FK mapping failed; aborting without touching Neon.")
    if a.verify_only:
        print("verify-only: no Neon writes performed.")
        return
    try:
        import psycopg2
    except ImportError:
        sys.exit("psycopg2 required (pip install psycopg2-binary).")
    if not a.dsn:
        sys.exit("--apply requires --dsn or DATABASE_URL (test branch DSN).")
    ddl = open(DDL, encoding="utf-8").read()
    import psycopg2.extras
    conn = psycopg2.connect(a.dsn)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
            for stmt in [
                "CREATE OR REPLACE VIEW v_executable_foods AS "
                "SELECT p.name AS place, p.region, p.time_slots, p.grade, p.maps_query,"
                " p.last_verified, p.op_status, p.atlas_state,"
                " c.title AS carrier, c.role, c.status AS carrier_status, c.evidence_as_of"
                " FROM food_places p LEFT JOIN dish_carriers c ON "
                "replace(c.place_id,'-','') = replace(p.notion_id,'-','')"
                " WHERE p.op_status = '營業中' AND p.atlas_state = 'ACTIVE'"
                " AND c.status = 'ACCEPTED'",
                "CREATE OR REPLACE VIEW v_points_query AS SELECT name, area, interest,"
                " mandatory, status, condition_gate, returnability, kid_note FROM points"
                " WHERE status IN ('ACTIVE','OPTIONAL') ORDER BY interest DESC, name",
                "CREATE OR REPLACE VIEW v_cards_gates AS SELECT slug, name, status,"
                " route, gates, transport, summary FROM cards ORDER BY slug",
                "CREATE OR REPLACE VIEW v_order_gaps AS SELECT kind, title, detail,"
                " amount, status FROM bookings ORDER BY kind, title",
            ]:
                cur.execute(stmt)
            for t in TABLES:
                rows = normalized if t == "dish_carriers" else data[t]
                if t == "evidence_log" and not rows:
                    continue
                cols = [c for c in COLUMNS[t]
                        if not (t == "evidence_log" and c == "id")]
                psycopg2.extras.execute_values(
                    cur,
                    "INSERT INTO %s (%s) VALUES %%s "
                    "ON CONFLICT DO NOTHING" % (t, ",".join(cols)),
                    [[r[c] for c in cols] for r in rows])
            cur.execute("SELECT count(*) FROM dish_carriers "
                        "c LEFT JOIN dishes d ON c.dish_id=d.notion_id "
                        "WHERE d.notion_id IS NULL")
            orphans_d = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM dish_carriers "
                        "c LEFT JOIN food_places p ON c.place_id=p.notion_id "
                        "WHERE p.notion_id IS NULL")
            orphans_p = cur.fetchone()[0]
            print("post-load orphans: dishes=%d places=%d" %
                  (orphans_d, orphans_p))
            if orphans_d or orphans_p:
                conn.rollback()
                sys.exit("orphan FK rows after load; rolled back.")
        conn.commit()
        print("applied to test branch (counts above); source SQLite untouched.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
