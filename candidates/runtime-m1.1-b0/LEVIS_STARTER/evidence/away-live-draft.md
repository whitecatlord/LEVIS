# LEVIS — unverified proposal

The function `add` incorrectly implements addition by returning the difference (`a - b`) instead of the sum (`a + b`).

Here is the corrected code and a corresponding test:

```python
def add(a, b):
    return a + b

# Test case
def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
```