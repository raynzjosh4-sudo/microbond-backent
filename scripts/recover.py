import json
import os
import re

log_path = r"C:\Users\raynz\.gemini\antigravity-ide\brain\58b09636-4841-42d7-86fe-38206790a8a9\.system_generated\logs\transcript_full.jsonl"
recovered = {}

with open(log_path, 'r', encoding='utf-8') as f:
    for line_str in f:
        try:
            step = json.loads(line_str)
        except:
            continue
            
        if 'tool_calls' in step and step['tool_calls']:
            for tc in step['tool_calls']:
                func_name = tc.get('name') or tc.get('function', {}).get('name')
                if func_name == 'default_api:write_to_file':
                    args_str = tc.get('args') or tc.get('function', {}).get('arguments')
                    if isinstance(args_str, str):
                        try:
                            args = json.loads(args_str)
                        except:
                            continue
                    elif isinstance(args_str, dict):
                        args = args_str
                    else:
                        continue
                    
                    path = args.get('TargetFile')
                    content = args.get('CodeContent')
                    if path and content and path.endswith('.py'):
                        recovered[os.path.normpath(path).lower()] = content

        content_str = step.get('content', '')
        if isinstance(content_str, str) and 'File Path: `file:///' in content_str:
            matches = re.finditer(r'File Path: `file:///(.+?)`.*?Showing lines \d+ to \d+.*?<original_line>\.\s*Please note.*?\n(.*?)(?:\nThe above content shows|$)', content_str, re.DOTALL)
            for m in matches:
                path = m.group(1).replace('/', '\\')
                path = os.path.normpath(path).lower()
                lines_block = m.group(2)
                if path.endswith('.py'):
                    clean_lines = []
                    for line in lines_block.split('\n'):
                        if re.match(r'^\d+:', line):
                            # line is like "1: import foo" -> split by first colon, take rest, strip first space
                            clean_lines.append(line.split(':', 1)[1][1:])
                    recovered[path] = '\n'.join(clean_lines)

for p, c in recovered.items():
    if c.strip():
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as fw:
            fw.write(c)
        print(f"Recovered {p}")

print(f"Total recovered: {len(recovered)}")
