import runpy
import sys
from unittest.mock import patch

def test_orchestrator_main_block():
    # Clear module from cache to avoid runpy warning
    modules_to_clear = [k for k in sys.modules.keys() if k.startswith('core.orchestrator')]
    for mod in modules_to_clear:
        del sys.modules[mod]
    
    with patch("uvicorn.run") as mock_run:
        # run_module executes the code including the if __name__ == "__main__" block
        # if we pass run_name="__main__"
        runpy.run_module("core.orchestrator", run_name="__main__")
        assert mock_run.called
