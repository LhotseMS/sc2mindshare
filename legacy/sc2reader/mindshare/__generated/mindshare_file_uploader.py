#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MindShare Media Uploader (Python 2 & 3 compatible)

Uploads one or more files to the MindShare media API and prints a table mapping
local file name -> uploaded _id (and HTTP status). Optionally writes CSV/JSON.

Usage examples:
  # Upload specific files
  python mindshare_file_uploader.py img/a.png img/b.png

  # Upload all PNGs from a folder
  python mindshare_file_uploader.py --dir ./screenshots --glob "*.png"

  # Save results to CSV and JSON
  python mindshare_file_uploader.py --dir ./shots --csv results.csv --json results.json

  # Override metadata/type
  python mindshare_file_uploader.py --type node.images --width 2558 --height 1598 img/a.png

Environment:
  Optionally set MINDSHARE_MEDIA_URL to override the default upload URL.

Notes:
  * This file is intentionally compatible with Python 2.7+ and Python 3.x.
  * It avoids "print(..., file=...)" and other Python 3-only features.
  * For tests, run:  python mindshare_file_uploader.py --self-test
"""

from __future__ import print_function, unicode_literals

import argparse
import io
import json
import mimetypes
import os
import sys
import glob
import tempfile
import shutil

try:
    # requests is required at runtime (not for --self-test with a fake session)
    import requests  # noqa: F401
except Exception:
    # Don't hard fail here; tests may inject a fake session
    requests = None  # type: ignore

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
DEFAULT_SERVER_URL = os.environ.get(
    'MINDSHARE_MEDIA_URL', 'https://media.api.mindshare.k8s.touch4dev.net/media'
)

# -----------------------------------------------------------------------------
# Small compatibility helpers
# -----------------------------------------------------------------------------
PY2 = sys.version_info[0] == 2

def eprint(msg):
    try:
        sys.stderr.write((msg if isinstance(msg, type(u'')) else str(msg)) + u"\n")
    except Exception:
        # Last-ditch fallback
        sys.stderr.write(str(msg) + "\n")


def sprint(msg):
    # stdout print without relying on print(file=...)
    try:
        sys.stdout.write((msg if isinstance(msg, type(u'')) else str(msg)) + u"\n")
    except Exception:
        sys.stdout.write(str(msg) + "\n")


def to_text(x):
    if x is None:
        return u''
    try:
        if isinstance(x, type(u'')):
            return x
        return u"{0}".format(x)
    except Exception:
        return u''


# -----------------------------------------------------------------------------
# Data model (simple class, no dataclasses for Py2 compatibility)
# -----------------------------------------------------------------------------
class UploadResult(object):
    def __init__(self, file_path, _id, status, error=None):
        self.file = file_path
        self.id = _id
        self.status = status
        self.error = error

    def as_dict(self):
        return {
            'file': self.file,
            'id': self.id,
            'status': self.status,
            'error': self.error,
        }


# -----------------------------------------------------------------------------
# Core logic
# -----------------------------------------------------------------------------

def discover_files(directory, pattern):
    if not directory:
        return []
    paths = glob.glob(os.path.join(directory, pattern))
    files = [p for p in sorted(paths) if os.path.isfile(p)]
    return files


def build_files_payload(filepath, file_type, width, height):
    guessed_type, _ = mimetypes.guess_type(os.path.basename(filepath))
    content_type = guessed_type or 'application/octet-stream'

    file_tuple = (os.path.basename(filepath), open(filepath, 'rb'), content_type)

    payload = {
        'type': (None, file_type),
        'file': file_tuple,
    }
    if width is not None:
        payload['meta.width'] = (None, str(width))
    if height is not None:
        payload['meta.height'] = (None, str(height))
    return payload


def upload_one(session, server_url, filepath, file_type, width, height, timeout=60):
    try:
        files = build_files_payload(filepath, file_type, width, height)
        try:
            resp = session.post(server_url, files=files, timeout=timeout)
        finally:
            try:
                files['file'][1].close()
            except Exception:
                pass

        status = getattr(resp, 'status_code', 0)

        parsed = None
        try:
            parsed = resp.json()
        except Exception:
            try:
                parsed = json.loads(resp.text)
            except Exception:
                parsed = None

        file_id = None
        error_msg = None
        if 200 <= status < 300:
            if isinstance(parsed, dict):
                file_id = parsed.get('_id') or parsed.get('id')
            if not file_id:
                error_msg = 'Upload succeeded but no _id returned in response.'
        else:
            if isinstance(parsed, dict):
                error_msg = parsed.get('message') or parsed.get('error') or getattr(resp, 'text', u'')
            else:
                error_msg = getattr(resp, 'text', u'')

        return UploadResult(filepath, file_id, status, error_msg)

    except Exception as e:
        return UploadResult(filepath, None, 0, 'Request/Unexpected error: {0}'.format(e))


# -----------------------------------------------------------------------------
# Output helpers
# -----------------------------------------------------------------------------

def _calc_widths(headers, rows):
    cols = list(zip(*([headers] + rows))) if rows else [headers]
    return [max(len(to_text(c)) for c in col) for col in cols]


def print_table(results):
    headers = (u'File', u'ID', u'Status', u'Error')
    rows = []
    for r in results:
        rows.append((
            to_text(r.file),
            to_text(r.id) or u'-',
            to_text(r.status),
            (to_text(r.error) or u'-').replace(u"\n", u" ")[:200],
        ))
    widths = _calc_widths(headers, rows)

    def fmt_row(row):
        padded = []
        for cell, w in zip(row, widths):
            s = to_text(cell)
            if len(s) < w:
                s = s + u' ' * (w - len(s))
            padded.append(s)
        return u'  '.join(padded)

    sprint(fmt_row(headers))
    sprint(u'  '.join(u'-' * w for w in widths))
    for row in rows:
        sprint(fmt_row(row))


def _csv_escape(s):
    s = to_text(s)
    needs_quotes = (u',' in s) or (u'\n' in s) or (u'"' in s)
    s = s.replace(u'"', u'""')
    return u'"' + s + u'"' if needs_quotes else s


def write_csv(path, results):
    # Simple CSV writer that works on Py2/3 without newline issues
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(u'file,id,status,error\n')
        for r in results:
            line = u'{0},{1},{2},{3}\n'.format(
                _csv_escape(r.file),
                _csv_escape(r.id or u''),
                to_text(r.status),
                _csv_escape(r.error or u''),
            )
            f.write(line)


def write_json(path, results):
    with io.open(path, 'w', encoding='utf-8') as f:
        data = [r.as_dict() for r in results]
        # Ensure ascii=False for readability (works on Py2/3 with io.open)
        f.write(to_text(json.dumps(data, ensure_ascii=False, indent=2)))


# -----------------------------------------------------------------------------
# CLI parsing & orchestration
# -----------------------------------------------------------------------------

def collect_inputs(args):
    files = []

    for p in args.files:
        if os.path.isfile(p):
            files.append(p)
        else:
            eprint('Warning: not a file, skipping: {0}'.format(p))

    if args.dir:
        directory = args.dir
        if not os.path.exists(directory) or not os.path.isdir(directory):
            eprint('Warning: directory not found: {0}'.format(directory))
        else:
            pattern = args.glob or '*'
            files += discover_files(directory, pattern)

    # De-duplicate while preserving order
    seen = set()
    uniq = []
    for f in files:
        try:
            key = os.path.realpath(f)
        except Exception:
            key = f
        if key not in seen:
            uniq.append(f)
            seen.add(key)

    if not uniq:
        eprint('No input files found. Provide files or use --dir.')
        sys.exit(2)

    return uniq


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Upload files to MindShare media API.')
    p.add_argument('files', nargs='*', help='Specific file paths to upload (in addition to --dir discovery)')
    p.add_argument('--dir', help='Directory to scan for files (used with --glob)')
    p.add_argument('--glob', default='*.png', help='Glob pattern for --dir discovery (default: *.png)')
    p.add_argument('--server-url', default=DEFAULT_SERVER_URL, help='Upload endpoint (default: {0})'.format(DEFAULT_SERVER_URL))
    p.add_argument('--type', default='node.images', help="Value for multipart field 'type' (default: node.images)")
    p.add_argument('--width', help='Optional meta.width value; if omitted, meta.width is not sent')
    p.add_argument('--height', help='Optional meta.height value; if omitted, meta.height is not sent')
    p.add_argument('--timeout', type=int, default=60, help='HTTP timeout in seconds (default: 60)')
    p.add_argument('--csv', help='Optional path to write results as CSV')
    p.add_argument('--json', help='Optional path to write results as JSON')
    p.add_argument('--self-test', action='store_true', help='Run built-in tests and exit')
    return p.parse_args(argv)


def run_uploads(argv=None, session=None):
    args = parse_args(argv)

    if args.self_test:
        return self_test()

    if session is None:
        if requests is None:
            eprint('requests library not available')
            return 1
        session = __import__('requests').Session()

    files = collect_inputs(args)

    results = []
    for path in files:
        res = upload_one(
            session,
            args.server_url,
            path,
            args.type,
            args.width,
            args.height,
            timeout=args.timeout,
        )
        results.append(res)

    print_table(results)

    if args.csv:
        write_csv(args.csv, results)
        sprint('\nCSV written to: {0}'.format(args.csv))
    if args.json:
        write_json(args.json, results)
        sprint('JSON written to: {0}'.format(args.json))

    any_failed = any((r.status < 200 or r.status >= 300) for r in results)
    return 1 if any_failed else 0


# -----------------------------------------------------------------------------
# Minimal test suite (no external deps; uses a fake session)
# -----------------------------------------------------------------------------
class _FakeResponse(object):
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body)
    def json(self):
        return self._body


class _FakeSession(object):
    def __init__(self, behavior='ok'):
        self.behavior = behavior
    def post(self, url, files=None, timeout=60):
        # Simulate two behaviors based on filename to cover success and failure
        # If filename contains 'fail', return 500; otherwise 201 with an _id
        filename = files['file'][0] if files and 'file' in files else 'unknown'
        if 'fail' in filename or self.behavior == 'fail':
            return _FakeResponse(500, {'error': 'simulated failure'})
        fake_id = 'mock_' + filename.replace('.', '_')
        return _FakeResponse(201, {'_id': fake_id})


def _touch(path, content=u'x'):
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def self_test():
    sprint('Running self-test...')
    tempdir = tempfile.mkdtemp(prefix='ms_uploader_')
    try:
        ok_path = os.path.join(tempdir, 'ok.png')
        fail_path = os.path.join(tempdir, 'should_fail.png')
        _touch(ok_path)
        _touch(fail_path)

        # 1) discover_files
        files = discover_files(tempdir, '*.png')
        assert ok_path in files and fail_path in files, 'discover_files failed'

        # 2) upload_one success
        fs = _FakeSession('ok')
        res_ok = upload_one(fs, DEFAULT_SERVER_URL, ok_path, 'node.images', '10', '10', 3)
        assert res_ok.status == 201 and res_ok.id and res_ok.error is None, 'upload_one success path failed'

        # 3) upload_one failure
        res_fail = upload_one(fs, DEFAULT_SERVER_URL, fail_path, 'node.images', None, None, 3)
        assert res_fail.status == 500 and res_fail.id is None and res_fail.error, 'upload_one failure path failed'

        # 4) print_table smoke test
        print_table([res_ok, res_fail])

        # 5) write_csv/json
        csv_path = os.path.join(tempdir, 'out.csv')
        json_path = os.path.join(tempdir, 'out.json')
        write_csv(csv_path, [res_ok, res_fail])
        write_json(json_path, [res_ok, res_fail])
        assert os.path.isfile(csv_path) and os.path.getsize(csv_path) > 0, 'CSV not written'
        assert os.path.isfile(json_path) and os.path.getsize(json_path) > 0, 'JSON not written'

        sprint('Self-test passed.')
        return 0
    except AssertionError as ae:
        eprint('Self-test FAILED: {0}'.format(ae))
        return 1
    except Exception as e:
        eprint('Self-test ERROR: {0}'.format(e))
        return 1
    finally:
        try:
            shutil.rmtree(tempdir)
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    sys.exit(run_uploads())
