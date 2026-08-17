import sys, unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
CHECKER_DIR=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(CHECKER_DIR))
import testing_promotion_gate as gate

class Tests(unittest.TestCase):
    def ch(self,url="https://example.org/live.m3u8"):
        return {"id":"demo","name":"Demo","country":"CZ","category":"general","status":"testing",
                "stream":{"url":url,"format":"hls"}}
    def test_first_counts(self):
        n=datetime(2026,8,17,20,tzinfo=timezone.utc)
        e=gate.update_entry(None,self.ch(),ok=True,message="OK",observed_at=n,min_gap_hours=24)
        self.assertEqual(e["counted_passes"],1); self.assertTrue(e["pass_counted_this_run"])
    def test_inside_gap_not_counted(self):
        n=datetime(2026,8,17,20,tzinfo=timezone.utc)
        e=gate.update_entry(None,self.ch(),ok=True,message="OK",observed_at=n,min_gap_hours=24)
        e=gate.update_entry(e,self.ch(),ok=True,message="OK",observed_at=n+timedelta(hours=3),min_gap_hours=24)
        self.assertEqual(e["counted_passes"],1); self.assertFalse(e["pass_counted_this_run"])
    def test_after_gap_counts(self):
        n=datetime(2026,8,17,20,tzinfo=timezone.utc)
        e=gate.update_entry(None,self.ch(),ok=True,message="OK",observed_at=n,min_gap_hours=24)
        e=gate.update_entry(e,self.ch(),ok=True,message="OK",observed_at=n+timedelta(hours=25),min_gap_hours=24)
        self.assertEqual(e["counted_passes"],2)
    def test_failure_resets(self):
        n=datetime(2026,8,17,20,tzinfo=timezone.utc)
        prev={"stream_fingerprint":gate.stream_fingerprint(self.ch()),"counted_passes":2,
              "last_counted_pass_at":"2026-08-16T20:00:00Z"}
        e=gate.update_entry(prev,self.ch(),ok=False,message="timeout",observed_at=n,min_gap_hours=24)
        self.assertEqual(e["counted_passes"],0); self.assertIsNone(e["last_counted_pass_at"])
    def test_url_change_resets(self):
        n=datetime(2026,8,17,20,tzinfo=timezone.utc)
        old=self.ch("https://old/live.m3u8")
        prev={"stream_fingerprint":gate.stream_fingerprint(old),"counted_passes":2,
              "last_counted_pass_at":"2026-08-16T20:00:00Z"}
        e=gate.update_entry(prev,self.ch("https://new/live.m3u8"),ok=True,message="OK",observed_at=n,min_gap_hours=24)
        self.assertEqual(e["counted_passes"],1)
    def test_eligible(self):
        n=datetime(2026,8,17,20,tzinfo=timezone.utc)
        e={"counted_passes":3,"last_result":"pass","last_message":"OK","last_counted_pass_at":"2026-08-17T20:00:00Z"}
        self.assertTrue(gate.eligibility_row(self.ch(),e,required_passes=3,now=n)["eligible"])
    def test_failed_not_eligible(self):
        n=datetime(2026,8,17,20,tzinfo=timezone.utc)
        e={"counted_passes":3,"last_result":"fail","last_message":"timeout","last_counted_pass_at":"2026-08-17T20:00:00Z"}
        self.assertFalse(gate.eligibility_row(self.ch(),e,required_passes=3,now=n)["eligible"])
    def test_testing_only(self):
        db={"channels":[self.ch(),{**self.ch(),"id":"s","status":"stable"}]}
        self.assertEqual([x["id"] for x in gate.testing_channels(db)],["demo"])

if __name__=="__main__":
    unittest.main(verbosity=2)
