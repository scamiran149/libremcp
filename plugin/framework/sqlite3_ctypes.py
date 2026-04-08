# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""sqlite3_ctypes — Pure-Python DB-API 2.0 wrapper around sqlite3 via ctypes.

Drop-in replacement for the standard ``sqlite3`` module when the C extension
``_sqlite3.pyd`` cannot be loaded (e.g. inside LibreOffice's custom Python
on Windows).  Loads ``sqlite3.dll`` (or ``libsqlite3.so``) directly through
:mod:`ctypes`, with zero compiled dependencies.

Implements the subset of DB-API 2.0 actually used by Nelson MCP:
``connect``, ``Connection.execute/executemany/executescript/commit/close``,
``Cursor.fetchone/fetchall/__iter__``, and ``Row`` (dict-like access).

Usage::

    from plugin.framework.sqlite3_ctypes import connect, Row

    conn = connect("my.db")
    conn.row_factory = Row
    for row in conn.execute("SELECT * FROM t WHERE x = ?", (42,)):
        print(dict(row))
    conn.close()
"""

import ctypes
import ctypes.util
import os
import sys

# ---------------------------------------------------------------------------
# DB-API 2.0 module globals
# ---------------------------------------------------------------------------

apilevel = "2.0"
threadsafety = 1
paramstyle = "qmark"

# ---------------------------------------------------------------------------
# SQLite constants
# ---------------------------------------------------------------------------

SQLITE_OK = 0
SQLITE_ERROR = 1
SQLITE_BUSY = 5
SQLITE_ROW = 100
SQLITE_DONE = 101

SQLITE_INTEGER = 1
SQLITE_FLOAT = 2
SQLITE_TEXT = 3
SQLITE_BLOB = 4
SQLITE_NULL = 5

SQLITE_OPEN_READWRITE = 0x00000002
SQLITE_OPEN_CREATE = 0x00000004
SQLITE_OPEN_FULLMUTEX = 0x00010000

SQLITE_TRANSIENT = ctypes.cast(ctypes.c_void_p(-1), ctypes.c_void_p)

# ---------------------------------------------------------------------------
# Exceptions (DB-API 2.0 hierarchy)
# ---------------------------------------------------------------------------


class Error(Exception):
    """Base class for all sqlite3_ctypes errors."""


class DatabaseError(Error):
    pass


class OperationalError(DatabaseError):
    pass


class IntegrityError(DatabaseError):
    pass


class ProgrammingError(DatabaseError):
    pass


class InterfaceError(Error):
    pass


# ---------------------------------------------------------------------------
# DLL loading
# ---------------------------------------------------------------------------

_lib = None


def _get_lib():
    """Find and load the sqlite3 shared library.  Result is cached."""
    global _lib
    if _lib is not None:
        return _lib

    dll_path = None

    # 0. NELSON_SQLITE3_DLL env var overrides all search
    env_dll = os.environ.get("NELSON_SQLITE3_DLL")
    if env_dll and os.path.isfile(env_dll):
        dll_path = env_dll

    if sys.platform == "win32" and not dll_path:
        candidates = []

        # 1. Bundled sqlite3.dll in the extension (plugin/lib/sqlite3/)
        _this_dir = os.path.dirname(os.path.abspath(__file__))
        _plugin_dir = os.path.dirname(_this_dir)
        bundled = os.path.join(_plugin_dir, "lib", "sqlite3", "sqlite3.dll")
        if os.path.isfile(bundled):
            candidates.append(bundled)

        # 2. LO's program/ and python-core/ directories
        for base in [os.path.dirname(sys.executable),
                     r"C:\Program Files\LibreOffice\program",
                     r"C:\Program Files (x86)\LibreOffice\program"]:
            c = os.path.join(base, "sqlite3.dll")
            if os.path.isfile(c):
                candidates.append(c)
            try:
                for entry in os.listdir(base):
                    if entry.startswith("python-core"):
                        c = os.path.join(base, entry, "lib", "sqlite3.dll")
                        if os.path.isfile(c):
                            candidates.append(c)
            except Exception:
                pass

        # Try each candidate — some DLLs may crash on open
        for candidate in candidates:
            try:
                test_lib = ctypes.CDLL(candidate)
                test_lib.sqlite3_open_v2.argtypes = [
                    ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p),
                    ctypes.c_int, ctypes.c_char_p]
                test_lib.sqlite3_open_v2.restype = ctypes.c_int
                test_lib.sqlite3_close.argtypes = [ctypes.c_void_p]
                test_lib.sqlite3_close.restype = ctypes.c_int
                db = ctypes.c_void_p()
                rc = test_lib.sqlite3_open_v2(
                    b":memory:", ctypes.byref(db), 6, None)
                if rc == 0:
                    test_lib.sqlite3_close(db)
                    dll_path = candidate
                    break
            except Exception:
                continue

        # 3. System search
        if not dll_path:
            dll_path = ctypes.util.find_library("sqlite3")
    elif not dll_path:
        dll_path = ctypes.util.find_library("sqlite3")

    if not dll_path:
        raise ImportError("sqlite3 shared library not found")

    _lib = ctypes.CDLL(dll_path)
    _setup_signatures(_lib)
    return _lib


def _setup_signatures(lib):
    """Declare argtypes/restype for the C functions we call."""

    # --- open / close ---
    lib.sqlite3_open_v2.argtypes = [
        ctypes.c_char_p,                    # filename
        ctypes.POINTER(ctypes.c_void_p),    # ppDb
        ctypes.c_int,                       # flags
        ctypes.c_char_p,                    # zVfs
    ]
    lib.sqlite3_open_v2.restype = ctypes.c_int

    lib.sqlite3_close.argtypes = [ctypes.c_void_p]
    lib.sqlite3_close.restype = ctypes.c_int

    # --- prepare / step / finalize / reset ---
    lib.sqlite3_prepare_v2.argtypes = [
        ctypes.c_void_p,                    # db
        ctypes.c_char_p,                    # zSql
        ctypes.c_int,                       # nByte
        ctypes.POINTER(ctypes.c_void_p),    # ppStmt
        ctypes.POINTER(ctypes.c_char_p),    # pzTail
    ]
    lib.sqlite3_prepare_v2.restype = ctypes.c_int

    lib.sqlite3_step.argtypes = [ctypes.c_void_p]
    lib.sqlite3_step.restype = ctypes.c_int

    lib.sqlite3_finalize.argtypes = [ctypes.c_void_p]
    lib.sqlite3_finalize.restype = ctypes.c_int

    lib.sqlite3_reset.argtypes = [ctypes.c_void_p]
    lib.sqlite3_reset.restype = ctypes.c_int

    # --- bind ---
    lib.sqlite3_bind_int64.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int64]
    lib.sqlite3_bind_int64.restype = ctypes.c_int

    lib.sqlite3_bind_double.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_double]
    lib.sqlite3_bind_double.restype = ctypes.c_int

    lib.sqlite3_bind_text.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p,
        ctypes.c_int, ctypes.c_void_p]
    lib.sqlite3_bind_text.restype = ctypes.c_int

    lib.sqlite3_bind_blob.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_void_p]
    lib.sqlite3_bind_blob.restype = ctypes.c_int

    lib.sqlite3_bind_null.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.sqlite3_bind_null.restype = ctypes.c_int

    # --- column ---
    lib.sqlite3_column_count.argtypes = [ctypes.c_void_p]
    lib.sqlite3_column_count.restype = ctypes.c_int

    lib.sqlite3_column_type.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.sqlite3_column_type.restype = ctypes.c_int

    lib.sqlite3_column_name.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.sqlite3_column_name.restype = ctypes.c_char_p

    lib.sqlite3_column_int64.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.sqlite3_column_int64.restype = ctypes.c_int64

    lib.sqlite3_column_double.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.sqlite3_column_double.restype = ctypes.c_double

    lib.sqlite3_column_text.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.sqlite3_column_text.restype = ctypes.c_char_p

    lib.sqlite3_column_blob.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.sqlite3_column_blob.restype = ctypes.c_void_p

    lib.sqlite3_column_bytes.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.sqlite3_column_bytes.restype = ctypes.c_int

    # --- error ---
    lib.sqlite3_errmsg.argtypes = [ctypes.c_void_p]
    lib.sqlite3_errmsg.restype = ctypes.c_char_p

    # --- misc ---
    lib.sqlite3_changes.argtypes = [ctypes.c_void_p]
    lib.sqlite3_changes.restype = ctypes.c_int

    lib.sqlite3_last_insert_rowid.argtypes = [ctypes.c_void_p]
    lib.sqlite3_last_insert_rowid.restype = ctypes.c_int64

    # --- exec (multi-statement) ---
    lib.sqlite3_exec.argtypes = [
        ctypes.c_void_p,    # db
        ctypes.c_char_p,    # sql
        ctypes.c_void_p,    # callback (NULL)
        ctypes.c_void_p,    # callback arg (NULL)
        ctypes.POINTER(ctypes.c_char_p),  # errmsg
    ]
    lib.sqlite3_exec.restype = ctypes.c_int

    # --- version ---
    lib.sqlite3_libversion.argtypes = []
    lib.sqlite3_libversion.restype = ctypes.c_char_p


# ---------------------------------------------------------------------------
# Module-level version string (lazy)
# ---------------------------------------------------------------------------

_sqlite_version = None


@property
def _version_prop(self):
    return sqlite_version


def _get_sqlite_version():
    global _sqlite_version
    if _sqlite_version is None:
        lib = _get_lib()
        _sqlite_version = lib.sqlite3_libversion().decode("utf-8")
    return _sqlite_version


class _VersionDescriptor:
    """Allow ``sqlite3_ctypes.sqlite_version`` as a module-level attribute."""
    def __get__(self, obj, objtype=None):
        return _get_sqlite_version()


# Eagerly try to get version; fall back to lazy
try:
    sqlite_version = _get_lib().sqlite3_libversion().decode("utf-8")
except Exception:
    sqlite_version = ""


# ---------------------------------------------------------------------------
# Row
# ---------------------------------------------------------------------------


class Row:
    """Row factory compatible with ``sqlite3.Row``.

    Supports ``row["col"]``, ``row[0]``, ``dict(row)``, ``row.keys()``.
    """

    __slots__ = ("_values", "_names", "_name_map")

    def __init__(self, cursor, values):
        self._values = tuple(values)
        self._names = cursor._column_names
        self._name_map = cursor._column_name_map

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                return self._values[self._name_map[key.lower()]]
            except KeyError:
                raise IndexError("No column named '%s'" % key)
        return self._values[key]

    def __len__(self):
        return len(self._values)

    def __iter__(self):
        return iter(self._values)

    def __repr__(self):
        items = ", ".join("%s=%r" % (n, v)
                          for n, v in zip(self._names, self._values))
        return "<Row(%s)>" % items

    def keys(self):
        """Column names — enables ``dict(row)``."""
        return list(self._names)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check(lib, db, rc, msg=""):
    """Raise on non-OK return code."""
    if rc not in (SQLITE_OK, SQLITE_ROW, SQLITE_DONE):
        if db:
            detail = lib.sqlite3_errmsg(db)
            if detail:
                detail = detail.decode("utf-8", errors="replace")
            else:
                detail = "error code %d" % rc
        else:
            detail = "error code %d" % rc
        if rc == SQLITE_BUSY:
            raise OperationalError("database is locked: %s" % detail)
        if msg:
            raise OperationalError("%s: %s" % (msg, detail))
        raise OperationalError(detail)


def _bind_params(lib, stmt, db, params):
    """Bind a tuple of Python values to ``?`` placeholders."""
    for i, val in enumerate(params, 1):
        if val is None:
            rc = lib.sqlite3_bind_null(stmt, i)
        elif isinstance(val, int):
            rc = lib.sqlite3_bind_int64(stmt, i, val)
        elif isinstance(val, float):
            rc = lib.sqlite3_bind_double(stmt, i, val)
        elif isinstance(val, str):
            encoded = val.encode("utf-8")
            rc = lib.sqlite3_bind_text(
                stmt, i, encoded, len(encoded), SQLITE_TRANSIENT)
        elif isinstance(val, (bytes, bytearray, memoryview)):
            buf = bytes(val)
            rc = lib.sqlite3_bind_blob(
                stmt, i, buf, len(buf), SQLITE_TRANSIENT)
        elif isinstance(val, bool):
            rc = lib.sqlite3_bind_int64(stmt, i, int(val))
        else:
            raise InterfaceError(
                "Cannot bind parameter %d: unsupported type %s"
                % (i, type(val).__name__))
        _check(lib, db, rc, "bind param %d" % i)


def _extract_row(lib, stmt, col_count):
    """Extract one row of values from a stepped statement."""
    values = []
    for i in range(col_count):
        col_type = lib.sqlite3_column_type(stmt, i)
        if col_type == SQLITE_NULL:
            values.append(None)
        elif col_type == SQLITE_INTEGER:
            values.append(lib.sqlite3_column_int64(stmt, i))
        elif col_type == SQLITE_FLOAT:
            values.append(lib.sqlite3_column_double(stmt, i))
        elif col_type == SQLITE_TEXT:
            raw = lib.sqlite3_column_text(stmt, i)
            values.append(raw.decode("utf-8") if raw else "")
        elif col_type == SQLITE_BLOB:
            n = lib.sqlite3_column_bytes(stmt, i)
            ptr = lib.sqlite3_column_blob(stmt, i)
            values.append(ctypes.string_at(ptr, n) if ptr else b"")
        else:
            values.append(None)
    return tuple(values)


# ---------------------------------------------------------------------------
# Cursor
# ---------------------------------------------------------------------------


class Cursor:
    """DB-API 2.0 Cursor (minimal subset)."""

    def __init__(self, connection):
        self._conn = connection
        self._stmt = None
        self._column_names = ()
        self._column_name_map = {}
        self._col_count = 0
        self._exhausted = True
        self.description = None
        self.lastrowid = None
        self.rowcount = -1

    # -- internal --

    def _execute(self, sql, parameters=()):
        lib = _get_lib()
        db = self._conn._db
        if db is None:
            raise ProgrammingError("Cannot operate on a closed database.")

        # Finalize previous statement
        self._finalize()

        stmt = ctypes.c_void_p()
        tail = ctypes.c_char_p()
        encoded_sql = sql.encode("utf-8") if isinstance(sql, str) else sql
        rc = lib.sqlite3_prepare_v2(
            db, encoded_sql, len(encoded_sql),
            ctypes.byref(stmt), ctypes.byref(tail))
        _check(lib, db, rc, sql[:60] if isinstance(sql, str) else "")

        if not stmt:
            # Empty statement
            self._exhausted = True
            return

        _bind_params(lib, stmt, db, parameters)

        rc = lib.sqlite3_step(stmt)
        if rc == SQLITE_ROW:
            self._stmt = stmt
            self._col_count = lib.sqlite3_column_count(stmt)
            names = []
            name_map = {}
            for i in range(self._col_count):
                raw = lib.sqlite3_column_name(stmt, i)
                name = raw.decode("utf-8") if raw else "col%d" % i
                names.append(name)
                name_map[name.lower()] = i
            self._column_names = tuple(names)
            self._column_name_map = name_map
            self.description = tuple(
                (n, None, None, None, None, None, None) for n in names)
            self._exhausted = False
        elif rc == SQLITE_DONE:
            self.lastrowid = lib.sqlite3_last_insert_rowid(db)
            self.rowcount = lib.sqlite3_changes(db)
            lib.sqlite3_finalize(stmt)
            self._stmt = None
            self._exhausted = True
        else:
            lib.sqlite3_finalize(stmt)
            self._stmt = None
            self._exhausted = True
            _check(lib, db, rc, sql[:60] if isinstance(sql, str) else "")

    def _finalize(self):
        if self._stmt is not None:
            _get_lib().sqlite3_finalize(self._stmt)
            self._stmt = None
            self._exhausted = True

    def _make_row(self, values):
        factory = self._conn.row_factory
        if factory is not None:
            return factory(self, values)
        return values

    # -- public API --

    def fetchone(self):
        if self._exhausted:
            return None
        lib = _get_lib()
        values = _extract_row(lib, self._stmt, self._col_count)
        row = self._make_row(values)
        # Advance to next row
        rc = lib.sqlite3_step(self._stmt)
        if rc == SQLITE_DONE:
            self._finalize()
        elif rc != SQLITE_ROW:
            self._finalize()
            _check(lib, self._conn._db, rc)
        return row

    def fetchall(self):
        rows = []
        while not self._exhausted:
            row = self.fetchone()
            if row is not None:
                rows.append(row)
        return rows

    def __iter__(self):
        return self

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row

    def close(self):
        self._finalize()

    def __del__(self):
        self._finalize()


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


class Connection:
    """DB-API 2.0 Connection (minimal subset)."""

    def __init__(self, database, flags=None):
        lib = _get_lib()
        self._db = ctypes.c_void_p()
        if flags is None:
            flags = (SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE
                     | SQLITE_OPEN_FULLMUTEX)
        encoded = database.encode("utf-8") if isinstance(database, str) else database
        rc = lib.sqlite3_open_v2(
            encoded, ctypes.byref(self._db), flags, None)
        if rc != SQLITE_OK:
            msg = ""
            if self._db:
                raw = lib.sqlite3_errmsg(self._db)
                if raw:
                    msg = raw.decode("utf-8", errors="replace")
                lib.sqlite3_close(self._db)
            self._db = None
            raise OperationalError(
                "Cannot open database '%s': %s" % (database, msg))
        self.row_factory = None

    def execute(self, sql, parameters=()):
        cur = Cursor(self)
        cur._execute(sql, parameters)
        return cur

    def executemany(self, sql, seq_of_parameters):
        cur = Cursor(self)
        lib = _get_lib()
        db = self._db
        if db is None:
            raise ProgrammingError("Cannot operate on a closed database.")

        encoded_sql = sql.encode("utf-8") if isinstance(sql, str) else sql

        for params in seq_of_parameters:
            stmt = ctypes.c_void_p()
            tail = ctypes.c_char_p()
            rc = lib.sqlite3_prepare_v2(
                db, encoded_sql, len(encoded_sql),
                ctypes.byref(stmt), ctypes.byref(tail))
            _check(lib, db, rc, "executemany prepare")

            if not stmt:
                continue

            _bind_params(lib, stmt, db, params)
            rc = lib.sqlite3_step(stmt)
            lib.sqlite3_finalize(stmt)
            if rc not in (SQLITE_ROW, SQLITE_DONE):
                _check(lib, db, rc, "executemany step")

        cur.rowcount = lib.sqlite3_changes(db)
        cur.lastrowid = lib.sqlite3_last_insert_rowid(db)
        return cur

    def executescript(self, sql_script):
        lib = _get_lib()
        db = self._db
        if db is None:
            raise ProgrammingError("Cannot operate on a closed database.")

        encoded = sql_script.encode("utf-8") if isinstance(
            sql_script, str) else sql_script
        errmsg = ctypes.c_char_p()
        rc = lib.sqlite3_exec(db, encoded, None, None,
                              ctypes.byref(errmsg))
        if rc != SQLITE_OK:
            msg = errmsg.value.decode("utf-8", errors="replace") \
                if errmsg.value else "error code %d" % rc
            raise OperationalError("executescript: %s" % msg)

    def commit(self):
        if self._db is None:
            return
        lib = _get_lib()
        errmsg = ctypes.c_char_p()
        rc = lib.sqlite3_exec(self._db, b"COMMIT", None, None,
                              ctypes.byref(errmsg))
        # SQLITE_ERROR "cannot commit - no transaction is active" is OK
        if rc != SQLITE_OK and rc != SQLITE_ERROR:
            _check(lib, self._db, rc, "commit")

    def close(self):
        if self._db is not None:
            _get_lib().sqlite3_close(self._db)
            self._db = None

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        self.close()
        return False


# ---------------------------------------------------------------------------
# Module-level connect()
# ---------------------------------------------------------------------------


def connect(database, *, check_same_thread=False, **kwargs):
    """Open a database connection.  DB-API 2.0 entry point.

    ``check_same_thread`` is accepted for compatibility but ignored
    (we always open with SQLITE_OPEN_FULLMUTEX for thread safety).
    """
    return Connection(database)
