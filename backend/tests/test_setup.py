"""First-run defaults must be safe across all three startup processes."""
import os
from pathlib import Path
import subprocess
import sys


def run(code, folder):
    return subprocess.run([sys.executable, '-c', code], env={**os.environ, 'BT_DATA_DIR': str(folder)}, text=True, capture_output=True, timeout=30)


def test_fresh_install_and_existing_install_defaults(tmp_path):
    code = """
from bt.db import init_db, get_settings, session
from bt.models import Profile, Setting
init_db()
assert get_settings()['setup']['completed'] is False
assert get_settings()['agent']['enabled'] is False
with session() as s:
    s.delete(s.get(Setting, 'setup'))
    agent = s.get(Setting, 'agent')
    agent.value = {'enabled': True}
    s.add(agent)
    s.commit()
# Simulate an old installation, which already has a profile but no setup record.
init_db()
assert get_settings()['setup']['completed'] is True
assert get_settings()['agent']['enabled'] is True
"""
    result = run(code, tmp_path)
    assert result.returncode == 0, result.stderr


def test_concurrent_first_start_creates_one_profile(tmp_path):
    # Generate the signing secret once; this test targets database initialization.
    (tmp_path / '.secret').write_text('setup-test-secret')
    env = {**os.environ, 'BT_DATA_DIR': str(tmp_path)}
    jobs = [subprocess.Popen([sys.executable, '-c', 'from bt.db import init_db; init_db()'], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(3)]
    for job in jobs:
        _, errors = job.communicate(timeout=30)
        assert job.returncode == 0, errors
    result = run("from bt.db import init_db, session, get_settings; from bt.models import Profile; from sqlmodel import select; init_db();\nwith session() as s: assert len(s.exec(select(Profile)).all()) == 1\nassert get_settings()['setup']['completed'] is False", tmp_path)
    assert result.returncode == 0, result.stderr
