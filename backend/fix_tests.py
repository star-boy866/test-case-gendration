import os
import glob
for f in glob.glob(r'd:\test-case-gendration\healthcare-nl-testgen\backend\tests\test_*.py'):
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    modified = False
    
    if '@pytest.mark.skip(reason=' in content:
        import re
        content = re.sub(r'@pytest\.mark\.skip\(reason=[^\)]+\)', '@pytest.mark.skip', content)
        modified = True
        
    if modified:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)
