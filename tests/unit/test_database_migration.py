import sqlite3

from qa_manager.core.database import Database, SCHEMA


def test_existing_database_gets_compatible_defaults(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        connection.execute("INSERT INTO projects(id,name,frontend_url,created_at) VALUES('p','Legacy','http://localhost','now')")
        connection.execute("INSERT INTO scenarios(id,project_id,name,steps,expected) VALUES('s','p','Legacy','[]','[]')")
        connection.execute("INSERT INTO settings VALUES('security_enabled','true')")
    db = Database(path)
    db.initialize()
    db.initialize()  # A server restart must not reset user settings or duplicate data.
    project = db.fetchone("SELECT * FROM projects WHERE id='p'")
    scenario = db.fetchone("SELECT * FROM scenarios WHERE id='s'")
    assert project["zap_enabled"] is None
    assert project["trivy_enabled"] is False
    assert project["trivy_scanners"] == ["vuln", "misconfig", "secret"]
    assert scenario["regression_enabled"] is True
    assert scenario["group"] is None and scenario["order"] == 0
