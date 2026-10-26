"""Real native signals on synthetic bytes; source/CI evidence explicitly mocked."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


CHILD = r'''
import signal,sys
from pathlib import Path
from unittest.mock import patch
from tests.io.velocity_timing_fixture import prepare
from lane_residuals.workflows import velocity_timing_pilot as workflow
from lane_residuals.cli.velocity_timing_pilot import main
phase,root=sys.argv[1],Path(sys.argv[2])
request,pin,_=prepare(root)
original=workflow.decode_prepared
def stop(*args):
    if phase == 'decode': original(*args)
    (root/'ready').write_text('ready')
    while True: signal.pause()
with patch.object(workflow.gate,'validate',return_value={'commit':'synthetic','tree':'synthetic'}), \
     patch.object(workflow.gate,'runtime_sha256',return_value='r'*64), \
     patch.object(workflow.gate,'git',return_value='synthetic'), \
     patch.object(workflow,'resources',return_value={'synthetic':True}), \
     patch.object(workflow,'verify_raw' if phase=='hash' else 'decode_prepared',side_effect=stop):
    main(['run','--project',str(root),'--request',str(request),'--request-sha256',pin,
          '--expected-runtime-sha256','r'*64,'--gate',str(root/'gate'),'--gate-sha256','f'*64,
          '--output',str(root/'result')])
'''


class SignalReceiptTests(unittest.TestCase):
    def setUp(self):
        try:
            from lane_residuals.io.recording_decode_check import check_dependencies
            check_dependencies()
        except (ImportError, ValueError):
            self.skipTest("optional MCAP extras not installed")

    def check_signal(self, phase, termination):
        repo = Path(__file__).resolve().parents[2]
        environment = dict(os.environ, PYTHONPATH=str(repo/"src"), OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            child = subprocess.Popen([sys.executable, "-c", CHILD, phase, str(root)], cwd=repo,
                env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic()+15
                while not (root/"ready").exists() and child.poll() is None and time.monotonic() < deadline:
                    time.sleep(.01)
                if not (root/"ready").exists():
                    child.kill(); _, error = child.communicate()
                    self.fail("Synthetic child did not reach phase: "+error)
                child.send_signal(termination)
                child.communicate(timeout=10)
            finally:
                if child.poll() is None:
                    child.kill(); child.communicate()
            report = json.loads((root/"result/report.private.json").read_text())
            self.assertEqual(report["status"], "started" if termination == signal.SIGKILL else "incomplete")
            self.assertIsNone(report["message_payloads_decoded"])
            if phase == "hash":
                self.assertIsNone(report["current_full_raw_hash_verified"])
            else:
                self.assertIs(report["current_full_raw_hash_verified"], True)
            self.assertEqual(len(list((root/"outputs/private/velocity_timing_attempts").glob("*.started.json"))), 1)

    def test_sigint_hash(self): self.check_signal("hash", signal.SIGINT)
    def test_sigterm_hash(self): self.check_signal("hash", signal.SIGTERM)
    def test_sigkill_hash(self): self.check_signal("hash", signal.SIGKILL)
    def test_sigint_after_decode(self): self.check_signal("decode", signal.SIGINT)
    def test_sigterm_after_decode(self): self.check_signal("decode", signal.SIGTERM)
    def test_sigkill_after_decode(self): self.check_signal("decode", signal.SIGKILL)
