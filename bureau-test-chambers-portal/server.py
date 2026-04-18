#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
CONFIGURED_DATA_DIR = os.environ.get("BUREAU_DATA_DIR", "").strip()
DATA_DIR = Path(CONFIGURED_DATA_DIR).expanduser().resolve() if CONFIGURED_DATA_DIR != "" else (ROOT / "data")
DATA_FILE = DATA_DIR / "accounts.json"
DATABASE_FILE = DATA_DIR / "accounts.db"
DOWNLOADS_DIR = ROOT / "downloads"
ENVIRONMENT = os.environ.get("BUREAU_ENV", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT in {"production", "prod", "live"}
PUBLIC_BASE_URL = os.environ.get("BUREAU_PUBLIC_BASE_URL", "").strip().rstrip("/")
HOST = os.environ.get("BUREAU_PORTAL_HOST", "0.0.0.0" if IS_PRODUCTION else "127.0.0.1")
PORT = int(os.environ.get("BUREAU_PORTAL_PORT", "8000"))
ROLES = {"player", "moderator", "director"}
DEFAULT_DIRECTOR_PASSWORD = "bureau-director-override"
DIRECTOR_USERNAME = os.environ.get("BUREAU_DIRECTOR_USERNAME", "director")
DIRECTOR_PASSWORD = os.environ.get("BUREAU_DIRECTOR_PASSWORD", DEFAULT_DIRECTOR_PASSWORD)
ENABLE_DEV_DEFAULTS = os.environ.get("BUREAU_ENABLE_DEV_DEFAULTS", "0" if IS_PRODUCTION else "1") == "1"
ALLOW_REGISTRATION = os.environ.get("BUREAU_ALLOW_REGISTRATION", "1") == "1"
REQUIRE_HTTPS = os.environ.get("BUREAU_REQUIRE_HTTPS", "1" if IS_PRODUCTION else "0") == "1"
SESSION_TTL_SECONDS = int(os.environ.get("BUREAU_SESSION_TTL_SECONDS", str(60 * 60 * 12)))
LOGIN_WINDOW_SECONDS = int(os.environ.get("BUREAU_LOGIN_WINDOW_SECONDS", "300"))
LOGIN_MAX_ATTEMPTS = int(os.environ.get("BUREAU_LOGIN_MAX_ATTEMPTS", "8"))
PBKDF2_ITERATIONS = int(os.environ.get("BUREAU_PBKDF2_ITERATIONS", "240000"))
PASSWORD_RESET_TTL_SECONDS = int(os.environ.get("BUREAU_PASSWORD_RESET_TTL_SECONDS", str(60 * 30)))
RESET_LINK_PREVIEW_ENABLED = os.environ.get("BUREAU_RESET_LINK_PREVIEW", "0" if IS_PRODUCTION else "1") == "1"
MAX_JSON_BODY_BYTES = int(os.environ.get("BUREAU_MAX_JSON_BODY_BYTES", "65536"))
TOS_VERSION = "2026-04-11"
MAX_DISPLAY_NAME_LENGTH = 24
MAX_LEVEL_NAME_LENGTH = 80
MAX_LEVEL_DESCRIPTION_LENGTH = 280
MAX_MODERATION_REASON_LENGTH = 240
ALLOWED_CHAMBER_SIZES = {"small", "large"}
ALLOWED_HAT_IDS = {"none", "baseball_cap", "top_hat", "traffic_cone"}
ALLOWED_BUILD_EXTENSIONS = {".zip", ".dmg", ".exe", ".appimage"}
DIFFICULTY_TOKEN_REWARDS = {
	1: 10,
	2: 25,
	3: 50,
	4: 75,
	5: 100,
}
PORTAL_FALLBACK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<title>Bureau Account Portal</title>
	<style>
		body {
			margin: 0;
			font-family: Arial, sans-serif;
			background: #08111d;
			color: #eef7ff;
			display: flex;
			align-items: center;
			justify-content: center;
			min-height: 100vh;
		}
		main {
			width: min(720px, calc(100vw - 48px));
			padding: 32px;
			border: 1px solid rgba(80, 200, 255, 0.55);
			border-radius: 18px;
			background: rgba(10, 18, 28, 0.92);
			box-shadow: 0 0 32px rgba(0, 180, 255, 0.18);
		}
		h1 {
			margin-top: 0;
		}
		code {
			background: rgba(255, 255, 255, 0.08);
			padding: 2px 6px;
			border-radius: 6px;
		}
	</style>
</head>
<body>
	<main>
		<h1>Bureau Account Portal</h1>
		<p>The full portal shell could not be loaded, but the service is online.</p>
		<p>Try reloading the page. If this keeps happening, confirm that <code>index.html</code>, <code>app.js</code>, and <code>styles.css</code> are present beside the server.</p>
	</main>
</body>
</html>
"""

LOGIN_ATTEMPTS: dict[str, list[float]] = {}


def default_accounts() -> dict[str, dict]:
	accounts: dict[str, dict] = {
		"acct_director": {
			"account_id": "acct_director",
			"username": DIRECTOR_USERNAME,
			"password": DIRECTOR_PASSWORD,
			"display_name": "Facility Director",
			"suit_preset_index": 1,
			"accent_preset_index": 0,
			"visor_preset_index": 0,
			"role": "director",
			"banned": False,
		},
	}
	if ENABLE_DEV_DEFAULTS:
		accounts["acct_local"] = {
			"account_id": "acct_local",
			"username": "localuser",
			"password": "localpass",
			"display_name": "Test Subject",
			"suit_preset_index": 0,
			"accent_preset_index": 0,
			"visor_preset_index": 0,
			"role": "player",
			"banned": False,
		}
	return accounts


def ensure_storage() -> None:
	DATA_DIR.mkdir(parents=True, exist_ok=True)
	DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
	with get_db_connection() as connection:
		connection.execute(
			"""
			CREATE TABLE IF NOT EXISTS accounts (
				account_id TEXT PRIMARY KEY,
				username TEXT NOT NULL UNIQUE COLLATE NOCASE,
				password_hash TEXT NOT NULL,
				display_name TEXT NOT NULL,
				suit_preset_index INTEGER NOT NULL,
				accent_preset_index INTEGER NOT NULL,
				visor_preset_index INTEGER NOT NULL,
				owned_hat_ids TEXT NOT NULL DEFAULT '["none"]',
				equipped_hat_id TEXT NOT NULL DEFAULT 'none',
				role TEXT NOT NULL,
				banned INTEGER NOT NULL DEFAULT 0,
				tos_version TEXT NOT NULL DEFAULT '',
				tos_accepted_at INTEGER NOT NULL DEFAULT 0
			)
			"""
		)
		for statement in (
			"ALTER TABLE accounts ADD COLUMN tos_version TEXT NOT NULL DEFAULT ''",
			"ALTER TABLE accounts ADD COLUMN tos_accepted_at INTEGER NOT NULL DEFAULT 0",
			"""ALTER TABLE accounts ADD COLUMN owned_hat_ids TEXT NOT NULL DEFAULT '["none"]'""",
			"ALTER TABLE accounts ADD COLUMN equipped_hat_id TEXT NOT NULL DEFAULT 'none'",
		):
			try:
				connection.execute(statement)
			except sqlite3.OperationalError:
				pass
		connection.execute(
			"""
			CREATE TABLE IF NOT EXISTS moderation_audit_log (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				created_at INTEGER NOT NULL,
				actor_account_id TEXT NOT NULL,
				actor_username TEXT NOT NULL,
				actor_role TEXT NOT NULL,
				target_account_id TEXT NOT NULL,
				target_username TEXT NOT NULL,
				action TEXT NOT NULL,
				reason TEXT NOT NULL DEFAULT '',
				remote_ip TEXT NOT NULL
			)
			"""
		)
		try:
			connection.execute("ALTER TABLE moderation_audit_log ADD COLUMN reason TEXT NOT NULL DEFAULT ''")
		except sqlite3.OperationalError:
			pass
		connection.execute(
			"""
			CREATE TABLE IF NOT EXISTS password_reset_tokens (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				account_id TEXT NOT NULL,
				token_hash TEXT NOT NULL UNIQUE,
				created_at INTEGER NOT NULL,
				expires_at INTEGER NOT NULL,
				used_at INTEGER NOT NULL DEFAULT 0,
				requester_ip TEXT NOT NULL
			)
			"""
		)
		connection.execute(
			"""
			CREATE TABLE IF NOT EXISTS sessions (
				token_hash TEXT PRIMARY KEY,
				account_id TEXT NOT NULL,
				remote_ip TEXT NOT NULL,
				user_agent TEXT NOT NULL DEFAULT '',
				created_at INTEGER NOT NULL,
				expires_at INTEGER NOT NULL,
				last_seen_at INTEGER NOT NULL
			)
			"""
		)
		connection.execute("CREATE INDEX IF NOT EXISTS idx_sessions_account_id ON sessions(account_id)")
		connection.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)")
		connection.execute(
			"""
			CREATE TABLE IF NOT EXISTS published_levels (
				level_id TEXT PRIMARY KEY,
				name TEXT NOT NULL,
				description TEXT NOT NULL,
				author_account_id TEXT NOT NULL,
				author_username TEXT NOT NULL,
				author_display_name TEXT NOT NULL,
				chamber_size TEXT NOT NULL,
				difficulty_stars INTEGER NOT NULL,
				token_reward INTEGER NOT NULL,
				created_at INTEGER NOT NULL,
				updated_at INTEGER NOT NULL
			)
			"""
		)
		connection.commit()
	migrate_json_accounts()
	ensure_default_accounts()


def clamp_preset(value) -> int:
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		parsed = 0
	return max(0, min(3, parsed))


def clamp_difficulty(value) -> int:
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		parsed = 1
	return max(1, min(5, parsed))


def token_reward_for_difficulty(value) -> int:
	return int(DIFFICULTY_TOKEN_REWARDS[clamp_difficulty(value)])


def normalize_display_name(value: str, fallback: str = "Test Subject") -> str:
	text = " ".join(str(value or "").strip().split())
	if text == "":
		text = fallback
	return text[:MAX_DISPLAY_NAME_LENGTH]


def normalize_level_name(value: str) -> str:
	text = " ".join(str(value or "").strip().split())
	return (text or "Community Chamber")[:MAX_LEVEL_NAME_LENGTH]


def normalize_level_description(value: str) -> str:
	text = " ".join(str(value or "").strip().split())
	return (text or "User-made chamber")[:MAX_LEVEL_DESCRIPTION_LENGTH]


def normalize_chamber_size(value: str) -> str:
	size = str(value or "small").strip().lower()
	return size if size in ALLOWED_CHAMBER_SIZES else "small"


def validate_level_id(value: str) -> bool:
	if len(value) < 3 or len(value) > 96:
		return False
	return all(character.isalnum() or character in {"_", "-"} for character in value)


def validate_username(value: str) -> bool:
	if len(value) < 3 or len(value) > 24:
		return False
	return value.replace("_", "").replace("-", "").isalnum()


def validate_password(value: str) -> bool:
	return len(value) >= 8


def hash_password(password: str, salt: str | None = None) -> str:
	salt_bytes = secrets.token_bytes(16) if salt is None else base64.b64decode(salt.encode("utf-8"))
	digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, PBKDF2_ITERATIONS)
	return "pbkdf2_sha256$%d$%s$%s" % (
		PBKDF2_ITERATIONS,
		base64.b64encode(salt_bytes).decode("utf-8"),
		base64.b64encode(digest).decode("utf-8"),
	)


def verify_password(password: str, encoded_hash: str) -> bool:
	try:
		algorithm, iteration_text, salt, digest = encoded_hash.split("$", 3)
		if algorithm != "pbkdf2_sha256":
			return False
		iterations = int(iteration_text)
		salt_bytes = base64.b64decode(salt.encode("utf-8"))
		expected = base64.b64decode(digest.encode("utf-8"))
	except (ValueError, TypeError):
		return False
	candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
	return hmac.compare_digest(candidate, expected)


def hash_session_token(token: str) -> str:
	return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session(account: dict, remote_ip: str) -> dict:
	cleanup_expired_sessions()
	token = secrets.token_urlsafe(32)
	now = int(time.time())
	expires_at = now + SESSION_TTL_SECONDS
	with get_db_connection() as connection:
		connection.execute(
			"""
			INSERT OR REPLACE INTO sessions (
				token_hash, account_id, remote_ip, user_agent, created_at, expires_at, last_seen_at
			) VALUES (?, ?, ?, ?, ?, ?, ?)
			""",
			(
				hash_session_token(token),
				account["account_id"],
				remote_ip,
				"",
				now,
				expires_at,
				now,
			),
		)
		connection.commit()
	return {
		"token": token,
		"expires_at": expires_at,
	}


def cleanup_expired_sessions() -> None:
	now = int(time.time())
	with get_db_connection() as connection:
		connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
		connection.commit()


def revoke_session_token(token: str) -> None:
	if token.strip() == "":
		return
	with get_db_connection() as connection:
		connection.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_session_token(token),))
		connection.commit()


def revoke_sessions_for_account(account_id: str) -> None:
	if account_id.strip() == "":
		return
	with get_db_connection() as connection:
		connection.execute("DELETE FROM sessions WHERE account_id = ?", (account_id,))
		connection.commit()


def _prune_login_attempts() -> None:
	now = time.time()
	for key in list(LOGIN_ATTEMPTS.keys()):
		LOGIN_ATTEMPTS[key] = [stamp for stamp in LOGIN_ATTEMPTS[key] if now - stamp <= LOGIN_WINDOW_SECONDS]
		if not LOGIN_ATTEMPTS[key]:
			LOGIN_ATTEMPTS.pop(key, None)


def is_login_throttled(identity: str) -> bool:
	_prune_login_attempts()
	return len(LOGIN_ATTEMPTS.get(identity, [])) >= LOGIN_MAX_ATTEMPTS


def register_login_failure(identity: str) -> None:
	_prune_login_attempts()
	LOGIN_ATTEMPTS.setdefault(identity, []).append(time.time())


def clear_login_failures(identity: str) -> None:
	LOGIN_ATTEMPTS.pop(identity, None)


def normalize_role(value) -> str:
	role = str(value or "player").strip().lower()
	return role if role in ROLES else "player"


def normalize_hat_ids(value) -> list[str]:
	items = value
	if isinstance(items, str):
		try:
			items = json.loads(items)
		except json.JSONDecodeError:
			items = [items]
	if not isinstance(items, list):
		items = []
	normalized = ["none"]
	for item in items:
		hat_id = str(item or "").strip().lower()
		if hat_id in ALLOWED_HAT_IDS and hat_id not in normalized:
			normalized.append(hat_id)
	return normalized


def normalize_equipped_hat_id(value, owned_hat_ids: list[str]) -> str:
	hat_id = str(value or "none").strip().lower()
	if hat_id not in ALLOWED_HAT_IDS:
		return "none"
	if hat_id not in owned_hat_ids:
		return "none"
	return hat_id


def normalize_account(payload: dict | None, fallback_account_id: str | None = None) -> dict:
	source = payload or {}
	account_id = str(source.get("account_id") or fallback_account_id or "").strip()
	raw_password = str(source.get("password", ""))
	password_hash = str(source.get("password_hash", "")).strip()
	if password_hash == "" and raw_password != "":
		password_hash = hash_password(raw_password)
	owned_hat_ids = normalize_hat_ids(source.get("owned_hat_ids", ["none"]))
	equipped_hat_id = normalize_equipped_hat_id(source.get("equipped_hat_id", "none"), owned_hat_ids)
	return {
		"account_id": account_id,
		"username": str(source.get("username", "")).strip(),
		"password_hash": password_hash,
		"display_name": normalize_display_name(source.get("display_name", "Test Subject")),
		"suit_preset_index": clamp_preset(source.get("suit_preset_index", 0)),
		"accent_preset_index": clamp_preset(source.get("accent_preset_index", 0)),
		"visor_preset_index": clamp_preset(source.get("visor_preset_index", 0)),
		"owned_hat_ids": owned_hat_ids,
		"equipped_hat_id": equipped_hat_id,
		"role": normalize_role(source.get("role", "player")),
		"banned": bool(source.get("banned", False)),
		"tos_version": str(source.get("tos_version", "")).strip(),
		"tos_accepted_at": int(source.get("tos_accepted_at", 0) or 0),
	}


def get_db_connection() -> sqlite3.Connection:
	connection = sqlite3.connect(DATABASE_FILE)
	connection.row_factory = sqlite3.Row
	return connection


def row_to_account(row: sqlite3.Row | dict | None) -> dict | None:
	if row is None:
		return None
	source = dict(row)
	source["banned"] = bool(source.get("banned", False))
	return normalize_account(source, str(source.get("account_id", "")).strip())


def public_account_view(account: dict) -> dict:
	return {
		"account_id": account["account_id"],
		"username": account["username"],
		"display_name": account["display_name"],
		"suit_preset_index": account["suit_preset_index"],
		"accent_preset_index": account["accent_preset_index"],
		"visor_preset_index": account["visor_preset_index"],
		"owned_hat_ids": list(account.get("owned_hat_ids", ["none"])),
		"equipped_hat_id": str(account.get("equipped_hat_id", "none")),
		"role": account["role"],
		"banned": account["banned"],
		"tos_version": account.get("tos_version", ""),
		"tos_accepted_at": account.get("tos_accepted_at", 0),
	}


def normalize_published_level(payload: dict | None, author: dict | None = None) -> dict:
	source = payload or {}
	level_id = str(source.get("level_id", source.get("id", ""))).strip()
	name = normalize_level_name(source.get("name", ""))
	description = normalize_level_description(source.get("description", ""))
	chamber_size = normalize_chamber_size(source.get("chamber_size", source.get("size", "small")))
	difficulty_stars = clamp_difficulty(source.get("difficulty_stars", 1))
	author_account_id = str(source.get("author_account_id", author.get("account_id", "") if author else "")).strip()
	author_username = str(source.get("author_username", source.get("author", author.get("username", "") if author else ""))).strip()
	author_display_name = normalize_display_name(
		source.get(
			"author_display_name",
			author.get("display_name", author_username or "Local Creator") if author else source.get("author", "Local Creator"),
		),
		author_username or "Local Creator",
	)
	return {
		"level_id": level_id,
		"name": name,
		"description": description,
		"author_account_id": author_account_id,
		"author_username": author_username,
		"author_display_name": author_display_name or author_username or "Local Creator",
		"chamber_size": chamber_size,
		"difficulty_stars": difficulty_stars,
		"token_reward": token_reward_for_difficulty(difficulty_stars),
	}


def list_published_levels(limit: int = 200) -> list[dict]:
	with get_db_connection() as connection:
		rows = connection.execute(
			"""
			SELECT level_id, name, description, author_account_id, author_username, author_display_name,
			       chamber_size, difficulty_stars, token_reward, created_at, updated_at
			FROM published_levels
			ORDER BY updated_at DESC, created_at DESC
			LIMIT ?
			""",
			(limit,),
		).fetchall()
	return [dict(row) for row in rows]


def save_published_level(level: dict) -> dict:
	normalized = normalize_published_level(level)
	existing = get_published_level(normalized["level_id"])
	if existing is not None and existing["author_account_id"] != normalized["author_account_id"]:
		raise PermissionError("That release slot belongs to another account.")
	now = int(time.time())
	created_at = int(existing.get("created_at", now)) if existing is not None else now
	with get_db_connection() as connection:
		connection.execute(
			"""
			INSERT INTO published_levels (
				level_id, name, description, author_account_id, author_username, author_display_name,
				chamber_size, difficulty_stars, token_reward, created_at, updated_at
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			ON CONFLICT(level_id) DO UPDATE SET
				name=excluded.name,
				description=excluded.description,
				author_username=excluded.author_username,
				author_display_name=excluded.author_display_name,
				chamber_size=excluded.chamber_size,
				difficulty_stars=excluded.difficulty_stars,
				token_reward=excluded.token_reward,
				updated_at=excluded.updated_at
			""",
			(
				normalized["level_id"],
				normalized["name"],
				normalized["description"],
				normalized["author_account_id"],
				normalized["author_username"],
				normalized["author_display_name"],
				normalized["chamber_size"],
				normalized["difficulty_stars"],
				normalized["token_reward"],
				created_at,
				now,
			),
		)
		connection.commit()
	saved = get_published_level(normalized["level_id"])
	return saved if saved is not None else normalized


def get_published_level(level_id: str) -> dict | None:
	if level_id.strip() == "":
		return None
	with get_db_connection() as connection:
		row = connection.execute(
			"""
			SELECT level_id, name, description, author_account_id, author_username, author_display_name,
			       chamber_size, difficulty_stars, token_reward, created_at, updated_at
			FROM published_levels
			WHERE level_id = ?
			""",
			(level_id,),
		).fetchone()
	return dict(row) if row is not None else None


def list_available_builds(limit: int = 20) -> list[dict]:
	if not DOWNLOADS_DIR.exists():
		return []
	builds: list[dict] = []
	for file_path in DOWNLOADS_DIR.iterdir():
		if not file_path.is_file():
			continue
		if file_path.suffix.lower() not in ALLOWED_BUILD_EXTENSIONS:
			continue
		stats = file_path.stat()
		builds.append({
			"id": file_path.stem,
			"name": file_path.stem.replace("-", " ").replace("_", " ").title(),
			"filename": file_path.name,
			"url": f"/downloads/{file_path.name}",
			"size_bytes": int(stats.st_size),
			"updated_at": int(stats.st_mtime),
		})
	builds.sort(key=lambda entry: int(entry["updated_at"]), reverse=True)
	return builds[:limit]


def get_session_account(handler: BaseHTTPRequestHandler, payload: dict | None = None) -> dict | None:
	cleanup_expired_sessions()
	session_token = handler.headers.get("X-Session-Token", "").strip()
	if session_token == "" and payload is not None:
		session_token = str(payload.get("session_token", "")).strip()
	if session_token == "":
		return None
	with get_db_connection() as connection:
		session = connection.execute(
			"""
			SELECT account_id, expires_at
			FROM sessions
			WHERE token_hash = ?
			""",
			(hash_session_token(session_token),),
		).fetchone()
		if session is None:
			return None
		now = int(time.time())
		if int(session["expires_at"] or 0) <= now:
			connection.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_session_token(session_token),))
			connection.commit()
			return None
		connection.execute(
			"UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?",
			(now, hash_session_token(session_token)),
		)
		connection.commit()
	account = get_account_by_id(str(session["account_id"]))
	if account is None or account["banned"]:
		revoke_session_token(session_token)
		return None
	return account


def load_accounts() -> dict[str, dict]:
	with get_db_connection() as connection:
		rows = connection.execute("SELECT * FROM accounts ORDER BY username COLLATE NOCASE ASC").fetchall()
	return {account["account_id"]: account for account in (row_to_account(row) for row in rows) if account is not None}


def save_accounts(accounts: dict[str, dict]) -> None:
	DATA_DIR.mkdir(parents=True, exist_ok=True)
	with get_db_connection() as connection:
		connection.execute("BEGIN")
		connection.execute("DELETE FROM accounts")
		for account_id, payload in accounts.items():
			save_account(normalize_account(payload, str(account_id)), connection)
		connection.commit()


def save_account(account: dict, connection: sqlite3.Connection | None = None) -> None:
	normalized = normalize_account(account, account.get("account_id"))
	owns_connection = connection is None
	if owns_connection:
		connection = get_db_connection()
	try:
		connection.execute(
			"""
			INSERT INTO accounts (
				account_id,
				username,
				password_hash,
				display_name,
				suit_preset_index,
				accent_preset_index,
				visor_preset_index,
				owned_hat_ids,
				equipped_hat_id,
				role,
				banned,
				tos_version,
				tos_accepted_at
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			ON CONFLICT(account_id) DO UPDATE SET
				username=excluded.username,
				password_hash=excluded.password_hash,
				display_name=excluded.display_name,
				suit_preset_index=excluded.suit_preset_index,
				accent_preset_index=excluded.accent_preset_index,
				visor_preset_index=excluded.visor_preset_index,
				owned_hat_ids=excluded.owned_hat_ids,
				equipped_hat_id=excluded.equipped_hat_id,
				role=excluded.role,
				banned=excluded.banned,
				tos_version=excluded.tos_version,
				tos_accepted_at=excluded.tos_accepted_at
			""",
			(
				normalized["account_id"],
				normalized["username"],
				normalized["password_hash"],
				normalized["display_name"],
				normalized["suit_preset_index"],
				normalized["accent_preset_index"],
				normalized["visor_preset_index"],
				json.dumps(normalized.get("owned_hat_ids", ["none"])),
				str(normalized.get("equipped_hat_id", "none")),
				normalized["role"],
				1 if normalized["banned"] else 0,
				normalized.get("tos_version", ""),
				int(normalized.get("tos_accepted_at", 0) or 0),
			),
		)
		if owns_connection:
			connection.commit()
	finally:
		if owns_connection:
			connection.close()


def get_account_by_id(account_id: str) -> dict | None:
	with get_db_connection() as connection:
		row = connection.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
	return row_to_account(row)


def next_account_id(accounts: dict[str, dict]) -> str:
	index = 1
	while True:
		candidate = f"acct_{index:04d}"
		if candidate not in accounts:
			return candidate
		index += 1


def find_account_by_username(username: str) -> dict | None:
	target = username.strip()
	if target == "":
		return None
	with get_db_connection() as connection:
		row = connection.execute("SELECT * FROM accounts WHERE username = ? COLLATE NOCASE", (target,)).fetchone()
	return row_to_account(row)


def list_accounts_for(viewer: dict) -> list[dict]:
	accounts = load_accounts()
	ordered = sorted(accounts.values(), key=lambda account: (account["role"] != "director", account["role"] != "moderator", account["display_name"].lower()))
	return [public_account_view(account) for account in ordered]


def authenticate(username: str, password: str) -> dict | None:
	account = find_account_by_username(username)
	if account is None:
		return None
	if not verify_password(password, account["password_hash"]):
		return None
	return account


def verify_account_password(account: dict, password: str) -> bool:
	if account is None:
		return False
	return verify_password(password, account.get("password_hash", ""))


def migrate_json_accounts() -> None:
	with get_db_connection() as connection:
		row = connection.execute("SELECT COUNT(*) AS count FROM accounts").fetchone()
		existing_count = int(row["count"]) if row is not None else 0
	if existing_count > 0 or not DATA_FILE.exists():
		return
	try:
		raw_accounts = json.loads(DATA_FILE.read_text(encoding="utf-8"))
	except json.JSONDecodeError:
		return
	if not isinstance(raw_accounts, dict):
		return
	with get_db_connection() as connection:
		for account_id, payload in raw_accounts.items():
			if not isinstance(payload, dict):
				continue
			save_account(normalize_account(payload, str(account_id)), connection)
		connection.commit()


def ensure_default_accounts() -> None:
	with get_db_connection() as connection:
		for account_id, account in default_accounts().items():
			existing = connection.execute("SELECT account_id FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
			if existing is None:
				save_account(normalize_account(account, account_id), connection)
		connection.commit()


def list_audit_entries(limit: int = 50) -> list[dict]:
	with get_db_connection() as connection:
		rows = connection.execute(
			"""
			SELECT id, created_at, actor_account_id, actor_username, actor_role, target_account_id, target_username, action, remote_ip
			, reason
			FROM moderation_audit_log
			ORDER BY id DESC
			LIMIT ?
			""",
			(limit,),
		).fetchall()
	return [dict(row) for row in rows]


def audit_entries_for(viewer: dict) -> list[dict]:
	if viewer["role"] not in {"director", "moderator"}:
		return []
	return list_audit_entries()


def record_moderation_audit(viewer: dict, target: dict, action: str, reason: str, remote_ip: str) -> None:
	with get_db_connection() as connection:
		connection.execute(
			"""
			INSERT INTO moderation_audit_log (
				created_at,
				actor_account_id,
				actor_username,
				actor_role,
				target_account_id,
				target_username,
				action,
				reason,
				remote_ip
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
			""",
			(
				int(time.time()),
				viewer["account_id"],
				viewer["username"],
				viewer["role"],
				target["account_id"],
				target["username"],
				action,
				reason,
				remote_ip,
			),
		)
		connection.commit()


def hash_reset_token(token: str) -> str:
	return hashlib.sha256(token.encode("utf-8")).hexdigest()


def purge_expired_reset_tokens() -> None:
	now = int(time.time())
	with get_db_connection() as connection:
		connection.execute("DELETE FROM password_reset_tokens WHERE used_at > 0 OR expires_at <= ?", (now,))
		connection.commit()


def issue_password_reset_token(account: dict, requester_ip: str) -> str:
	purge_expired_reset_tokens()
	token = secrets.token_urlsafe(32)
	now = int(time.time())
	with get_db_connection() as connection:
		connection.execute("DELETE FROM password_reset_tokens WHERE account_id = ?", (account["account_id"],))
		connection.execute(
			"""
			INSERT INTO password_reset_tokens (
				account_id,
				token_hash,
				created_at,
				expires_at,
				used_at,
				requester_ip
			) VALUES (?, ?, ?, ?, 0, ?)
			""",
			(
				account["account_id"],
				hash_reset_token(token),
				now,
				now + PASSWORD_RESET_TTL_SECONDS,
				requester_ip,
			),
		)
		connection.commit()
	return token


def consume_password_reset_token(token: str) -> dict | None:
	purge_expired_reset_tokens()
	token_hash = hash_reset_token(token)
	now = int(time.time())
	with get_db_connection() as connection:
		row = connection.execute(
			"""
			SELECT account_id, expires_at, used_at
			FROM password_reset_tokens
			WHERE token_hash = ?
			""",
			(token_hash,),
		).fetchone()
		if row is None:
			return None
		if int(row["used_at"] or 0) > 0 or int(row["expires_at"] or 0) <= now:
			connection.execute("DELETE FROM password_reset_tokens WHERE token_hash = ?", (token_hash,))
			connection.commit()
			return None
		connection.execute("UPDATE password_reset_tokens SET used_at = ? WHERE token_hash = ?", (now, token_hash))
		connection.commit()
	account = get_account_by_id(str(row["account_id"]))
	return account


def request_scheme(handler: BaseHTTPRequestHandler) -> str:
	forwarded = handler.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip().lower()
	if forwarded in {"http", "https"}:
		return forwarded
	return "https" if getattr(handler.connection, "cipher", None) else "http"


def is_secure_request(handler: BaseHTTPRequestHandler) -> bool:
	return request_scheme(handler) == "https"


def should_return_reset_preview(handler: BaseHTTPRequestHandler) -> bool:
	if not RESET_LINK_PREVIEW_ENABLED:
		return False
	if IS_PRODUCTION and REQUIRE_HTTPS and not is_secure_request(handler):
		return False
	return True


def build_reset_url(handler: BaseHTTPRequestHandler, token: str) -> str:
	if PUBLIC_BASE_URL != "":
		return f"{PUBLIC_BASE_URL}/?reset_token={token}"
	host = handler.headers.get("Host", f"{HOST}:{PORT}") or f"{HOST}:{PORT}"
	return f"{request_scheme(handler)}://{host}/?reset_token={token}"


class PortalHandler(BaseHTTPRequestHandler):
	server_version = "BureauAccountPortal/3.0"

	def _send_bytes(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK, include_body: bool = True) -> None:
		self.send_response(status)
		self.send_header("Content-Type", content_type)
		self.send_header("Content-Length", str(len(body)))
		self._write_security_headers()
		self.end_headers()
		if include_body:
			self.wfile.write(body)

	def _redirect_to_https_if_required(self, parsed_path) -> bool:
		if not REQUIRE_HTTPS or is_secure_request(self):
			return False
		if PUBLIC_BASE_URL == "":
			self._send_json({"error": "HTTPS is required for this portal."}, HTTPStatus.FORBIDDEN)
			return True
		target = f"{PUBLIC_BASE_URL}{parsed_path.path or '/'}"
		if parsed_path.query:
			target += f"?{parsed_path.query}"
		if self.command == "GET":
			self.send_response(HTTPStatus.TEMPORARY_REDIRECT)
			self.send_header("Location", target)
			self._write_security_headers()
			self.end_headers()
		else:
			self._send_json({"error": "HTTPS is required for this portal."}, HTTPStatus.FORBIDDEN)
		return True

	def _write_security_headers(self) -> None:
		self.send_header("Cache-Control", "no-store")
		self.send_header("X-Content-Type-Options", "nosniff")
		self.send_header("X-Frame-Options", "DENY")
		self.send_header("Referrer-Policy", "same-origin")
		self.send_header("Cross-Origin-Opener-Policy", "same-origin")
		self.send_header("Cross-Origin-Resource-Policy", "same-origin")
		self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
		self.send_header(
			"Content-Security-Policy",
			"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
			"base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'",
		)
		if REQUIRE_HTTPS or is_secure_request(self):
			self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

	def do_GET(self) -> None:
		try:
			parsed = urlparse(self.path)
			if self._redirect_to_https_if_required(parsed):
				return
			if parsed.path == "/favicon.ico":
				self.send_response(HTTPStatus.NO_CONTENT)
				self.send_header("Content-Length", "0")
				self._write_security_headers()
				self.end_headers()
				return
			if parsed.path == "/healthz":
				self._send_json({
					"ok": True,
					"environment": ENVIRONMENT,
					"public_base_url": PUBLIC_BASE_URL,
					"registration_enabled": ALLOW_REGISTRATION,
				})
				return
			if parsed.path == "/api/builds":
				self._send_json({"builds": list_available_builds()})
				return
			if parsed.path == "/api/levels":
				self._send_json({"levels": list_published_levels()})
				return
			if parsed.path in ("/", "/index.html"):
				self._send_portal_page()
				return
			self._send_static(parsed.path.lstrip("/"))
		except Exception as error:
			self._handle_internal_error(error)

	def do_HEAD(self) -> None:
		try:
			parsed = urlparse(self.path)
			if self._redirect_to_https_if_required(parsed):
				return
			if parsed.path == "/favicon.ico":
				self.send_response(HTTPStatus.NO_CONTENT)
				self.send_header("Content-Length", "0")
				self._write_security_headers()
				self.end_headers()
				return
			if parsed.path == "/healthz":
				body = json.dumps({
					"ok": True,
					"environment": ENVIRONMENT,
					"public_base_url": PUBLIC_BASE_URL,
					"registration_enabled": ALLOW_REGISTRATION,
				}, indent=2).encode("utf-8")
				self._send_bytes(body, "application/json; charset=utf-8", HTTPStatus.OK, False)
				return
			if parsed.path == "/api/builds":
				body = json.dumps({"builds": list_available_builds()}, indent=2).encode("utf-8")
				self._send_bytes(body, "application/json; charset=utf-8", HTTPStatus.OK, False)
				return
			if parsed.path == "/api/levels":
				body = json.dumps({"levels": list_published_levels()}, indent=2).encode("utf-8")
				self._send_bytes(body, "application/json; charset=utf-8", HTTPStatus.OK, False)
				return
			if parsed.path in ("/", "/index.html"):
				self._send_portal_page(False)
				return
			self._send_static(parsed.path.lstrip("/"), False)
		except Exception as error:
			self._handle_internal_error(error)

	def do_POST(self) -> None:
		try:
			parsed = urlparse(self.path)
			if self._redirect_to_https_if_required(parsed):
				return
			payload = self._read_json_body()
			if payload is None:
				return

			if parsed.path == "/api/auth/login":
				self._handle_login(payload)
				return
			if parsed.path == "/api/auth/register":
				self._handle_register(payload)
				return
			if parsed.path == "/api/auth/request-password-reset":
				self._handle_request_password_reset(payload)
				return
			if parsed.path == "/api/auth/reset-password":
				self._handle_reset_password(payload)
				return
			if parsed.path == "/api/account":
				self._handle_save_account(payload)
				return
			if parsed.path == "/api/account/password":
				self._handle_change_password(payload)
				return
			if parsed.path == "/api/moderation":
				self._handle_moderation(payload)
				return
			if parsed.path == "/api/levels/publish":
				self._handle_publish_level(payload)
				return
			if parsed.path == "/api/auth/logout":
				self._handle_logout(payload)
				return

			self.send_error(HTTPStatus.NOT_FOUND, "Unknown API route")
		except Exception as error:
			self._handle_internal_error(error)

	def _handle_login(self, payload: dict) -> None:
		username = str(payload.get("username", "")).strip()
		password = str(payload.get("password", ""))
		identity = "%s:%s" % (self.client_address[0], username.lower())
		if is_login_throttled(identity):
			self._send_json({"error": "Too many login attempts. Please wait a few minutes and try again."}, HTTPStatus.TOO_MANY_REQUESTS)
			return
		account = authenticate(username, password)
		if account is None:
			register_login_failure(identity)
			self._send_json({"error": "Invalid username or password."}, HTTPStatus.FORBIDDEN)
			return
		if account["banned"]:
			self._send_json({"error": "This account has been banned."}, HTTPStatus.FORBIDDEN)
			return
		clear_login_failures(identity)
		session = issue_session(account, self.client_address[0])
		self._send_json({
			"account": public_account_view(account),
			"accounts": list_accounts_for(account) if account["role"] in {"director", "moderator"} else [],
			"audit_log": audit_entries_for(account),
			"session": session,
		})

	def _handle_register(self, payload: dict) -> None:
		if not ALLOW_REGISTRATION:
			self._send_json({"error": "Account registration is currently disabled."}, HTTPStatus.FORBIDDEN)
			return
		accounts = load_accounts()
		username = str(payload.get("username", "")).strip()
		password = str(payload.get("password", ""))
		display_name = normalize_display_name(payload.get("display_name", ""), "Test Subject")
		tos_accepted = bool(payload.get("accept_tos", False))
		if username == "" or password == "":
			self._send_json({"error": "Username and password are required."}, HTTPStatus.BAD_REQUEST)
			return
		if not tos_accepted:
			self._send_json({"error": "You must agree to the Terms of Service before creating an account."}, HTTPStatus.BAD_REQUEST)
			return
		if not validate_username(username):
			self._send_json({"error": "Username must be 3-24 characters and use only letters, numbers, dashes, or underscores."}, HTTPStatus.BAD_REQUEST)
			return
		if not validate_password(password):
			self._send_json({"error": "Password must be at least 8 characters long."}, HTTPStatus.BAD_REQUEST)
			return
		if find_account_by_username(username) is not None:
			self._send_json({"error": "That username is already taken."}, HTTPStatus.CONFLICT)
			return
		account_id = next_account_id(accounts)
		account = normalize_account({
			"account_id": account_id,
			"username": username,
			"password": password,
			"display_name": display_name,
			"suit_preset_index": 0,
			"accent_preset_index": 0,
			"visor_preset_index": 0,
			"role": "player",
			"banned": False,
			"tos_version": TOS_VERSION,
			"tos_accepted_at": int(time.time()),
		}, account_id)
		save_account(account)
		session = issue_session(account, self.client_address[0])
		self._send_json({"account": public_account_view(account), "accounts": [], "audit_log": [], "session": session}, HTTPStatus.CREATED)

	def _handle_save_account(self, payload: dict) -> None:
		account = get_session_account(self, payload)
		if account is None:
			account = authenticate(str(payload.get("username", "")).strip(), str(payload.get("password", "")))
		if account is None:
			self._send_json({"error": "Authentication required."}, HTTPStatus.FORBIDDEN)
			return
		if account["banned"]:
			self._send_json({"error": "This account has been banned."}, HTTPStatus.FORBIDDEN)
			return
		account["display_name"] = normalize_display_name(payload.get("display_name", account["display_name"]), account["display_name"])
		account["suit_preset_index"] = clamp_preset(payload.get("suit_preset_index", account["suit_preset_index"]))
		account["accent_preset_index"] = clamp_preset(payload.get("accent_preset_index", account["accent_preset_index"]))
		account["visor_preset_index"] = clamp_preset(payload.get("visor_preset_index", account["visor_preset_index"]))
		account["owned_hat_ids"] = normalize_hat_ids(payload.get("owned_hat_ids", account.get("owned_hat_ids", ["none"])))
		account["equipped_hat_id"] = normalize_equipped_hat_id(payload.get("equipped_hat_id", account.get("equipped_hat_id", "none")), list(account.get("owned_hat_ids", ["none"])))
		save_account(account)
		self._send_json({
			"account": public_account_view(account),
			"accounts": list_accounts_for(account) if account["role"] in {"director", "moderator"} else [],
			"audit_log": audit_entries_for(account),
		})

	def _handle_request_password_reset(self, payload: dict) -> None:
		username = str(payload.get("username", "")).strip()
		if username == "":
			self._send_json({"error": "Username is required."}, HTTPStatus.BAD_REQUEST)
			return
		account = find_account_by_username(username)
		response = {
			"message": "If that account exists, a password reset link has been prepared."
		}
		if account is None or account["banned"]:
			self._send_json(response)
			return
		token = issue_password_reset_token(account, self.client_address[0])
		if should_return_reset_preview(self):
			response["reset_url"] = build_reset_url(self, token)
			response["expires_in_seconds"] = PASSWORD_RESET_TTL_SECONDS
		self._send_json(response)

	def _handle_change_password(self, payload: dict) -> None:
		account = get_session_account(self, payload)
		if account is None:
			account = authenticate(str(payload.get("username", "")).strip(), str(payload.get("password", "")))
		if account is None:
			self._send_json({"error": "Authentication required."}, HTTPStatus.FORBIDDEN)
			return
		if account["banned"]:
			self._send_json({"error": "This account has been banned."}, HTTPStatus.FORBIDDEN)
			return
		current_password = str(payload.get("current_password", ""))
		new_password = str(payload.get("new_password", ""))
		confirm_new_password = str(payload.get("confirm_new_password", ""))
		if not verify_account_password(account, current_password):
			self._send_json({"error": "Current password is incorrect."}, HTTPStatus.FORBIDDEN)
			return
		if not validate_password(new_password):
			self._send_json({"error": "New password must be at least 8 characters long."}, HTTPStatus.BAD_REQUEST)
			return
		if new_password != confirm_new_password:
			self._send_json({"error": "New password confirmation does not match."}, HTTPStatus.BAD_REQUEST)
			return
		account["password_hash"] = hash_password(new_password)
		save_account(account)
		revoke_sessions_for_account(account["account_id"])
		session = issue_session(account, self.client_address[0])
		self._send_json({
			"message": "Password updated.",
			"account": public_account_view(account),
			"accounts": list_accounts_for(account) if account["role"] in {"director", "moderator"} else [],
			"audit_log": audit_entries_for(account),
			"session": session,
		})

	def _handle_reset_password(self, payload: dict) -> None:
		token = str(payload.get("token", "")).strip()
		new_password = str(payload.get("new_password", ""))
		confirm_new_password = str(payload.get("confirm_new_password", ""))
		if token == "":
			self._send_json({"error": "Reset token is required."}, HTTPStatus.BAD_REQUEST)
			return
		if not validate_password(new_password):
			self._send_json({"error": "New password must be at least 8 characters long."}, HTTPStatus.BAD_REQUEST)
			return
		if new_password != confirm_new_password:
			self._send_json({"error": "New password confirmation does not match."}, HTTPStatus.BAD_REQUEST)
			return
		account = consume_password_reset_token(token)
		if account is None:
			self._send_json({"error": "This password reset link is invalid or has expired."}, HTTPStatus.FORBIDDEN)
			return
		account["password_hash"] = hash_password(new_password)
		save_account(account)
		revoke_sessions_for_account(account["account_id"])
		self._send_json({"message": "Password reset complete. You can sign in with the new password now."})

	def _handle_moderation(self, payload: dict) -> None:
		viewer = get_session_account(self, payload)
		if viewer is None:
			viewer = authenticate(str(payload.get("username", "")).strip(), str(payload.get("password", "")))
		if viewer is None:
			self._send_json({"error": "Authentication required."}, HTTPStatus.FORBIDDEN)
			return
		if viewer["role"] not in {"director", "moderator"}:
			self._send_json({"error": "Moderator access required."}, HTTPStatus.FORBIDDEN)
			return
		verification_username = str(payload.get("verification_username", "")).strip()
		verification_password = str(payload.get("verification_password", ""))
		if verification_username == "" or verification_password == "":
			self._send_json({"error": "You must verify your identity with your moderator or Director username and password before using moderation controls."}, HTTPStatus.FORBIDDEN)
			return
		if verification_username.lower() != str(viewer.get("username", "")).lower():
			self._send_json({"error": "Identity verification failed. The moderation username must match the signed-in moderator or Director account."}, HTTPStatus.FORBIDDEN)
			return
		if not verify_account_password(viewer, verification_password):
			self._send_json({"error": "Identity verification failed. Only moderators or the Director with the correct password can use ban or unban."}, HTTPStatus.FORBIDDEN)
			return
		reason = str(payload.get("reason", "")).strip()
		if reason == "":
			self._send_json({"error": "A moderation reason is required for every moderation action."}, HTTPStatus.BAD_REQUEST)
			return
		if len(reason) > MAX_MODERATION_REASON_LENGTH:
			self._send_json({"error": "Moderation reasons must stay under %d characters." % MAX_MODERATION_REASON_LENGTH}, HTTPStatus.BAD_REQUEST)
			return
		accounts = load_accounts()
		target = accounts.get(str(payload.get("target_account_id", "")).strip())
		if target is None:
			self._send_json({"error": "Target account not found."}, HTTPStatus.NOT_FOUND)
			return
		if target["account_id"] == viewer["account_id"]:
			self._send_json({"error": "You cannot moderate your own account."}, HTTPStatus.FORBIDDEN)
			return
		action = str(payload.get("action", "")).strip()
		if action == "promote_moderator":
			if viewer["role"] != "director":
				self._send_json({"error": "Only the Director can assign moderators."}, HTTPStatus.FORBIDDEN)
				return
			if target["role"] == "director":
				self._send_json({"error": "The Director cannot be changed."}, HTTPStatus.FORBIDDEN)
				return
			target["role"] = "moderator"
			message = f"{target['display_name']} is now a moderator."
		elif action == "demote_moderator":
			if viewer["role"] != "director":
				self._send_json({"error": "Only the Director can remove moderators."}, HTTPStatus.FORBIDDEN)
				return
			if target["role"] != "moderator":
				self._send_json({"error": "Target account is not a moderator."}, HTTPStatus.FORBIDDEN)
				return
			target["role"] = "player"
			message = f"{target['display_name']} is now a standard player."
		elif action == "ban":
			if target["role"] in {"moderator", "director"}:
				self._send_json({"error": "Moderators cannot ban moderators or the Director."}, HTTPStatus.FORBIDDEN)
				return
			target["banned"] = True
			revoke_sessions_for_account(target["account_id"])
			message = f"{target['display_name']} has been banned."
		elif action == "unban":
			if target["role"] in {"moderator", "director"}:
				self._send_json({"error": "Moderators cannot unban moderators or the Director."}, HTTPStatus.FORBIDDEN)
				return
			target["banned"] = False
			message = f"{target['display_name']} has been unbanned."
		else:
			self._send_json({"error": "Unknown moderation action."}, HTTPStatus.BAD_REQUEST)
			return
		save_account(target)
		record_moderation_audit(viewer, target, action, reason, self.client_address[0])
		self._send_json({"message": message, "accounts": list_accounts_for(viewer), "audit_log": audit_entries_for(viewer)})

	def _handle_publish_level(self, payload: dict) -> None:
		account = get_session_account(self, payload)
		if account is None:
			self._send_json({"error": "Sign in from the website before releasing a chamber."}, HTTPStatus.FORBIDDEN)
			return
		if account["banned"]:
			self._send_json({"error": "This account has been banned."}, HTTPStatus.FORBIDDEN)
			return
		level_id = str(payload.get("level_id", payload.get("id", ""))).strip()
		name = str(payload.get("name", "")).strip()
		if level_id == "" or name == "":
			self._send_json({"error": "Level id and name are required for release."}, HTTPStatus.BAD_REQUEST)
			return
		if not validate_level_id(level_id):
			self._send_json({"error": "Level id must be 3-96 characters and use only letters, numbers, dashes, or underscores."}, HTTPStatus.BAD_REQUEST)
			return
		level = normalize_published_level(payload, account)
		try:
			saved = save_published_level(level)
		except PermissionError as error:
			self._send_json({"error": str(error)}, HTTPStatus.FORBIDDEN)
			return
		self._send_json({
			"message": "Released %s to the Bureau catalog." % saved["name"],
			"level": saved,
			"levels": list_published_levels(),
		})

	def _handle_logout(self, payload: dict) -> None:
		session_token = self.headers.get("X-Session-Token", "").strip()
		if session_token == "":
			session_token = str(payload.get("session_token", "")).strip()
		if session_token != "":
			revoke_session_token(session_token)
		self._send_json({"ok": True})

	def _read_json_body(self) -> dict | None:
		length = int(self.headers.get("Content-Length", "0"))
		if length > MAX_JSON_BODY_BYTES:
			self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body too large")
			return None
		raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
		try:
			return json.loads(raw_body)
		except json.JSONDecodeError:
			self.send_error(HTTPStatus.BAD_REQUEST, "Body must be valid JSON")
			return None

	def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
		body = json.dumps(payload, indent=2).encode("utf-8")
		self._send_bytes(body, "application/json; charset=utf-8", status)

	def _handle_internal_error(self, error: Exception) -> None:
		traceback.print_exc()
		try:
			self._send_json({"error": "Internal server error."}, HTTPStatus.INTERNAL_SERVER_ERROR)
		except BrokenPipeError:
			pass

	def _send_portal_page(self, include_body: bool = True) -> None:
		page_path = ROOT / "index.html"
		if not page_path.exists():
			body = PORTAL_FALLBACK_HTML.encode("utf-8")
			self._send_bytes(body, "text/html; charset=utf-8", HTTPStatus.SERVICE_UNAVAILABLE, include_body)
			return
		try:
			body = page_path.read_bytes()
		except OSError:
			body = PORTAL_FALLBACK_HTML.encode("utf-8")
		self._send_bytes(body, "text/html; charset=utf-8", HTTPStatus.OK, include_body)

	def _send_static(self, relative_path: str, include_body: bool = True) -> None:
		if not relative_path:
			self.send_error(HTTPStatus.NOT_FOUND, "Missing file")
			return
		file_path = (ROOT / relative_path).resolve()
		if ROOT not in file_path.parents and file_path != ROOT:
			self.send_error(HTTPStatus.FORBIDDEN, "Blocked path")
			return
		if not file_path.exists() or not file_path.is_file():
			self.send_error(HTTPStatus.NOT_FOUND, "File not found")
			return
		content_type, _ = mimetypes.guess_type(str(file_path))
		data = file_path.read_bytes()
		self._send_bytes(data, content_type or "application/octet-stream", HTTPStatus.OK, include_body)

	def log_message(self, fmt: str, *args) -> None:
		print("[portal]", fmt % args)


class PortalHTTPServer(ThreadingHTTPServer):
	allow_reuse_address = True
	daemon_threads = True


def validate_runtime_configuration() -> None:
	if not validate_username(DIRECTOR_USERNAME):
		raise RuntimeError("BUREAU_DIRECTOR_USERNAME must be 3-24 characters using only letters, numbers, dashes, or underscores.")
	if SESSION_TTL_SECONDS < 300:
		raise RuntimeError("BUREAU_SESSION_TTL_SECONDS must be at least 300 seconds.")
	if MAX_JSON_BODY_BYTES < 1024:
		raise RuntimeError("BUREAU_MAX_JSON_BODY_BYTES is set too low.")
	if IS_PRODUCTION:
		if CONFIGURED_DATA_DIR == "":
			raise RuntimeError("Set BUREAU_DATA_DIR to a persistent storage path before running the portal in production.")
		if DIRECTOR_PASSWORD in {"", DEFAULT_DIRECTOR_PASSWORD}:
			raise RuntimeError("Set a non-default BUREAU_DIRECTOR_PASSWORD before running the portal in production.")
		if ENABLE_DEV_DEFAULTS:
			raise RuntimeError("Disable BUREAU_ENABLE_DEV_DEFAULTS before running the portal in production.")
		if PUBLIC_BASE_URL == "":
			raise RuntimeError("Set BUREAU_PUBLIC_BASE_URL before running the portal in production.")
		if not PUBLIC_BASE_URL.startswith("https://"):
			raise RuntimeError("BUREAU_PUBLIC_BASE_URL must use https:// in production.")
		if HOST in {"127.0.0.1", "localhost"}:
			raise RuntimeError("BUREAU_PORTAL_HOST must not bind to localhost in production.")


def main() -> None:
	validate_runtime_configuration()
	ensure_storage()
	server = PortalHTTPServer((HOST, PORT), PortalHandler)
	scheme = "https" if REQUIRE_HTTPS and PUBLIC_BASE_URL.startswith("https://") else "http"
	print(f"Bureau account portal running at {PUBLIC_BASE_URL or f'{scheme}://{HOST}:{PORT}'}")
	print(f"Director username: {DIRECTOR_USERNAME}")
	print(f"Environment: {ENVIRONMENT}")
	print(f"Registration enabled: {'yes' if ALLOW_REGISTRATION else 'no'}")
	if ENABLE_DEV_DEFAULTS:
		print("Warning: development default accounts are enabled.")
	if DIRECTOR_PASSWORD == DEFAULT_DIRECTOR_PASSWORD:
		print("Warning: default Director password is active. Override BUREAU_DIRECTOR_PASSWORD before public deployment.")
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		print("\nStopping portal server.")
	finally:
		server.server_close()


if __name__ == "__main__":
	main()
