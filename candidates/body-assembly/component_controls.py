"""Contract regressions for the vendored components; test-only donor draft store."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'components'));sys.path.insert(0,str(ROOT/'components/testsupport/evidence_memory'));sys.path.insert(0,str(ROOT/'components/testsupport/durable_drafts'))
from components import evidence_memory,communication
sys.modules['memory']=evidence_memory
import test_memory,test_draft_bridge,test_modular_b5
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in [test_memory,test_draft_bridge,test_modular_b5,communication])
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())
