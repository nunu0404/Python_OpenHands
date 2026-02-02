"""This file imports a global singleton of the `EditTool` class as well as raw functions that expose
its __call__.
The implementation of the `EditTool` class can be found at: https://github.com/OpenHands/openhands-aci/.
"""

# Dummy implementation to bypass openhands-aci dependency
class DummyFileEditor:
    pass

file_editor = DummyFileEditor()
# from openhands_aci.editor import file_editor

__all__ = ['file_editor']
