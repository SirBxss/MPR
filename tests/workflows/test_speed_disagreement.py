import builtins,json,os,socket,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from lane_residuals.workflows.speed_disagreement import run
from lane_residuals.cli.speed_disagreement import main
from tests.io.speed_disagreement_fixture import make_files,pack,sha

class DisagreementWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        raw=pack(make_files());self.pin=sha(raw);self.archive=self.root/'input.zip';self.archive.write_bytes(raw);self.out=self.root/'diagnostic'
    def test_native_cli_and_all_output_rows(self):
        self.assertEqual(main(['--result-zip',str(self.archive),'--result-sha256',self.pin,'--output',str(self.out)]),0)
        r=json.loads((self.out/'report.private.json').read_text())
        self.assertEqual(r['status'],'complete_cached_speed_disagreement');self.assertEqual(len(r['cases']),2)
        self.assertEqual(r['cases'][0]['analysis']['frame_rows'],6)
        self.assertTrue((self.out/'speed_disagreement.png').is_file());self.assertTrue((self.out/'speed_disagreement.pdf').is_file())
    def test_existing_output_cannot_be_reused(self):
        self.out.mkdir();(self.out/'preserved.txt').write_text('original')
        with self.assertRaises(FileExistsError):run(self.archive,self.pin,self.out)
        self.assertEqual((self.out/'preserved.txt').read_text(),'original')
    def test_bad_input_has_no_output(self):
        with self.assertRaises(ValueError):run(self.archive,'a'*64,self.out)
        self.assertFalse(self.out.exists())
    def test_symlink_output_refused(self):
        self.out.symlink_to(self.root/'missing')
        with self.assertRaises(FileExistsError):run(self.archive,self.pin,self.out)
    def test_snapshot_nesting_refused_before_read(self):
        (self.root/'registry.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'immutable_snapshot'):run(self.archive,self.pin,self.out)
        self.assertFalse(self.out.exists())
    def test_plot_failure_is_incomplete(self):
        with patch('lane_residuals.reporting.speed_disagreement.plot',side_effect=RuntimeError('synthetic')):
            with self.assertRaises(RuntimeError):run(self.archive,self.pin,self.out)
        r=json.loads((self.out/'report.private.json').read_text());self.assertEqual(r['status'],'incomplete_cached_speed_disagreement')
    def test_network_is_not_used(self):
        with patch.object(socket.socket,'connect',side_effect=AssertionError('network')):
            r=run(self.archive,self.pin,self.out)
        self.assertFalse(r['raw_recording_opened']);self.assertFalse(r['model_fitted'])
