"""
End-to-end: two real `main.py` processes play a full game against tools/fake_server.py, which
speaks the server's binary protocol and enforces its rules (cheating = game over, 2 s limit).
"""
import os
import subprocess
import sys
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena.maps import load_xml
from tools.fake_server import FakeServer


def _launch(name, port, extra_env=None):
    env = dict(os.environ, SPLITTER_TIME="0.3", PYTHONIOENCODING="utf-8")
    env.update(extra_env or {})
    return subprocess.Popen([sys.executable, os.path.join(ROOT, "main.py"), "--name", name,
                             "127.0.0.1", str(port)], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


class TestProtocol(unittest.TestCase):
    def _play(self, map_name, max_ply, opponent_env=None):
        srv = FakeServer(load_xml(map_name, max_ply), port=0, move_timeout=2.0, seed=7, log=lambda _msg: None)
        th = threading.Thread(target=srv.run, daemon=True)
        th.start()
        a = _launch("Splitter", srv.port)
        time.sleep(0.5)                                   # first to connect = player 0 = vampires
        b = _launch("Starter", srv.port, opponent_env)
        th.join(timeout=max_ply * 2.5 + 30)
        outs = []
        for p in (a, b):
            try:
                out, _ = p.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()
                out, _ = p.communicate()
            outs.append(out.decode("utf-8", "replace"))
            self.assertEqual(p.returncode, 0, out[-2000:])
        return srv.result, outs

    def test_full_game_no_cheat_no_timeout(self):
        res, outs = self._play("testmap.xml", 40)
        self.assertIsNone(res.get("cheat"), res)
        self.assertEqual(res["timeouts"], [0, 0], res)
        self.assertIn(res["reason"], ("plies", "wipeout"))
        self.assertTrue(any("BYE" in o for o in outs), outs[0][-500:])

    def test_small_map_to_the_end(self):
        res, _ = self._play("thetrap.xml", 30)
        self.assertIsNone(res.get("cheat"), res)
        self.assertEqual(res["timeouts"][0], 0, res)


if __name__ == "__main__":
    unittest.main()
